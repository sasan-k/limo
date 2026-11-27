import dataclasses
from collections.abc import Callable
from pathlib import Path

from limo.llm.ports import LlmError, LlmRequest, LlmResponse, LlmUsage


def tool_use(
    name: str, tool_input: dict[str, object], tool_id: str = "tu_1", usage: LlmUsage | None = None
) -> LlmResponse:
    block = {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}
    return LlmResponse(content=[block], stop_reason="tool_use", model="fake", usage=usage or LlmUsage())


def final(text: str = "done") -> LlmResponse:
    return final_with(LlmUsage(), text)


def final_with(usage: LlmUsage, text: str = "done") -> LlmResponse:
    return LlmResponse(
        content=[{"type": "text", "text": text}], stop_reason="end_turn", model="fake", usage=usage
    )


NEXT_STATUS = {"plan": "planned", "build": "built", "verify": "verified", "close": "review"}


def stage_responder(skills_dir: Path) -> Callable[[LlmRequest], LlmResponse]:
    """Acts like each stage agent: first call sets the next ticket status via fx, second call ends the run."""
    agents = {(skills_dir / a / "SKILL.md").read_text(): a for a in NEXT_STATUS}

    def respond(request: LlmRequest) -> LlmResponse:
        if len(request.messages) > 1:
            return final()
        agent = agents[request.system]
        fields = dict(part.split("=", 1) for part in request.messages[0]["content"].split())
        argv = ["fx", "set", f"work/{fields['feature']}", fields["ticket"], f"status={NEXT_STATUS[agent]}"]
        return tool_use("run_command", {"argv": argv})

    return respond


def resolver_responder(skills_dir: Path, action_text: str) -> Callable[[LlmRequest], LlmResponse]:
    """Resolver requests get `final(action_text)`; every other agent ends at once with `final()`."""
    resolver_prompt = (skills_dir / "resolver" / "SKILL.md").read_text()

    def respond(request: LlmRequest) -> LlmResponse:
        return final(action_text) if request.system == resolver_prompt else final()

    return respond


class FakeLlm:
    """Scripted Claude API: returns queued responses in order, then `final()`; records every request."""

    def __init__(self) -> None:
        self.script: list[LlmResponse] = []
        self.requests: list[LlmRequest] = []
        self.fail_with: LlmError | None = None
        self.repeat: Callable[[], LlmResponse] | None = None
        self.responder: Callable[[LlmRequest], LlmResponse] | None = None

    def create(self, request: LlmRequest) -> LlmResponse:
        self.requests.append(request)
        if self.fail_with is not None:
            raise self.fail_with
        if self.repeat is not None:
            resp = self.repeat()
        elif self.responder is not None:
            resp = self.responder(request)
        else:
            resp = self.script.pop(0) if self.script else final()
        return dataclasses.replace(resp, model=request.model) if resp.model == "fake" else resp
