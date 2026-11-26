import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

from limo.executor.ports import CommandResult, ExecutorError

OUTPUT_LIMIT = 20_000


class LocalExecutor:
    def run(self, argv: Sequence[str], cwd: Path, timeout_s: float) -> CommandResult:
        try:
            proc = subprocess.run(
                ["mise", "exec", "--", *argv],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env={"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")},
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            raise ExecutorError(str(e)) from e
        return CommandResult(
            code=proc.returncode,
            stdout=proc.stdout[:OUTPUT_LIMIT],
            stderr=proc.stderr[:OUTPUT_LIMIT],
        )
