"""Common agent machinery.

An agent is defined only by its contract: input schema, output schema, prompt
and semantic checks. It receives a validated JSON payload and returns a
validated JSON payload. Agents know nothing about each other's internals.

Failure policy: output that fails schema or semantic validation is retried
with the errors fed back. If every attempt fails, `AgentError` is raised. A
bad output is never passed on as if it were fine.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from ..errors import AgentError, LLMError
from ..llm.base import LLMClient, LLMRequest
from ..schemas import assert_valid, validate

# LLM failures that a retry cannot fix.
_FATAL_LLM_KINDS = {"refusal", "config", "replay_missing", "script_exhausted"}


def load_prompt(name: str) -> str:
    return (resources.files("math_study_agent") / "prompts" / f"{name}.md").read_text(encoding="utf-8")


@dataclass
class AgentResult:
    output: dict
    attempts: list[dict] = field(default_factory=list)


class Agent:
    name: str = ""
    input_schema: str = ""
    output_schema: str = ""
    prompt_files: tuple[str, ...] = ("shared_principles",)
    task_instruction: str = ""

    def __init__(self, llm: LLMClient, *, max_attempts: int = 2):
        self.llm = llm
        self.max_attempts = max(1, max_attempts)

    # -- hooks -------------------------------------------------------------

    def system_prompt(self) -> str:
        return "\n\n".join(load_prompt(name) for name in self.prompt_files)

    def render_input(self, payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=1)

    def semantic_issues(self, output: dict, payload: dict) -> list[str]:
        """Checks beyond the JSON schema (references, ordering, coverage)."""
        return []

    # -- driver ------------------------------------------------------------

    def user_message(self, payload: dict, feedback: list[str] | None) -> str:
        parts = [
            self.task_instruction.strip(),
            f"출력 schema: `{self.output_schema}`",
            f"<input schema=\"{self.input_schema}\">\n{self.render_input(payload)}\n</input>",
        ]
        if feedback:
            listed = "\n".join(f"- {item}" for item in feedback[:40])
            parts.append(
                "<previous_attempt_problems>\n"
                "이전 출력이 검사를 통과하지 못했습니다. 아래 문제를 모두 고친 완전한 출력을 다시 작성하세요.\n"
                f"{listed}\n</previous_attempt_problems>"
            )
        return "\n\n".join(p for p in parts if p)

    def run(self, payload: dict) -> AgentResult:
        assert_valid(payload, self.input_schema, context=f"{self.name} input")
        system = self.system_prompt()
        attempts: list[dict] = []
        feedback: list[str] | None = None

        for attempt in range(1, self.max_attempts + 1):
            started = time.monotonic()
            record: dict[str, Any] = {"attempt": attempt}
            request = LLMRequest(
                agent=self.name,
                system=system,
                user=self.user_message(payload, feedback),
                output_schema_id=self.output_schema,
                attempt=attempt,
            )
            try:
                response = self.llm.generate_json(request)
            except LLMError as exc:
                record.update(outcome="llm_error", kind=exc.kind, errors=[str(exc)])
                record["seconds"] = round(time.monotonic() - started, 3)
                attempts.append(record)
                if exc.kind in _FATAL_LLM_KINDS:
                    break
                feedback = [f"출력을 처리할 수 없었습니다 ({exc.kind}): {exc}"]
                continue

            record.update(model=response.model, usage=response.usage)
            errors = validate(response.data, self.output_schema)
            if not errors:
                errors = self.semantic_issues(response.data, payload)
                outcome = "semantic_error" if errors else "ok"
            else:
                outcome = "schema_error"
            record.update(outcome=outcome, errors=errors, seconds=round(time.monotonic() - started, 3))
            attempts.append(record)
            if not errors:
                return AgentResult(output=response.data, attempts=attempts)
            feedback = errors

        last = attempts[-1]["errors"] if attempts else ["no attempt was made"]
        summary = "; ".join(last[:5])
        rejected = [a for a in attempts if a["outcome"] in ("schema_error", "semantic_error")]
        if rejected and rejected[-1] is not attempts[-1]:
            summary += " | last rejected output: " + "; ".join(rejected[-1]["errors"][:5])
        raise AgentError(self.name, f"no valid output after {len(attempts)} attempt(s): {summary}", attempts=attempts)


# ---------------------------------------------------------------------------
# helpers shared by agents' semantic checks
# ---------------------------------------------------------------------------

ANALYSIS_COLLECTIONS = (
    "concepts",
    "definitions",
    "formulas",
    "theorems",
    "examples",
    "professor_emphasis",
    "relationships",
    "uncertainties",
)


def duplicate_ids(items: list[dict], key: str = "id") -> list[str]:
    seen, dupes = set(), []
    for item in items:
        value = item.get(key)
        if value in seen:
            dupes.append(value)
        seen.add(value)
    return dupes


def analysis_ids(analysis: dict) -> set[str]:
    return {item["id"] for name in ANALYSIS_COLLECTIONS for item in analysis.get(name, [])}


def find_cycle(edges: dict[str, list[str]]) -> list[str] | None:
    """Return one cycle in a directed graph {node: [prerequisites]} or None."""
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for nxt in edges.get(node, []):
            if state.get(nxt) == 1:
                return stack[stack.index(nxt):] + [nxt]
            if state.get(nxt) is None:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        state[node] = 2
        return None

    for node in edges:
        if state.get(node) is None:
            found = visit(node)
            if found:
                return found
    return None
