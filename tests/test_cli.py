import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from math_study_agent.cli import main

from .helpers import EXAMPLE, RECORDED


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class CliTest(unittest.TestCase):
    def test_run_from_files_with_replay(self):
        inputs = EXAMPLE / "inputs"
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = _run(
                [
                    "run",
                    "--slides", str(inputs / "slides.md"),
                    "--prof-notes", str(inputs / "professor_notes.md"),
                    "--user-notes", str(inputs / "user_notes.md"),
                    "--title", "3강. 일차결합, 생성(Span), 일차독립",
                    "--bundle-id", "la-lec03",
                    "--replay", str(RECORDED),
                    "--out", tmp,
                ]
            )
            self.assertEqual(code, 0, err)
            self.assertIn("status: ok", err)
            self.assertTrue((Path(tmp) / "study_note.md").is_file())
            self.assertTrue((Path(tmp) / "llm" / "material_analyst.1.request.md").is_file())

    def test_run_failure_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = _run(["run", "--bundle", str(EXAMPLE / "bundle.json"), "--replay", tmp])
        self.assertEqual(code, 1)
        self.assertIn("material_analyst", err)

    def test_no_input_is_an_error(self):
        code, _, err = _run(["ingest"])
        self.assertEqual(code, 1)
        self.assertIn("no input", err)

    def test_validate(self):
        code, out, _ = _run(["validate", str(RECORDED / "concept_mapper.json")])
        self.assertEqual(code, 0)
        self.assertIn("valid: math_concept_map/1", out)
        code, out, _ = _run(["validate", str(RECORDED / "concept_mapper.json"), "--schema", "math_study_note/1"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
