"""Offline backends: scripted responses (tests), replay from disk (demos), recording."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..errors import LLMError
from .base import LLMClient, LLMRequest, LLMResponse


class ScriptedLLM:
    """Returns pre-defined outputs per agent, in order.

    A scripted item may be a dict (returned as JSON) or an Exception (raised).
    Requests are recorded in `self.requests` for assertions.
    """

    def __init__(self, script: dict[str, list[Any]]):
        self.script = {agent: list(items) for agent, items in script.items()}
        self.requests: list[LLMRequest] = []

    def generate_json(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        queue = self.script.get(request.agent)
        if not queue:
            raise LLMError(f"no scripted response left for agent {request.agent!r}", kind="script_exhausted")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResponse(data=item, raw_text=json.dumps(item, ensure_ascii=False), model="scripted")


class ReplayLLM:
    """Replays recorded outputs from a directory.

    Looks for ``<agent>.<attempt>.json`` first, then ``<agent>.json``.
    """

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        if not self.directory.is_dir():
            raise LLMError(f"replay directory not found: {self.directory}", kind="config")
        self._calls: dict[str, int] = defaultdict(int)

    def generate_json(self, request: LLMRequest) -> LLMResponse:
        self._calls[request.agent] += 1
        n = self._calls[request.agent]
        for candidate in (self.directory / f"{request.agent}.{n}.json", self.directory / f"{request.agent}.json"):
            if candidate.is_file():
                raw = candidate.read_text(encoding="utf-8")
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise LLMError(f"{candidate} is not valid JSON: {exc}", kind="invalid_json", raw_text=raw) from exc
                return LLMResponse(data=data, raw_text=raw, model=f"replay:{candidate.name}")
        raise LLMError(f"no recorded response for agent {request.agent!r} in {self.directory}", kind="replay_missing")


class RecordingLLM:
    """Wraps another backend and writes every request/response to a directory."""

    def __init__(self, inner: LLMClient, directory: str | Path):
        self.inner = inner
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._calls: dict[str, int] = defaultdict(int)

    def generate_json(self, request: LLMRequest) -> LLMResponse:
        self._calls[request.agent] += 1
        stem = f"{request.agent}.{self._calls[request.agent]}"
        (self.directory / f"{stem}.request.md").write_text(
            f"# system\n\n{request.system}\n\n# user\n\n{request.user}\n", encoding="utf-8"
        )
        try:
            response = self.inner.generate_json(request)
        except LLMError as exc:
            (self.directory / f"{stem}.error.txt").write_text(f"{exc.kind}: {exc}\n\n{exc.raw_text or ''}", encoding="utf-8")
            raise
        (self.directory / f"{stem}.json").write_text(
            json.dumps(response.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return response
