from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CommandResult:
    code: int
    stdout: str
    stderr: str


class ExecutorError(Exception):
    pass


class Executor(Protocol):
    def run(self, argv: Sequence[str], cwd: Path, timeout_s: float) -> CommandResult: ...
