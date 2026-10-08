"""Exceptions. A failed agent always raises; it is never treated as a normal result."""

from __future__ import annotations


class MathStudyError(Exception):
    """Base class for all errors raised by this package."""


class SchemaValidationError(MathStudyError):
    def __init__(self, schema_id: str, errors: list[str], context: str = ""):
        self.schema_id = schema_id
        self.errors = list(errors)
        self.context = context
        shown = "\n  - ".join(self.errors[:20])
        more = f"\n  ... and {len(self.errors) - 20} more" if len(self.errors) > 20 else ""
        where = f" ({context})" if context else ""
        super().__init__(f"payload does not match {schema_id}{where}:\n  - {shown}{more}")


class LLMError(MathStudyError):
    """The model call itself failed (refusal, truncation, unparsable output, transport)."""

    def __init__(self, message: str, *, kind: str = "error", raw_text: str | None = None):
        self.kind = kind
        self.raw_text = raw_text
        super().__init__(message)


class AgentError(MathStudyError):
    """An agent could not produce a valid output after all attempts."""

    def __init__(self, agent: str, message: str, *, attempts: list[dict] | None = None):
        self.agent = agent
        self.attempts = attempts or []
        super().__init__(f"[{agent}] {message}")


class PipelineError(MathStudyError):
    """The orchestrator stopped. `stage` tells where, `manifest` holds the run record."""

    def __init__(self, stage: str, cause: Exception, manifest: dict | None = None):
        self.stage = stage
        self.cause = cause
        self.manifest = manifest or {}
        super().__init__(f"pipeline failed at stage '{stage}': {cause}")
