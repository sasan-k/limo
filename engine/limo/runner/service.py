import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from limo.agents.models import RunIn
from limo.agents.service import RunService
from limo.common.errors import ExternalError, NotFound, Unprocessable
from limo.features.phases import PhaseService
from limo.hosts.issue_repo import IssueRepo
from limo.hosts.issues import IssueService
from limo.inbox.models import InboxItem
from limo.inbox.service import InboxService
from limo.incidents.models import Incident
from limo.incidents.service import IncidentService
from limo.projects.models import Project
from limo.projects.repo import ProjectRepo
from limo.runner.models import PollResult, StepResult
from limo.runner.shipping import ShippingService
from limo.runner.tickets import TicketBoard, TicketState
from limo.vcs.git import GitError, GitOps

AgentName = Literal["plan", "build", "verify", "close"]
NEXT_AGENT: dict[str, AgentName] = {"verified": "close", "built": "verify", "planned": "build"}


@dataclass(frozen=True)
class RunnerDeps:
    runs: RunService
    projects: ProjectRepo
    board: TicketBoard
    inbox: InboxService
    shipping: ShippingService
    git: GitOps
    phases: PhaseService
    issues: IssueService
    incidents: IncidentService
    issue_repo: IssueRepo


class RunnerService:
    def __init__(self, deps: RunnerDeps, max_concurrent: int) -> None:
        self._runs = deps.runs
        self._projects = deps.projects
        self._board = deps.board
        self._inbox = deps.inbox
        self._shipping = deps.shipping
        self._git = deps.git
        self._phases = deps.phases
        self._issues = deps.issues
        self._incidents = deps.incidents
        self._issue_repo = deps.issue_repo
        self._max_concurrent = max_concurrent
        self._lock = threading.RLock()

    def step(self, project_name: str, feature: str) -> StepResult:
        """One runner step; serialized so the runner loop and HTTP callers never dispatch twice."""
        with self._lock:
            return self._step(project_name, feature)

    def _step(self, project_name: str, feature: str) -> StepResult:
        project = self._projects.get_by_name(project_name)
        if project is None:
            raise NotFound("project_not_found", f"project {project_name} not found")
        self._incidents.sweep_timeouts(project)
        if self._runs.active_count() >= self._max_concurrent:
            return StepResult(run=None, reason="run_active")
        action = self._phases.next_action(project, feature)
        if action.run is not None:
            return StepResult(run=self._runs.start(project.name, action.run), reason="started")
        if action.reason in ("stage_failed", "run_active"):
            return StepResult(run=None, reason=action.reason)
        states, ready = self._board.read(Path(project.workspace), project.name, feature)
        self._issues.sync(project, feature, states)
        outcome = self._incidents.handle(project, feature, states)
        if outcome is not None:
            return outcome
        held = set(self._inbox.held_tickets(project.id, feature))
        held |= self._incidents.open_tickets(project.id, feature)
        states = [s for s in states if s.id not in held]
        ready = [t for t in ready if t not in held]
        if self._ship_pending(project, feature, states):
            return StepResult(run=None, reason="shipped")
        target: tuple[AgentName, str, str] | None = next(
            ((NEXT_AGENT[s.status], s.id, s.status) for s in states if s.status in NEXT_AGENT), None
        )
        if target is None and ready:
            target = ("plan", ready[0], "todo")
        if target is None:
            return StepResult(run=None, reason="no_ready_ticket")
        agent, ticket, ticket_status = target
        self._start_branch(project, feature, ticket)
        note = self._incidents.consume_note(project.id, feature, ticket) if agent == "plan" else None
        run = self._runs.start(
            project.name,
            RunIn(agent=agent, feature=feature, ticket=ticket, ticket_status=ticket_status, note=note),
        )
        return StepResult(run=run, reason="started")

    def continue_hold(self, hold_id: str) -> StepResult:
        hold = self._inbox.take(hold_id)
        return self.step(hold.project, hold.feature)

    def inbox(self) -> list[InboxItem]:
        items = [InboxItem(**hold.model_dump(), link=None) for hold in self._inbox.list()]
        for e in self._incidents.escalations():
            project = self._projects.get_by_name(e.project)
            issue = None
            if project is not None:
                issue = self._issue_repo.for_feature(project.id, e.feature).get(e.row.ticket)
            items.append(
                InboxItem(
                    id=e.row.id,
                    project=e.project,
                    feature=e.feature,
                    ticket=e.row.ticket,
                    kind="escalation",
                    reason=e.row.ask or "needs a human",
                    created_at=e.created_at,
                    link=None if issue is None else issue.url,
                )
            )
        return sorted(items, key=lambda item: item.created_at)

    def continue_item(self, item_id: str, response: str | None) -> StepResult:
        if self._inbox.has(item_id):
            return self.continue_hold(item_id)
        if not self._incidents.exists(item_id):
            raise NotFound("hold_not_found", f"item {item_id} not found")
        if response is None:
            raise Unprocessable("response_required", "an escalation needs a response")
        name, feature = self._incidents.answer(item_id, response)
        return self.step(name, feature)

    def poll(self, project_name: str, feature: str) -> PollResult:
        with self._lock:
            return self._poll(project_name, feature)

    def _poll(self, project_name: str, feature: str) -> PollResult:
        project = self._projects.get_by_name(project_name)
        if project is None:
            raise NotFound("project_not_found", f"project {project_name} not found")
        result = self._shipping.poll(project, feature)
        self._incidents.collect_replies(project, feature)
        return result

    def incidents(self, project_name: str, feature: str) -> list[Incident]:
        project = self._projects.get_by_name(project_name)
        if project is None:
            raise NotFound("project_not_found", f"project {project_name} not found")
        return self._incidents.list(project, feature)

    def _ship_pending(self, project: Project, feature: str, states: list[TicketState]) -> bool:
        for state in states:
            if state.status == "review" and self._shipping.needs_ship(project.id, feature, state.id):
                self._shipping.ship(project, feature, state.id)
                return True
        return False

    def _start_branch(self, project: Project, feature: str, ticket: str) -> None:
        try:
            self._git.start_ticket(
                Path(project.workspace), f"limo/{feature}/{ticket}", project.default_branch
            )
        except GitError as e:
            raise ExternalError("git_failed", "git command failed") from e
