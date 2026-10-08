import shutil
import tempfile
import unittest
from pathlib import Path

from math_study_agent.errors import MathStudyError
from math_study_agent.orchestrator import Orchestrator
from math_study_agent.orchestrator.export_pdf import export_pdf, find_chromium, math_to_mathml, print_document, tex_to_mathml
from math_study_agent.llm import ReplayLLM

from .helpers import RECORDED, fixtures

HAS_PANDOC = shutil.which("pandoc") is not None


def _has_chromium() -> bool:
    try:
        find_chromium()
        return True
    except MathStudyError:
        return False


@unittest.skipUnless(HAS_PANDOC, "pandoc not installed")
class MathMLTest(unittest.TestCase):
    def test_matrix_delimiters_become_css_classes(self):
        bracket, vbar = tex_to_mathml([
            ("\\begin{bmatrix} 1 & 2 \\\\ 0 & 1 \\end{bmatrix}", False),
            ("\\begin{vmatrix} a & b \\\\ c & d \\end{vmatrix}", False),
        ])
        self.assertIn('<mtable class="d-bracket"', bracket)
        self.assertNotIn('form="prefix">[', bracket)
        self.assertIn('<mtable class="d-vbar"', vbar)

    def test_augmented_bar_is_drawn(self):
        (mathml,) = tex_to_mathml([("\\left[\\begin{array}{cc|c} 1 & 2 & 3 \\\\ 4 & 5 & 6 \\end{array}\\right]", True)])
        self.assertIn('display="block"', mathml)
        self.assertEqual(mathml.count("border-left: 1.2px solid"), 2)

    def test_html_math_is_replaced(self):
        page, failures = math_to_mathml("<p>값 $x_1 &lt; 2$ 와 $$\\frac{1}{2}$$</p>")
        self.assertEqual(failures, 0)
        self.assertNotIn("$", page)
        self.assertEqual(page.count("<math"), 2)


@unittest.skipUnless(HAS_PANDOC, "pandoc not installed")
class PrintDocumentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        Orchestrator(ReplayLLM(RECORDED)).run(fixtures()["bundle"], output_dir=self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_document_has_cover_lectures_and_open_answers(self):
        from math_study_agent.orchestrator.export_pdf import load_run

        run = load_run(self.tmp.name)
        doc, failures = print_document([run, run], title="테스트")
        self.assertEqual(failures, 0)
        self.assertIn('class="page cover"', doc)
        self.assertEqual(doc.count('<div class="lecture">'), 2)
        self.assertIn('id="l2-c-C3"', doc)
        self.assertNotIn("<details>", doc)
        self.assertIn("<details open>", doc)
        self.assertNotIn("mathjax", doc.lower())

    @unittest.skipUnless(_has_chromium(), "Chromium not available")
    def test_pdf_is_printed(self):
        out = Path(self.tmp.name) / "notes.pdf"
        info = export_pdf([self.tmp.name], out, title="테스트")
        self.assertTrue(out.is_file())
        self.assertGreater(out.stat().st_size, 10_000)
        self.assertEqual(info["math_failures"], 0)


if __name__ == "__main__":
    unittest.main()
