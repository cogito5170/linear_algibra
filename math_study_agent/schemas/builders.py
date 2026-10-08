"""Tiny helpers for writing JSON Schemas in Python.

Schemas are written as plain dicts so that they can be exported to `.json`
files, validated with `jsonschema`, and (after `to_wire_schema`) sent to an LLM
as a structured-output contract.

Convention: every object is closed (`additionalProperties: false`) and every
property is required. Optional values are expressed as `nullable(...)` or as an
empty list. This keeps the contract identical for humans, validators and the
LLM's structured-output decoder.
"""

from __future__ import annotations

from typing import Any

Schema = dict[str, Any]


def obj(properties: dict[str, Schema], description: str | None = None) -> Schema:
    schema: Schema = {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
        "additionalProperties": False,
    }
    if description:
        schema["description"] = description
    return schema


def arr(items: Schema, description: str | None = None, min_items: int | None = None) -> Schema:
    schema: Schema = {"type": "array", "items": items}
    if description:
        schema["description"] = description
    if min_items is not None:
        schema["minItems"] = min_items
    return schema


def string(description: str | None = None, *, pattern: str | None = None, min_length: int | None = None) -> Schema:
    schema: Schema = {"type": "string"}
    if description:
        schema["description"] = description
    if pattern:
        schema["pattern"] = pattern
    if min_length is not None:
        schema["minLength"] = min_length
    return schema


def text(description: str | None = None) -> Schema:
    """A string that must not be blank."""
    return string(description, min_length=1)


def integer(description: str | None = None, *, minimum: int | None = None) -> Schema:
    schema: Schema = {"type": "integer"}
    if description:
        schema["description"] = description
    if minimum is not None:
        schema["minimum"] = minimum
    return schema


def number(description: str | None = None, *, minimum: float | None = None, maximum: float | None = None) -> Schema:
    schema: Schema = {"type": "number"}
    if description:
        schema["description"] = description
    if minimum is not None:
        schema["minimum"] = minimum
    if maximum is not None:
        schema["maximum"] = maximum
    return schema


def boolean(description: str | None = None) -> Schema:
    schema: Schema = {"type": "boolean"}
    if description:
        schema["description"] = description
    return schema


def enum(values: list[str], description: str | None = None) -> Schema:
    schema: Schema = {"type": "string", "enum": list(values)}
    if description:
        schema["description"] = description
    return schema


def const(value: str) -> Schema:
    return {"type": "string", "const": value}


def nullable(schema: Schema) -> Schema:
    return {"anyOf": [schema, {"type": "null"}]}


# Keywords the structured-output decoder does not accept. They stay in the
# canonical schema and are enforced client-side by jsonschema validation.
_WIRE_UNSUPPORTED = {
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "pattern",
    "minItems",
    "maxItems",
    "uniqueItems",
    "$id",
    "$schema",
    "title",
}


def to_wire_schema(schema: Any) -> Any:
    """Return a copy of `schema` restricted to the structured-output subset."""
    if isinstance(schema, dict):
        out = {}
        for key, value in schema.items():
            if key in _WIRE_UNSUPPORTED:
                continue
            if key == "properties":
                out[key] = {name: to_wire_schema(sub) for name, sub in value.items()}
            else:
                out[key] = to_wire_schema(value)
        return out
    if isinstance(schema, list):
        return [to_wire_schema(item) for item in schema]
    return schema
