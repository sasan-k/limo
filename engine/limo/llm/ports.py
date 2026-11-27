from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class LlmError(Exception):
    pass


@dataclass(frozen=True)
class LlmUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass(frozen=True)
class LlmRequest:
    model: str
    system: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]


@dataclass(frozen=True)
class LlmResponse:
    content: list[dict[str, Any]]
    stop_reason: str
    model: str
    usage: LlmUsage = field(default_factory=LlmUsage)


class LlmClient(Protocol):
    def create(self, request: LlmRequest) -> LlmResponse: ...


@dataclass(frozen=True)
class CliRequest:
    """One agent run as a local `claude -p` session (ADR-14)."""

    model: str
    task: str
    system_prompt_file: Path
    mcp_config_file: Path
    cwd: Path
    timeout_s: float
    max_budget_usd: float | None = None


@dataclass(frozen=True)
class CliResult:
    ok: bool
    text: str
    error: str | None
    usage: LlmUsage
    cost_micros: int


class AgentCli(Protocol):
    """Runs one agent session to the end; `on_event` receives each stream-json event."""

    def run(self, request: CliRequest, on_event: Callable[[dict[str, Any]], None]) -> CliResult: ...
