import re
from dataclasses import dataclass
from pathlib import Path

from limo.common.errors import Conflict, NotFound
from limo.executor.ports import Executor, ExecutorError

STATUS_LINE = re.compile(r"^(TKT-\d+): status=(\S+)", re.M)
READY_LINE = re.compile(r"^ready: (.*)$", re.M)


@dataclass(frozen=True)
class TicketRef:
    workspace: Path
    project: str
    feature: str
    ticket: str


@dataclass(frozen=True)
class TicketState:
    id: str
    status: str


def _first_line(text: str) -> str:
    lines = text.strip().splitlines()
    return lines[0] if lines else "fx failed"


class TicketBoard:
    def __init__(self, executor: Executor, fx_db: Path, timeout_s: float) -> None:
        self._executor = executor
        self._fx_db = fx_db
        self._timeout_s = timeout_s

    def read(self, workspace: Path, project: str, feature: str) -> tuple[list[TicketState], list[str]]:
        if not (workspace / "work" / feature / "map.yaml").is_file():
            raise NotFound("feature_not_found", f"feature {feature} not found")
        env = {"FX_DB": str(self._fx_db), "FX_SCOPE": project}
        target = f"work/{feature}"
        try:
            status = self._executor.run(["fx", "status", target], workspace, self._timeout_s, env=env)
            ready = self._executor.run(["fx", "ready", target], workspace, self._timeout_s, env=env)
        except ExecutorError as e:
            raise Conflict("map_invalid", _first_line(str(e))) from e
        for result in (status, ready):
            if result.code != 0:
                raise Conflict("map_invalid", _first_line(result.stderr))
        states = [TicketState(id=i, status=s) for i, s in STATUS_LINE.findall(status.stdout)]
        match = READY_LINE.search(ready.stdout)
        ready_ids = [] if match is None or match.group(1).strip() == "-" else match.group(1).split()
        return states, ready_ids

    def set_status(self, ref: TicketRef, status: str) -> None:
        env = {"FX_DB": str(self._fx_db), "FX_SCOPE": ref.project}
        try:
            result = self._executor.run(
                ["fx", "set", f"work/{ref.feature}", ref.ticket, f"status={status}"],
                ref.workspace,
                self._timeout_s,
                env=env,
            )
        except ExecutorError as e:
            raise Conflict("map_invalid", _first_line(str(e))) from e
        if result.code != 0:
            raise Conflict("map_invalid", _first_line(result.stderr))
