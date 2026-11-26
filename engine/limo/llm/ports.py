from dataclasses import dataclass, field
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
