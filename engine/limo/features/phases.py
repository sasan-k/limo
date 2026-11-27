from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from limo.agents.models import RunIn
from limo.agents.service import RunService
from limo.common.errors import Conflict
from limo.features.repo import FeatureRepo
from limo.projects.models import Project
from limo.runner.tickets import TicketBoard

Phase = Literal["architecture", "spec", "nfr", "tickets"]


@dataclass(frozen=True)
class PhaseAction:
    run: RunIn | None
    reason: Literal["start", "stage_failed", "tickets", "run_active"]


class PhaseService:
    def __init__(self, features: FeatureRepo, runs: RunService, board: TicketBoard) -> None:
        self._features = features
        self._runs = runs
        self._board = board

    def next_action(self, project: Project, feature: str) -> PhaseAction:
        row = self._features.get(project.id, feature)
        if row is None:
            return PhaseAction(run=None, reason="tickets")
        phase: Phase = row.phase
        for _ in range(4):
            outcome = self._phase(project, feature, phase)
            if isinstance(outcome, PhaseAction):
                return outcome
            phase = outcome
            self._features.set_phase(project.id, feature, phase)
        return PhaseAction(run=None, reason="tickets")

    def _phase(self, project: Project, feature: str, phase: Phase) -> PhaseAction | Phase:
        if phase == "architecture":
            action = self._stage(project, feature, "architecture", "mode=init-existing")
            return "spec" if action is None else action
        if phase == "nfr":
            action = self._stage(project, feature, "architecture", f"mode=nfr {feature}")
            return "tickets" if action is None else action
        if phase == "spec":
            return self._spec(project, feature)
        return PhaseAction(run=None, reason="tickets")

    def _spec(self, project: Project, feature: str) -> PhaseAction | Phase:
        action = self._stage(project, feature, "spec", None)
        if action is not None:
            return action
        workspace = Path(project.workspace)
        if not self._board.map_check(workspace, project.name, feature):
            raise Conflict("map_invalid", "fx map-check failed")
        nfr = workspace / "work" / feature / "nfr.md"
        has_nfr = nfr.is_file() and any(line.startswith("| NFR-") for line in nfr.read_text().splitlines())
        return "nfr" if has_nfr else "tickets"

    def _stage(
        self, project: Project, feature: str, agent: Literal["architecture", "spec"], args: str | None
    ) -> PhaseAction | None:
        """Return None when the latest run of this stage succeeded, else the action to take."""
        run = self._runs.latest(project.id, feature, agent, args)
        if run is None:
            return PhaseAction(run=RunIn(agent=agent, feature=feature, args=args), reason="start")
        if run.status in ("queued", "running"):
            return PhaseAction(run=None, reason="run_active")
        if run.status == "failed":
            return PhaseAction(run=None, reason="stage_failed")
        return None
