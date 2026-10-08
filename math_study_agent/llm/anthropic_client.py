"""Claude backend using the official `anthropic` SDK with structured outputs."""

from __future__ import annotations

import json
from typing import Any

from ..errors import LLMError
from ..schemas import wire_schema
from .base import LLMRequest, LLMResponse

DEFAULT_MODEL = "claude-opus-5-5"


class AnthropicLLM:
    """Calls Claude with the agent's output schema as a structured-output contract.

    - adaptive thinking, explicit effort (Claude Opus 5.5 defaults to "medium")
    - streaming, so long notes do not hit HTTP timeouts
    - server-side refusal fallback (`fallbacks="default"`), on by default
    - refusal / truncation / unparsable output raise `LLMError`, never pass silently
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        *,
        effort: str = "high",
        max_tokens: int = 64000,
        fallbacks: bool = True,
        client: Any = None,
    ):
        if client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - depends on environment
                raise LLMError(
                    "the 'anthropic' package is required for live runs: pip install 'math-study-agent[llm]'",
                    kind="config",
                ) from exc
            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.fallbacks = fallbacks

    def _params(self, request: LLMRequest) -> dict[str, Any]:
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": request.system,
            "messages": [{"role": "user", "content": request.user}],
            "thinking": {"type": "adaptive"},
            "output_config": {
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": wire_schema(request.output_schema_id)},
            },
            "cache_control": {"type": "ephemeral"},
        }

    def _stream(self, params: dict[str, Any]):
        if self.fallbacks:
            return self.client.beta.messages.stream(
                **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
            )
        return self.client.messages.stream(**params)

    def generate_json(self, request: LLMRequest) -> LLMResponse:
        params = self._params(request)
        try:
            with self._stream(params) as stream:
                message = stream.get_final_message()
        except LLMError:
            raise
        except Exception as exc:
            raise _wrap_sdk_error(exc) from exc

        if message.stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise LLMError(f"model declined the request (category={category})", kind="refusal")
        if message.stop_reason == "max_tokens":
            raise LLMError("output truncated at max_tokens", kind="truncated")

        raw = "".join(block.text for block in message.content if getattr(block, "type", None) == "text")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMError(f"model output is not valid JSON: {exc}", kind="invalid_json", raw_text=raw) from exc

        usage = {}
        if getattr(message, "usage", None) is not None:
            for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
                value = getattr(message.usage, key, None)
                if value is not None:
                    usage[key] = value
        return LLMResponse(data=data, raw_text=raw, model=getattr(message, "model", self.model), usage=usage)


def _wrap_sdk_error(exc: Exception) -> LLMError:
    """Map SDK exceptions to LLMError, most specific first."""
    try:
        import anthropic
    except ImportError:  # pragma: no cover
        return LLMError(f"LLM call failed: {exc}", kind="api_error")
    if isinstance(exc, anthropic.RateLimitError):
        return LLMError(f"rate limited: {exc}", kind="rate_limit")
    if isinstance(exc, anthropic.APIStatusError):
        return LLMError(f"API error {exc.status_code}: {exc}", kind="api_error")
    if isinstance(exc, anthropic.APIConnectionError):
        return LLMError(f"connection error: {exc}", kind="connection")
    return LLMError(f"LLM call failed: {exc}", kind="api_error")
