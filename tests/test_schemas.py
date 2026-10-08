import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from math_study_agent.orchestrator import build_learning_contexts, to_v1
from math_study_agent.schemas import ALL_SCHEMAS, export_schemas, get_schema, validate, wire_schema
from math_study_agent.schemas.builders import _WIRE_UNSUPPORTED

from .helpers import ROOT, fixtures


def _walk(schema, path="$"):
    yield path, schema
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key == "properties":
                for name, sub in value.items():
                    yield from _walk(sub, f"{path}.{name}")
            elif isinstance(value, (dict, list)):
                yield from _walk(value, f"{path}/{key}")
    elif isinstance(schema, list):
        for i, item in enumerate(schema):
            yield from _walk(item, f"{path}[{i}]")


class SchemaRegistryTest(unittest.TestCase):
    def test_every_schema_is_a_valid_json_schema(self):
        for schema_id in ALL_SCHEMAS:
            with self.subTest(schema_id):
                Draft202012Validator.check_schema(get_schema(schema_id))

    def test_schema_ids_are_versioned_and_pinned_by_const(self):
        for schema_id, schema in ALL_SCHEMAS.items():
            with self.subTest(schema_id):
                name, version = schema_id.split("/")
                self.assertTrue(version.isdigit())
                self.assertEqual(schema["properties"]["schema"]["const"], schema_id)

    def test_objects_are_closed_and_fully_required(self):
        # Required by the structured-output decoder, and keeps contracts explicit.
        for schema_id in ALL_SCHEMAS:
            for path, node in _walk(ALL_SCHEMAS[schema_id]):
                if isinstance(node, dict) and node.get("type") == "object":
                    with self.subTest(schema_id=schema_id, path=path):
                        self.assertIs(node.get("additionalProperties"), False)
                        self.assertEqual(sorted(node["required"]), sorted(node["properties"]))

    def test_wire_schema_drops_unsupported_keywords_but_keeps_property_names(self):
        wire = wire_schema("math_material_bundle/1")
        for _, node in _walk(wire):
            if isinstance(node, dict):
                self.assertFalse(set(node) & _WIRE_UNSUPPORTED)
        # "title" is a property name of the bundle and must survive.
        self.assertIn("title", wire["properties"])
        self.assertNotIn("minItems", wire["properties"]["sources"])

    def test_exported_schema_files_are_in_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            for path in export_schemas(tmp):
                committed = ROOT / "schemas" / path.name
                self.assertTrue(committed.is_file(), f"run `math-study schemas schemas/` ({path.name} missing)")
                self.assertEqual(json.loads(committed.read_text()), json.loads(Path(path).read_text()))


class ValidationTest(unittest.TestCase):
    def test_example_payloads_are_valid(self):
        f = fixtures()
        for key in ("bundle", "analysis", "concept_map", "lesson", "note", "review"):
            with self.subTest(key):
                self.assertEqual(validate(f[key]), [])

    def test_reports_declared_vs_expected_mismatch(self):
        errors = validate(fixtures()["analysis"], "math_concept_map/1")
        self.assertIn("declares schema", errors[0])

    def test_reports_path_of_bad_field(self):
        analysis = fixtures()["analysis"]
        analysis["concepts"][0]["status"] = "probably"
        analysis["concepts"][0]["confidence"] = 1.5
        errors = validate(analysis)
        self.assertTrue(any(e.startswith("concepts/0/status") for e in errors))
        self.assertTrue(any(e.startswith("concepts/0/confidence") for e in errors))

    def test_extra_fields_are_rejected(self):
        concept_map = fixtures()["concept_map"]
        concept_map["concepts"][0]["professor_said"] = "invented"
        self.assertTrue(validate(concept_map))

    def test_learning_context_v2_projects_onto_v1(self):
        f = fixtures()
        contexts = build_learning_contexts(f["analysis"], f["concept_map"], f["bundle"])
        for ctx in contexts:
            self.assertEqual(validate(ctx), [])
            v1 = to_v1(ctx)
            self.assertEqual(validate(v1), [])
            self.assertNotIn("theorems", v1["content"])
        # v1 stays exactly the published basic contract
        self.assertEqual(
            sorted(ALL_SCHEMAS["math_learning_context/1"]["properties"]),
            sorted(["schema", "source", "concept", "content", "professor_context", "interpretation", "epistemic_status"]),
        )


if __name__ == "__main__":
    unittest.main()
