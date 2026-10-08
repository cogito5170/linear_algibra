import unittest

from math_study_agent.orchestrator import verify_analysis, verify_concept_map
from math_study_agent.orchestrator.guards import quote_in_chunk
from math_study_agent.schemas import validate

from .helpers import fixtures


def _by_id(items, item_id):
    return next(i for i in items if i["id"] == item_id)


class EvidenceGuardTest(unittest.TestCase):
    def setUp(self):
        f = fixtures()
        self.bundle, self.analysis, self.concept_map = f["bundle"], f["analysis"], f["concept_map"]

    def test_clean_example_passes_unchanged(self):
        result, findings = verify_analysis(self.analysis, self.bundle)
        self.assertEqual(findings, [])
        self.assertEqual(result, self.analysis)

    def test_quote_matching_tolerates_whitespace_and_formatting(self):
        self.assertTrue(quote_in_chunk("하나라도  빼면\nspan이 줄어든다", "**하나라도 빼면 span이 줄어든다.**"))
        self.assertFalse(quote_in_chunk("하나라도 빼면 span이 커진다", "하나라도 빼면 span이 줄어든다."))
        self.assertFalse(quote_in_chunk("   ", "anything"))

    def test_fabricated_quote_downgrades_observed_to_uncertain(self):
        _by_id(self.analysis["definitions"], "D2")["evidence"][0]["quote"] = "span은 항상 R^n 전체이다"
        result, findings = verify_analysis(self.analysis, self.bundle)
        d2 = _by_id(result["definitions"], "D2")
        self.assertEqual(d2["status"], "uncertain")
        self.assertEqual(d2["evidence"], [])
        self.assertLessEqual(d2["confidence"], 0.4)
        self.assertIn("[검증]", d2["rationale"])
        ids = [f["check_id"] for f in findings]
        self.assertIn("GUARD.EVIDENCE_QUOTE", ids)
        self.assertIn("GUARD.DOWNGRADED", ids)
        self.assertEqual(validate(result), [])

    def test_unknown_chunk_is_dropped(self):
        _by_id(self.analysis["formulas"], "F1")["evidence"].append({"chunk_id": "slides#999", "quote": "x"})
        result, findings = verify_analysis(self.analysis, self.bundle)
        self.assertEqual(len(_by_id(result["formulas"], "F1")["evidence"]), 1)
        self.assertEqual(_by_id(result["formulas"], "F1")["status"], "observed")
        self.assertIn("GUARD.EVIDENCE_CHUNK", [f["check_id"] for f in findings])

    def test_unverified_professor_emphasis_becomes_uncertainty(self):
        self.analysis["professor_emphasis"].append(
            {
                "id": "P9",
                "concept_ids": ["C3"],
                "kind": "emphasis",
                "content": "교수님이 기저가 이번 학기 가장 중요하다고 강조",
                "attribution": "professor_material",
                "status": "observed",
                "confidence": 0.9,
                "evidence": [{"chunk_id": "prof#001", "quote": "기저가 이번 학기 가장 중요"}],
                "rationale": "",
            }
        )
        result, findings = verify_analysis(self.analysis, self.bundle)
        self.assertNotIn("P9", [p["id"] for p in result["professor_emphasis"]])
        moved = result["uncertainties"][-1]
        self.assertEqual(moved["id"], "U4")
        self.assertIn("확인되지 않은 교수님", moved["question"])
        self.assertIn("GUARD.EMPHASIS_UNVERIFIED", [f["check_id"] for f in findings])
        self.assertEqual(validate(result), [])

    def test_inferred_professor_emphasis_is_not_kept(self):
        p1 = _by_id(self.analysis["professor_emphasis"], "P1")
        p1["status"] = "inferred"
        result, _ = verify_analysis(self.analysis, self.bundle)
        self.assertNotIn("P1", [p["id"] for p in result["professor_emphasis"]])

    def test_user_only_evidence_is_reattributed(self):
        p6 = _by_id(self.analysis["professor_emphasis"], "P6")
        p6["attribution"] = "professor_material"
        result, findings = verify_analysis(self.analysis, self.bundle)
        self.assertEqual(_by_id(result["professor_emphasis"], "P6")["attribution"], "user_reported")
        self.assertIn("GUARD.ATTRIBUTION", [f["check_id"] for f in findings])

    def test_concept_map_guard(self):
        self.concept_map["dependencies"][0]["evidence"][0]["quote"] = "없는 문장"
        result, findings = verify_concept_map(self.concept_map, self.bundle)
        self.assertEqual(result["dependencies"][0]["status"], "uncertain")
        self.assertTrue(findings)
        self.assertEqual(validate(result), [])


if __name__ == "__main__":
    unittest.main()
