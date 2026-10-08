"""Schema registry and validation.

Usage::

    from math_study_agent.schemas import validate, assert_valid

    errors = validate(payload)              # uses payload["schema"]
    assert_valid(payload, "math_concept_map/1")
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..errors import SchemaValidationError
from .builders import to_wire_schema
from .definitions import ALL_SCHEMAS

__all__ = [
    "ALL_SCHEMAS",
    "assert_valid",
    "export_schemas",
    "get_schema",
    "schema_id_of",
    "to_wire_schema",
    "validate",
    "wire_schema",
]

_VALIDATORS: dict[str, Draft202012Validator] = {}


def get_schema(schema_id: str) -> dict[str, Any]:
    try:
        schema = ALL_SCHEMAS[schema_id]
    except KeyError:
        known = ", ".join(sorted(ALL_SCHEMAS))
        raise KeyError(f"unknown schema id {schema_id!r} (known: {known})") from None
    full = copy.deepcopy(schema)
    full["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    full["$id"] = f"urn:math-study-agent:schema:{schema_id.replace('/', ':v')}"
    full["title"] = schema_id
    return full


def wire_schema(schema_id: str) -> dict[str, Any]:
    """The schema as sent to an LLM structured-output decoder."""
    return to_wire_schema(ALL_SCHEMAS[schema_id])


def _validator(schema_id: str) -> Draft202012Validator:
    if schema_id not in _VALIDATORS:
        _VALIDATORS[schema_id] = Draft202012Validator(get_schema(schema_id))
    return _VALIDATORS[schema_id]


def schema_id_of(payload: Any) -> str | None:
    if isinstance(payload, dict) and isinstance(payload.get("schema"), str):
        return payload["schema"]
    return None


def validate(payload: Any, schema_id: str | None = None) -> list[str]:
    """Return human-readable validation errors (empty list = valid)."""
    declared = schema_id_of(payload)
    schema_id = schema_id or declared
    if schema_id is None:
        return ["payload has no 'schema' field and no schema id was given"]
    if schema_id not in ALL_SCHEMAS:
        return [f"unknown schema id {schema_id!r}"]
    if declared is not None and declared != schema_id:
        return [f"payload declares schema {declared!r} but {schema_id!r} was expected"]
    errors = []
    for err in sorted(_validator(schema_id).iter_errors(payload), key=lambda e: list(e.absolute_path)):
        path = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"{path}: {err.message}")
    return errors


def assert_valid(payload: Any, schema_id: str | None = None, *, context: str = "") -> None:
    errors = validate(payload, schema_id)
    if errors:
        raise SchemaValidationError(schema_id or schema_id_of(payload) or "?", errors, context=context)


def export_schemas(directory: str | Path) -> list[Path]:
    """Write every registered schema to ``<dir>/<name>.v<version>.json``."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for schema_id in sorted(ALL_SCHEMAS):
        name, version = schema_id.split("/")
        path = directory / f"{name}.v{version}.json"
        path.write_text(json.dumps(get_schema(schema_id), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written
