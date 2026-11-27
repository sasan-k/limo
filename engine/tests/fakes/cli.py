import json
import threading
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from limo.llm.ports import CliRequest, CliResult, LlmError, LlmUsage


@dataclass(frozen=True)
class SeenRun:
    request: CliRequest
    mcp: dict[str, Any]
    mcp_file_mode: int
    system_prompt: str

    @property
    def mcp_path(self) -> str:
        return urlparse(self.mcp["mcpServers"]["limo"]["url"]).path

    @property
    def auth(self) -> str:
        return str(self.mcp["mcpServers"]["limo"]["headers"]["Authorization"])


class FakeCli:
    """Fake local `claude -p` (ADR-14): records each request with its MCP config and system prompt,
    can hold the run open (`hold`) until `release` is set so a test can call the run's MCP endpoint,
    then returns `result` or raises `fail_with`."""

    def __init__(self) -> None:
        self.seen: list[SeenRun] = []
        self.result = CliResult(ok=True, text="done", error=None, usage=LlmUsage(), cost_micros=0)
        self.fail_with: LlmError | None = None
        self.hold = False
        self.started = threading.Event()
        self.release = threading.Event()

    def run(self, request: CliRequest, on_event: Any) -> CliResult:
        mode = request.mcp_config_file.stat().st_mode & 0o777
        mcp = json.loads(request.mcp_config_file.read_text())
        self.seen.append(SeenRun(request, mcp, mode, request.system_prompt_file.read_text()))
        on_event({"type": "assistant"})
        self.started.set()
        if self.hold:
            self.release.wait(10)
        if self.fail_with is not None:
            raise self.fail_with
        return self.result
