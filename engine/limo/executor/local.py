import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from limo.executor.ports import CommandResult, ExecutorError

OUTPUT_LIMIT = 20_000


class LocalExecutor:
    def __init__(self, path_prefix: Path | None = None) -> None:
        self._path_prefix = path_prefix

    def run(
        self, argv: Sequence[str], cwd: Path, timeout_s: float, env: Mapping[str, str] | None = None
    ) -> CommandResult:
        path = os.environ.get("PATH", "")
        if self._path_prefix is not None:
            path = f"{self._path_prefix}{os.pathsep}{path}"
        base = {"PATH": path, "HOME": os.environ.get("HOME", "")}
        try:
            proc = subprocess.run(
                ["mise", "exec", "--", *argv],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env={**base, **(env or {})},
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            raise ExecutorError(str(e)) from e
        return CommandResult(
            code=proc.returncode,
            stdout=proc.stdout[:OUTPUT_LIMIT],
            stderr=proc.stderr[:OUTPUT_LIMIT],
        )
