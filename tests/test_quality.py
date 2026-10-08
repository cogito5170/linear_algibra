import unittest

from math_study_agent.orchestrator import build_learning_contexts, build_report, deterministic_checks, render_markdown

from .helpers import fixtures


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
        why = next(s for s in self.entry("C2")["sections"] if s["key"] == "why")
        why["body_markdown"] += " 교수님도 이 부분이 제일 중요하다고 하셨다."
        report = self.report()
        self.assertFalse(report["passed"])
        self.assertIn("SF1.professor_attribution", self.failed(report))

    def test_formula_without_prior_meaning(self):
        entry = self.entry("C2")
        entry["sections"] = [s for s in entry["sections"] if s["key"] not in ("core", "intuition")]
        report = self.report()
        self.assertIn("IN2.meaning_before_formula", self.failed(report))
        self.assertIn("CC2.core_sections", self.failed(report))

    def test_core_concept_needs_why_and_full_depth(self):
        entry = self.entry("C3")
        entry["depth"] = "brief"
        entry["sections"] = [s for s in entry["sections"] if s["key"] != "why"]
        failed = self.failed(self.report())
        self.assertIn("IN1.why_present", failed)
        self.assertIn("CC1.core_depth", failed)

    def test_inferred_motivation_must_not_be_labelled_observed(self):
        why = next(s for s in self.entry("C3")["sections"] if s["key"] == "why")
        why["status"] = "observed"
        self.assertIn("IN3.inferred_why_marked", self.failed(self.report()))

    def test_supplementary_formula_must_be_labelled(self):
        formulas = next(s for s in self.entry("C3")["sections"] if s["key"] == "formulas")
        formulas["body_markdown"] = formulas["body_markdown"].replace("보충", "추가")
        self.assertIn("SF2.supplementary_formula_label", self.failed(self.report()))

    def test_order_must_respect_prerequisites(self):
        note = self.f["note"]
        note["entries"].reverse()
        note["concept_order"].reverse()
        self.assertIn("LG1.prerequisite_order", self.failed(self.report()))

    def test_uncertainties_must_be_surfaced(self):
        self.f["note"]["open_questions"] = []
        for entry in self.f["note"]["entries"]:
            for section in entry["sections"]:
                section["refs"] = [r for r in section["refs"] if not r.startswith("U")]
        self.assertIn("SF3.uncertainties_surfaced", self.failed(self.report()))


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures()
        self.contexts = build_learning_contexts(self.f["analysis"], self.f["concept_map"], self.f["bundle"])

    def test_structure(self):
        md = render_markdown(self.f["note"], self.f["concept_map"], self.contexts)
        self.assertTrue(md.startswith("# 3강."))
        self.assertIn("## 1. 한 줄 직관", md)
        self.assertIn("## 2. 왜 배우는가? `[추론]`", md)
        self.assertIn("근거: P1 (교수님 자료: slides p.4)", md)
        self.assertIn("P6 (내 필기 기록", md)
        self.assertIn("# 아직 확인이 필요한 부분", md)
        self.assertNotIn("검토 필요", md)

    def test_sections_are_renumbered_without_gaps(self):
        md = render_markdown(self.f["note"], self.f["concept_map"], self.contexts)
        brief = md.split("# 일차결합 (Linear Combination)")[1].split("---")[0]
        self.assertIn("## 4. 핵심 수식", brief)  # brief entry has 4 sections, numbered 1..4
        self.assertNotIn("## 5.", brief)

    def test_failed_report_adds_visible_warning(self):
        report = {"passed": False, "checks": [{"check_id": "X", "severity": "error", "passed": False, "message": "m"}]}
        md = render_markdown(self.f["note"], self.f["concept_map"], self.contexts, quality_report=report)
        self.assertIn("⚠️ **검토 필요**", md.splitlines()[2])


if __name__ == "__main__":
    unittest.main()
