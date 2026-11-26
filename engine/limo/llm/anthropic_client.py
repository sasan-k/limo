from typing import Any

import anthropic
from pydantic import SecretStr

from limo.llm.ports import LlmError, LlmRequest, LlmResponse, LlmUsage

MAX_TOKENS = 64000


class AnthropicLlm:
    """Claude Messages API adapter. The SDK client is created on first use."""

    def __init__(self, api_key: SecretStr | None) -> None:
        self._api_key = api_key
        self._client: anthropic.Anthropic | None = None

    def _get_client(self) -> anthropic.Anthropic:
        if self._client is None:
            key = self._api_key.get_secret_value() if self._api_key else None
            self._client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        return self._client

    def create(self, request: LlmRequest) -> LlmResponse:
        try:
            with self._get_client().beta.messages.stream(
                model=request.model,
                max_tokens=MAX_TOKENS,
                system=request.system,
                messages=request.messages,  # type: ignore[arg-type]
                tools=request.tools,  # type: ignore[arg-type]
                thinking={"type": "adaptive"},
                betas=["server-side-fallback-2026-07-01"],
                extra_body={"fallbacks": "default", "output_config": {"effort": "high"}},
            ) as stream:
                message = stream.get_final_message()
        except anthropic.AnthropicError as e:
            raise LlmError(str(e)) from e
        usage = message.usage
        content: list[dict[str, Any]] = [
            b.model_dump(mode="json", exclude_none=True) for b in message.content
        ]
        return LlmResponse(
            content=content,
            stop_reason=str(message.stop_reason),
            model=message.model,
            usage=LlmUsage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_input_tokens or 0,
                cache_write_tokens=usage.cache_creation_input_tokens or 0,
            ),
        )
