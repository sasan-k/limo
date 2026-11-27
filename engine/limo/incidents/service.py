import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from limo.agents.models import Run, RunIn
from limo.agents.service import RunService
from limo.common.errors import Conflict, ExternalError, NotFound
from limo.events.bus import EventBus
from limo.hosts.issue_repo import IssueRepo
from limo.hosts.ports import HostError, HostProject, RepoHost
from limo.incidents.actions import parse_action
from limo.incidents.apply import ActionApplier, ApplyContext
from limo.incidents.detect import blocking_questions, trigger_for, write_bundle
from limo.incidents.models import Incident, IncidentRow
from limo.incidents.repo import Escalation, IncidentRepo
from limo.projects.models import Project
from limo.projects.repo import ProjectRepo
from limo.runner.models import StepResult
from limo.runner.tickets import TicketBoard, TicketState


def _latest_line(latest: Run | None) -> str:
    if latest is None:
        return "-"
    return f"{latest.agent} {latest.status} {latest.error or '-'}"


def _host_project(project: Project) -> HostProject:
    return HostProject(name=project.name, git_url=project.git_url, kind=project.host)


@dataclass(frozen=True)
class IncidentDeps:
    repo: IncidentRepo
    runs: RunService
    board: TicketBoard
    applier: ActionApplier
    host: RepoHost
    issues: IssueRepo
    projects: ProjectRepo
    events: EventBus


class IncidentService:
    def __init__(self, deps: IncidentDeps, timeout_s: float) -> None:
        self._repo = deps.repo
        self._runs = deps.runs
        self._board = deps.board
        self._applier = deps.applier
        self._host = deps.host
        self._issues = deps.issues
        self._projects = deps.projects
        self._events = deps.events
        self._timeout_s = timeout_s

    def sweep_timeouts(self, project: Project) -> int:
        cutoff = datetime.now(UTC) - timedelta(seconds=self._timeout_s)
        return self._runs.fail_timed_out(project.id, cutoff.isoformat())

    def open_tickets(self, project_id: str, feature: str) -> set[str]:
        return self._repo.blocking_tickets(project_id, feature)

    def escalations(self) -> list[Escalation]:
        return self._repo.escalations()

    def exists(self, incident_id: str) -> bool:
        return self._repo.get(incident_id) is not None

    def handle(self, project: Project, feature: str, states: list[TicketState]) -> StepResult | None:
        outcome = self._apply_finished(project, feature)
        if outcome is not None:
            return outcome
        replied = self._repo.replied(project.id, feature)
        if replied:
            return self._follow_up(project, feature, states, replied[0])
        return self._open_next(project, feature, states)

    def _apply_finished(self, project: Project, feature: str) -> StepResult | None:
        for incident in self._repo.open_for(project.id, feature):
            if incident.resolver_run_id is None:
                continue
            run = self._runs.get(incident.resolver_run_id)
            if run.status in ("succeeded", "failed"):
                return self._apply(project, feature, incident, run)
        return None

    def _apply(self, project: Project, feature: str, incident: IncidentRow, run: Run) -> StepResult:
        failed = run.status == "failed"
        output = f"resolver run failed: {run.error}" if failed else (run.output or "")
        report = Path(project.workspace) / "work" / feature / "reports"
        report = report / f"{incident.ticket}-resolve-{incident.k}.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(output + "\n")
        action = None if failed else parse_action(run.output)
        status = self._applier.apply(
            ApplyContext(project, feature, incident), action, run_failed=run.status == "failed"
        )
        text = None if action is None else json.dumps(action, sort_keys=True)
        self._repo.close(incident.id, status, text)
        return StepResult(run=None, reason=status)

    def _record(self, project: Project, feature: str, row: IncidentRow) -> None:
        self._repo.add(project.id, feature, row)
        payload: dict[str, object] = {
            "incident_id": row.id,
            "feature": feature,
            "ticket": row.ticket,
            "trigger": row.trigger,
        }
        self._events.publish("incident.opened", project.id, payload)

    def _follow_up(
        self, project: Project, feature: str, states: list[TicketState], incident: IncidentRow
    ) -> StepResult:
        self._repo.close(incident.id, "resolved", incident.action)
        state = next((s for s in states if s.id == incident.ticket), None)
        status = state.status if state is not None else "-"
        latest = self._runs.latest_for_ticket(project.id, feature, incident.ticket)
        k = self._repo.count_for(project.id, feature, incident.ticket) + 1
        lines = [
            f"# Incident {incident.ticket} #{k}",
            "- trigger: human-reply",
            f"- ticket status: {status}",
            f"- latest run: {_latest_line(latest)}",
            f"- human reply: {incident.reply}",
        ]
        write_bundle(Path(project.workspace), feature, incident.ticket, k, lines)
        row = IncidentRow(
            id=uuid4().hex,
            ticket=incident.ticket,
            k=k,
            trigger="human-reply",
            status="open",
            run_id=None,
            resolver_run_id=None,
            action=None,
            human_input=True,
        )
        self._record(project, feature, row)
        return self._start_resolver(project, feature, row)

    def consume_note(self, project_id: str, feature: str, ticket: str) -> str | None:
        pending = self._repo.pending_note(project_id, feature, ticket)
        if pending is None:
            return None
        incident_id, fix = pending
        self._repo.set_note_pending(incident_id, False)
        return fix

    def collect_replies(self, project: Project, feature: str) -> None:
        issues = self._issues.for_feature(project.id, feature)
        for row in self._repo.awaiting_reply(project.id, feature):
            issue = issues.get(row.ticket)
            if issue is None:
                continue
            try:
                comments = self._host.issue_comments(_host_project(project), issue.number)
            except HostError as e:
                raise ExternalError("host_error", "repo host call failed") from e
            start = 0
            if row.last_comment_id is not None:
                ids = [comment.id for comment in comments]
                start = ids.index(row.last_comment_id) + 1 if row.last_comment_id in ids else 0
            reply = next((comment for comment in comments[start:] if not comment.mine), None)
            if reply is not None:
                self._repo.set_reply(row.id, reply.body, reply.id)

    def answer(self, incident_id: str, response: str) -> tuple[str, str]:
        if self._repo.get(incident_id) is None:
            raise NotFound("hold_not_found", f"hold {incident_id} not found")
        match = next((e for e in self._repo.escalations() if e.row.id == incident_id), None)
        if match is None:
            raise Conflict("hold_cleared", f"escalation {incident_id} already answered")
        row, name, feature = match.row, match.project, match.feature
        project = self._projects.get_by_name(name)
        if project is None:
            raise NotFound("project_not_found", f"project {name} not found")
        issue = self._issues.for_feature(project.id, feature).get(row.ticket)
        if issue is not None:
            try:
                self._host.comment_issue(_host_project(project), issue.number, response)
            except HostError as e:
                raise ExternalError("host_error", "repo host call failed") from e
        self._repo.set_reply(incident_id, response, None)
        return name, feature

    def _open_next(self, project: Project, feature: str, states: list[TicketState]) -> StepResult | None:
        blocked = self._repo.blocking_tickets(project.id, feature)
        questions = blocking_questions(Path(project.workspace), feature)
        for state in states:
            if state.id in blocked:
                continue
            latest = self._runs.latest_for_ticket(project.id, feature, state.id)
            found = trigger_for(state, latest, questions)
            if found is None or self._repo.exists_for_run(project.id, state.id, found[0], found[1]):
                continue
            return self._open(project, feature, state, latest, found)
        return None

    def _open(
        self,
        project: Project,
        feature: str,
        state: TicketState,
        latest: Run | None,
        found: tuple[str, str | None],
    ) -> StepResult:
        trigger, run_id = found
        k = self._repo.count_for(project.id, feature, state.id) + 1
        lines = [
            f"# Incident {state.id} #{k}",
            f"- trigger: {trigger}",
            f"- ticket status: {state.status}",
            f"- latest run: {_latest_line(latest)}",
        ]
        write_bundle(Path(project.workspace), feature, state.id, k, lines)
        stuck = self._repo.resolver_count(project.id, feature, state.id) >= 2
        row = IncidentRow(
            id=uuid4().hex,
            ticket=state.id,
            k=k,
            trigger=trigger,
            status="needs_human" if stuck else "open",
            run_id=run_id,
            resolver_run_id=None,
            action=None,
        )
        self._record(project, feature, row)
        if stuck:
            ticket = state.id
            try:
                self._applier.escalate(
                    ApplyContext(project, feature, row),
                    f"{ticket} is still stuck after 2 resolver attempts",
                    f"What should Limo do with {ticket}?",
                )
            except HostError as e:
                raise ExternalError("host_error", "repo host call failed") from e
            return StepResult(run=None, reason="needs_human")
        return self._start_resolver(project, feature, row)

    def _start_resolver(self, project: Project, feature: str, row: IncidentRow) -> StepResult:
        run = self._runs.start(
            project.name,
            RunIn(agent="resolver", feature=feature, ticket=row.ticket, args=f"incident={row.k}"),
        )
        self._repo.set_resolver_run(row.id, run.id)
        return StepResult(run=run, reason="resolving")

    def list(self, project: Project, feature: str) -> list[Incident]:
        return [
            Incident(
                id=row.id,
                ticket=row.ticket,
                k=row.k,
                trigger=row.trigger,
                status=row.status,
                action=row.action,
                run_id=row.run_id,
                human_input=row.human_input,
            )
            for row in self._repo.list(project.id, feature)
        ]
