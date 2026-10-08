import unittest

from math_study_agent.orchestrator import (
    build_learning_contexts,
    build_report,
    deterministic_checks,
    render_html,
    render_markdown,
)
from math_study_agent.orchestrator.mdlite import to_html
from math_study_agent.orchestrator.quality import latex_problems

from .helpers import fixtures


def _block(kind, body="내용", refs=(), status="inferred", **extra):
    block = {"kind": kind, "title": "", "body_markdown": body, "refs": list(refs), "status": status,
             "figure": None, "reconstruction": None, "proof_method": None}
    block.update(extra)
    return block


class DeterministicQualityTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures()
        self.contexts = build_learning_contexts(self.f["analysis"], self.f["concept_map"], self.f["bundle"])

    def report(self):
        checks = deterministic_checks(self.f["note"], self.f["lesson"], self.f["concept_map"], self.contexts)
        return build_report(checks)

    def failed(self, report):
        return {c["check_id"] for c in report["checks"] if not c["passed"]}

    def entry(self, cid):
        return next(e for e in self.f["note"]["entries"] if e["concept_id"] == cid)

    def test_example_passes_without_warnings(self):
        report = self.report()
        self.assertTrue(report["passed"])
        self.assertEqual(report["summary"]["errors"], 0)
        self.assertEqual(report["summary"]["warnings"], 0)

    def test_professor_mentioned_without_evidence(self):
        self.entry("C2")["blocks"].append(_block("warning", "교수님도 이 부분이 제일 중요하다고 하셨다."))
        report = self.report()
        self.assertFalse(report["passed"])
        self.assertIn("SF1.professor_attribution", self.failed(report))

    def test_reconstruction_only_in_professor_blocks(self):
        self.entry("C2")["blocks"].append(_block("explanation", reconstruction="이건 이렇게 이해하면 돼요."))
        self.assertIn("SF2.reconstruction_scope", self.failed(self.report()))

    def test_main_content_must_come_first(self):
        blocks = self.entry("C3")["blocks"]
        blocks.insert(0, _block("why", "왜 배우는가"))
        report = self.report()
        self.assertFalse(report["passed"])
        self.assertIn("CC2.main_content_first", self.failed(report))

    def test_core_concept_needs_full_depth_and_why_is_a_warning(self):
        entry = self.entry("C3")
        entry["depth"] = "brief"
        entry["blocks"] = [b for b in entry["blocks"] if b["kind"] != "why"]
        report = self.report()
        failed = self.failed(report)
        self.assertIn("CC1.core_depth", failed)
        why = next(c for c in report["checks"] if c["check_id"] == "IN1.why_present" and not c["passed"])
        self.assertEqual(why["severity"], "warning")

    def test_theorem_without_proof(self):
        blocks = self.entry("C2")["blocks"]
        self.entry("C2")["blocks"] = [b for b in blocks if b["kind"] != "proof"]
        self.assertIn("PR1.theorem_has_proof", self.failed(self.report()))

    def test_broken_latex_is_an_error(self):
        self.entry("C2")["blocks"][0]["body_markdown"] += " $\\begin{bmatrix} 1 & 2 $"
        report = self.report()
        self.assertFalse(report["passed"])
        self.assertIn("UR3.latex_well_formed", self.failed(report))

    def test_bad_figure_is_an_error(self):
        figure_block = next(b for b in self.entry("C3")["blocks"] if b["kind"] == "example")
        figure_block["figure"]["steps"][1]["matrix"][1].append("9")
        self.assertIn("FG1.figures_valid", self.failed(self.report()))

    def test_order_must_respect_prerequisites(self):
        note = self.f["note"]
        note["entries"].reverse()
        note["concept_order"].reverse()
        self.assertIn("LG1.prerequisite_order", self.failed(self.report()))

    def test_uncertainties_must_be_surfaced(self):
        self.f["note"]["open_questions"] = []
        for entry in self.f["note"]["entries"]:
            for block in entry["blocks"]:
                block["refs"] = [r for r in block["refs"] if not r.startswith("U")]
        self.assertIn("SF3.uncertainties_surfaced", self.failed(self.report()))

    def test_missing_exam_problems_warns(self):
        self.f["note"]["exam"]["problems"] = []
        self.assertIn("EX1.exam_problems", self.failed(self.report()))


class LatexCheckTest(unittest.TestCase):
    def test_well_formed(self):
        self.assertEqual(latex_problems("$\\begin{bmatrix} 1 & 2 \\\\ 3 & 4 \\end{bmatrix}$ 그리고 $\\left[ x \\right]$"), [])
        self.assertEqual(latex_problems("$R_2 \\leftarrow R_2 - 2R_1$"), [])

    def test_problems(self):
        self.assertTrue(latex_problems("$x$ 그리고 $y"))
        self.assertTrue(latex_problems("$\\frac{1}{2$"))
        self.assertTrue(latex_problems("$\\begin{bmatrix} 1 \\end{pmatrix}$"))
        self.assertTrue(latex_problems("$\\left( x$"))


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures()
        self.contexts = build_learning_contexts(self.f["analysis"], self.f["concept_map"], self.f["bundle"])

    def test_html_structure(self):
        page = render_html(self.f["note"], self.f["concept_map"], self.contexts)
        self.assertTrue(page.startswith("<title>"))
        self.assertIn("이 절을 마치면 할 수 있어야 하는 것", page)
        self.assertIn("핵심 요약", page)
        self.assertLess(page.index("핵심 요약"), page.index('id="c-C1"'))
        self.assertIn("수업 설명 재구성 · 추정", page)
        self.assertIn("실제 발언 인용이 아닙니다", page)
        self.assertIn('class="cell pivot"', page)
        self.assertIn("R_{2} \\leftarrow R_2 - 2R_1", page)
        self.assertIn("<svg class=\"plot\"", page)
        self.assertIn('class="flowchart"', page)
        self.assertIn("시험 대비", page)
        self.assertIn("mathjax/3.2.2", page)
        self.assertNotIn("검토 필요", page)

    def test_main_content_is_rendered_before_support(self):
        page = render_html(self.f["note"], self.f["concept_map"], self.contexts)
        c3 = page[page.index('id="c-C3"'):]
        self.assertLess(c3.index("b-definition"), c3.index("이해를 돕는 설명"))

    def test_failed_report_adds_visible_warning(self):
        report = {"passed": False, "checks": [{"check_id": "X", "severity": "error", "passed": False, "message": "m"}]}
        page = render_html(self.f["note"], self.f["concept_map"], self.contexts, quality_report=report)
        self.assertIn("검토 필요", page)
        md = render_markdown(self.f["note"], self.f["concept_map"], self.contexts, quality_report=report)
        self.assertIn("검토 필요", md.splitlines()[2])

    def test_markdown_uses_matrix_format(self):
        md = render_markdown(self.f["note"], self.f["concept_map"], self.contexts)
        self.assertIn("\\left[\\begin{array}{cc}", md)
        self.assertIn("\\xrightarrow{R_{2} \\leftarrow R_2 - 2R_1}", md)
        self.assertEqual(latex_problems(md), [])


class MarkdownLiteTest(unittest.TestCase):
    def test_math_is_protected(self):
        out = to_html("**굵게** $a * b < c$ 와 *기울임*")
        self.assertIn("<strong>굵게</strong>", out)
        self.assertIn("$a * b &lt; c$", out)
        self.assertIn("<em>기울임</em>", out)

    def test_lists_and_tables(self):
        out = to_html("- 하나\n- 둘\n\n1. 첫째\n2. 둘째\n\n| a | b |\n|---|---|\n| 1 | 2 |")
        self.assertIn("<ul><li>하나</li><li>둘</li></ul>", out)
        self.assertIn("<ol><li>첫째</li>", out)
        self.assertIn("<td>1</td>", out)


if __name__ == "__main__":
    unittest.main()
