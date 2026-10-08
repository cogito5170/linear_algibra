import tempfile
import unittest
from pathlib import Path

from math_study_agent.ingest import IngestError, build_bundle, chunk_text, load_source
from math_study_agent.schemas import validate

from .helpers import EXAMPLE


class ChunkingTest(unittest.TestCase):
    def test_page_markers_and_headings(self):
        text = "<!-- page: 2 -->\n# Span\n\n정의 문장\n\n--- page 3 ---\n## 일차독립\n본문"
        chunks = chunk_text(text)
        self.assertEqual([(c["page"], c["section"]) for c in chunks], [(2, "Span"), (3, "일차독립")])
        self.assertIn("정의 문장", chunks[0]["text"])

    def test_long_sections_are_split(self):
        text = "# A\n\n" + "\n\n".join("문단 " + "가" * 300 for _ in range(5))
        chunks = chunk_text(text)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(c["section"] == "A" for c in chunks))


class LoadSourceTest(unittest.TestCase):
    def test_example_sources_build_a_valid_bundle(self):
        inputs = EXAMPLE / "inputs"
        bundle = build_bundle(
            [
                load_source(inputs / "slides.md", "lecture_slides", material_id="slides"),
                load_source(inputs / "professor_notes.md", "professor_notes", material_id="prof"),
                load_source(inputs / "user_notes.md", "user_notes", material_id="mine"),
            ],
            title="t",
            bundle_id="b",
        )
        self.assertEqual(validate(bundle), [])
        authors = {s["material_id"]: s["author"] for s in bundle["sources"]}
        self.assertEqual(authors, {"slides": "professor", "prof": "professor", "mine": "user"})
        self.assertEqual(bundle["sources"][0]["chunks"][0]["chunk_id"], "slides#001")

    def test_example_bundle_matches_inputs(self):
        # The committed bundle is what `math-study ingest` produces for the inputs.
        import json

        committed = json.loads((EXAMPLE / "bundle.json").read_text(encoding="utf-8"))
        inputs = EXAMPLE / "inputs"
        rebuilt = build_bundle(
            [
                load_source(inputs / "slides.md", "lecture_slides", material_id="slides"),
                load_source(inputs / "professor_notes.md", "professor_notes", material_id="prof"),
                load_source(inputs / "user_notes.md", "user_notes", material_id="mine"),
            ],
            title=committed["title"],
            bundle_id=committed["bundle_id"],
        )
        self.assertEqual(rebuilt, committed)

    def test_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.md"
            empty.write_text("\n\n", encoding="utf-8")
            with self.assertRaises(IngestError):
                load_source(empty, "user_notes")
            with self.assertRaises(IngestError):
                load_source(Path(tmp) / "missing.md", "user_notes")
            note = Path(tmp) / "n.md"
            note.write_text("x", encoding="utf-8")
            with self.assertRaises(IngestError):
                load_source(note, "podcast")
            src = load_source(note, "user_notes", material_id="same")
            with self.assertRaises(IngestError):
                build_bundle([src, src])


if __name__ == "__main__":
    unittest.main()
