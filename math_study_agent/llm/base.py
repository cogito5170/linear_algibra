"""LLM backend interface.

Agents never talk to a vendor SDK directly. They build an `LLMRequest` and get
back parsed JSON. This keeps agents testable with scripted/replayed backends.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMRequest:
    agent: str
    system: str
    user: str
    output_schema_id: str
    attempt: int = 1


@dataclass
class LLMResponse:
    data: Any
    raw_text: str
    model: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    def generate_json(self, request: LLMRequest) -> LLMResponse:
        """Return JSON matching `request.output_schema_id` or raise `LLMError`."""
        ...
