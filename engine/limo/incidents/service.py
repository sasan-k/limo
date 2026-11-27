import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from limo.agents.models import Run, RunIn
from limo.agents.service import RunService
from limo.incidents.actions import RETRY_STATUS, parse_action
from limo.incidents.detect import blocking_questions, trigger_for, write_bundle
from limo.incidents.models import Incident, IncidentRow
from limo.incidents.repo import IncidentRepo
from limo.projects.models import Project
from limo.runner.models import StepResult
from limo.runner.tickets import TicketBoard, TicketRef, TicketState


def _latest_line(latest: Run | None) -> str:
    if latest is None:
        return "-"
    return f"{latest.agent} {latest.status} {latest.error or '-'}"


class IncidentService:
    def __init__(self, repo: IncidentRepo, runs: RunService, board: TicketBoard, timeout_s: float) -> None:
        self._repo = repo
        self._runs = runs
        self._board = board
        self._timeout_s = timeout_s

    def sweep_timeouts(self, project: Project) -> int:
        cutoff = datetime.now(UTC) - timedelta(seconds=self._timeout_s)
        return self._runs.fail_timed_out(project.id, cutoff.isoformat())

    def open_tickets(self, project_id: str, feature: str) -> set[str]:
        return self._repo.blocking_tickets(project_id, feature)

    def handle(self, project: Project, feature: str, states: list[TicketState]) -> StepResult | None:
        outcome = self._apply_finished(project, feature)
        if outcome is not None:
            return outcome
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
        action = None if run.status == "failed" else parse_action(run.output)
        if action is None:
            self._repo.close(incident.id, "needs_human", None)
            return StepResult(run=None, reason="needs_human")
        text = json.dumps(action, sort_keys=True)
        stage = action.get("stage")
        if action["type"] != "retry" or not isinstance(stage, str) or stage not in RETRY_STATUS:
            self._repo.close(incident.id, "needs_human", text)
            return StepResult(run=None, reason="needs_human")
        ref = TicketRef(Path(project.workspace), project.name, feature, incident.ticket)
        self._board.set_status(ref, RETRY_STATUS[stage])
        self._repo.close(incident.id, "resolved", text)
        return StepResult(run=None, reason="resolved")

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
        row = IncidentRow(
            id=uuid4().hex,
            ticket=state.id,
            k=k,
            trigger=trigger,
            status="open",
            run_id=run_id,
            resolver_run_id=None,
            action=None,
        )
        self._repo.add(project.id, feature, row)
        run = self._runs.start(
            project.name, RunIn(agent="resolver", feature=feature, ticket=state.id, args=f"incident={k}")
        )
        self._repo.set_resolver_run(row.id, run.id)
        return StepResult(run=run, reason="resolving")

    def list(self, project: Project, feature: str) -> list[Incident]:
        return [
            Incident(
                ticket=row.ticket,
                k=row.k,
                trigger=row.trigger,
                status=row.status,
                action=row.action,
                run_id=row.run_id,
            )
            for row in self._repo.list(project.id, feature)
        ]
