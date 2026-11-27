from pathlib import Path
from typing import Literal

from limo.agents.models import RunIn
from limo.agents.service import RunService
from limo.common.errors import NotFound
from limo.inbox.service import InboxService
from limo.projects.repo import ProjectRepo
from limo.runner.models import StepResult
from limo.runner.tickets import TicketBoard

AgentName = Literal["plan", "build", "verify", "close"]
NEXT_AGENT: dict[str, AgentName] = {"verified": "close", "built": "verify", "planned": "build"}


class RunnerService:
    def __init__(
        self,
        runs: RunService,
        projects: ProjectRepo,
        board: TicketBoard,
        inbox: InboxService,
        max_concurrent: int,
    ) -> None:
        self._runs = runs
        self._projects = projects
        self._board = board
        self._inbox = inbox
        self._max_concurrent = max_concurrent

    def step(self, project_name: str, feature: str) -> StepResult:
        project = self._projects.get_by_name(project_name)
        if project is None:
            raise NotFound("project_not_found", f"project {project_name} not found")
        if self._runs.active_count() >= self._max_concurrent:
            return StepResult(run=None, reason="run_active")
        states, ready = self._board.read(Path(project.workspace), project.name, feature)
        held = self._inbox.held_tickets(project.id, feature)
        states = [s for s in states if s.id not in held]
        ready = [t for t in ready if t not in held]
        target: tuple[AgentName, str] | None = next(
            ((NEXT_AGENT[s.status], s.id) for s in states if s.status in NEXT_AGENT), None
        )
        if target is None and ready:
            target = ("plan", ready[0])
        if target is None:
            return StepResult(run=None, reason="no_ready_ticket")
        agent, ticket = target
        run = self._runs.start(project.name, RunIn(agent=agent, feature=feature, ticket=ticket))
        return StepResult(run=run, reason="started")

    def continue_hold(self, hold_id: str) -> StepResult:
        hold = self._inbox.take(hold_id)
        return self.step(hold.project, hold.feature)
