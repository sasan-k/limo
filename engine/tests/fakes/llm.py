from collections.abc import Callable

from limo.llm.ports import LlmError, LlmRequest, LlmResponse, LlmUsage


def tool_use(name: str, tool_input: dict[str, object], tool_id: str = "tu_1") -> LlmResponse:
    block = {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}
    return LlmResponse(content=[block], stop_reason="tool_use", model="fake", usage=LlmUsage())


def final(text: str = "done") -> LlmResponse:
    return LlmResponse(
        content=[{"type": "text", "text": text}], stop_reason="end_turn", model="fake", usage=LlmUsage()
    )


class FakeLlm:
    """Scripted Claude API: returns queued responses in order, then `final()`; records every request."""

    def __init__(self) -> None:
        self.script: list[LlmResponse] = []
        self.requests: list[LlmRequest] = []
        self.fail_with: LlmError | None = None
        self.repeat: Callable[[], LlmResponse] | None = None

    def create(self, request: LlmRequest) -> LlmResponse:
        self.requests.append(request)
        if self.fail_with is not None:
            raise self.fail_with
        if self.repeat is not None:
            return self.repeat()
        return self.script.pop(0) if self.script else final()
