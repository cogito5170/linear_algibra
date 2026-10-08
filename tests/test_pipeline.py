import copy
import json
import tempfile
import unittest
from pathlib import Path

from math_study_agent import Orchestrator, OrchestratorConfig, PipelineError
from math_study_agent.errors import LLMError
from math_study_agent.llm import RecordingLLM, ReplayLLM, ScriptedLLM
from math_study_agent.schemas import validate

from .helpers import RECORDED, fixtures, script_from_example


def _broken_latex(note: dict, cid: str) -> dict:
    """A note that passes the editor's own checks but fails the final LaTeX check."""
    note = copy.deepcopy(note)
    entry = next(e for e in note["entries"] if e["concept_id"] == cid)
    entry["blocks"][0]["body_markdown"] += " $\\begin{bmatrix} 1 & 2 $"
    return note


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures()

    def test_replay_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = Orchestrator(ReplayLLM(RECORDED)).run(self.f["bundle"], output_dir=tmp)
            self.assertEqual(result.status, "ok")
            out = Path(tmp)
            for name in ("analysis", "concept_map", "lesson", "note", "quality_report"):
                payload = json.loads((out / f"{name}.json").read_text(encoding="utf-8"))
                self.assertEqual(validate(payload), [], name)
            for ctx in json.loads((out / "learning_contexts.json").read_text(encoding="utf-8")):
                self.assertEqual(validate(ctx), [])
            self.assertEqual((out / "study_note.md").read_text(encoding="utf-8"), result.markdown)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "ok")
            self.assertEqual(
                [s["stage"] for s in manifest["stages"]],
                [
                    "validate_input",
                    "material_analyst",
                    "evidence_guard:analysis",
                    "concept_mapper",
                    "evidence_guard:concept_map",
                    "learning_contexts",
                    "intuition_teacher",
                    "note_editor",
                    "quality_check",
                ],
            )

    def test_agents_communicate_only_through_schemas(self):
        llm = ScriptedLLM(script_from_example())
        Orchestrator(llm).run(self.f["bundle"])
        expected_inputs = {
            "material_analyst": "math_material_bundle/1",
            "concept_mapper": "math_concept_mapping_request/1",
            "intuition_teacher": "math_teaching_request/1",
            "note_editor": "math_note_request/2",
            "quality_reviewer": "math_review_request/2",
        }
        for request in llm.requests:
            self.assertIn(f'<input schema="{expected_inputs[request.agent]}">', request.user)

    def test_quality_failure_triggers_a_revision_with_feedback(self):
        bad = _broken_latex(self.f["note"], "C2")
        llm = ScriptedLLM(
            script_from_example(note_editor=[bad, self.f["note"]], quality_reviewer=[self.f["review"]] * 2)
        )
        result = Orchestrator(llm).run(self.f["bundle"])
        self.assertEqual(result.status, "ok")
        editor_calls = [r for r in llm.requests if r.agent == "note_editor"]
        self.assertEqual(len(editor_calls), 2)
        self.assertIn("UR3.latex_well_formed", editor_calls[1].user)
        stages = [s["stage"] for s in result.manifest["stages"]]
        self.assertIn("note_editor:revision_1", stages)

    def test_unresolved_quality_errors_mark_note_for_review(self):
        bad = _broken_latex(self.f["note"], "C2")
        llm = ScriptedLLM(script_from_example(note_editor=[bad, bad], quality_reviewer=[self.f["review"]] * 2))
        result = Orchestrator(llm).run(self.f["bundle"])
        self.assertEqual(result.status, "needs_review")
        self.assertFalse(result.artifacts["quality_report"]["passed"])
        self.assertIn("검토 필요", result.markdown)

    def test_reviewer_math_error_is_reported(self):
        review = {
            "schema": "math_quality_review/1",
            "findings": [
                {
                    "category": "mathematical_correctness",
                    "severity": "error",
                    "message": "일차독립 정의의 함의 방향이 뒤집혀 있다.",
                    "targets": ["C3.core"],
                    "suggestion": "'영벡터이면 계수가 모두 0'으로 고칠 것",
                }
            ],
            "overall_comment": "",
        }
        llm = ScriptedLLM(script_from_example(note_editor=[self.f["note"]] * 2, quality_reviewer=[review, review]))
        result = Orchestrator(llm).run(self.f["bundle"])
        self.assertEqual(result.status, "needs_review")
        editor_calls = [r for r in llm.requests if r.agent == "note_editor"]
        self.assertIn("함의 방향", editor_calls[1].user)

    def test_reviewer_unavailable_is_not_a_silent_pass(self):
        llm = ScriptedLLM(
            script_from_example(
                note_editor=[self.f["note"]] * 2,
                quality_reviewer=[LLMError("declined", kind="refusal")] * 2,
            )
        )
        result = Orchestrator(llm).run(self.f["bundle"])
        self.assertEqual(result.status, "needs_review")
        self.assertIn("RV.unavailable", [c["check_id"] for c in result.artifacts["quality_report"]["checks"]])

    def test_reviewer_can_be_disabled(self):
        llm = ScriptedLLM(script_from_example(quality_reviewer=[]))
        result = Orchestrator(llm, OrchestratorConfig(use_reviewer=False)).run(self.f["bundle"])
        self.assertEqual(result.status, "ok")
        self.assertNotIn("quality_reviewer", [r.agent for r in llm.requests])

    def test_agent_failure_stops_the_pipeline_with_a_record(self):
        broken_map = copy.deepcopy(self.f["concept_map"])
        broken_map["core_concepts"] = ["C42"]
        llm = ScriptedLLM(script_from_example(concept_mapper=[broken_map, broken_map]))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PipelineError) as ctx:
                Orchestrator(llm).run(self.f["bundle"], output_dir=tmp)
            self.assertEqual(ctx.exception.stage, "concept_mapper")
            manifest = json.loads((Path(tmp) / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "failed")
            self.assertEqual(manifest["failed_stage"], "concept_mapper")
            self.assertEqual(len(manifest["stages"][-1]["attempts"]), 2)
            self.assertTrue((Path(tmp) / "analysis.json").is_file())
            self.assertFalse((Path(tmp) / "study_note.md").exists())
        self.assertNotIn("intuition_teacher", [r.agent for r in llm.requests])

    def test_guard_removes_fabricated_professor_claim_before_teaching(self):
        analysis = copy.deepcopy(self.f["analysis"])
        p2 = next(p for p in analysis["professor_emphasis"] if p["id"] == "P2")
        p2["evidence"][0]["quote"] = "span은 시험에 무조건 나온다"
        # The guard moves P2 to uncertainties. The recorded downstream outputs still cite P2,
        # so the first agent that does (the concept mapper) must be rejected.
        llm = ScriptedLLM(script_from_example(material_analyst=[analysis], concept_mapper=[self.f["concept_map"]] * 2))
        with self.assertRaises(PipelineError) as ctx:
            Orchestrator(llm).run(self.f["bundle"])
        self.assertEqual(ctx.exception.stage, "concept_mapper")
        self.assertIn("unknown id P2", str(ctx.exception))
        self.assertNotIn("intuition_teacher", [r.agent for r in llm.requests])

    def test_guard_removed_claim_never_reaches_the_teacher(self):
        analysis = copy.deepcopy(self.f["analysis"])
        p2 = next(p for p in analysis["professor_emphasis"] if p["id"] == "P2")
        p2["evidence"][0]["quote"] = "span은 시험에 무조건 나온다"
        concept_map = copy.deepcopy(self.f["concept_map"])
        c2 = next(c for c in concept_map["concepts"] if c["id"] == "C2")
        c2["analysis_refs"].remove("P2")
        llm = ScriptedLLM(
            script_from_example(
                material_analyst=[analysis], concept_mapper=[concept_map], intuition_teacher=[self.f["lesson"]] * 2
            )
        )
        with self.assertRaises(PipelineError) as ctx:
            Orchestrator(llm).run(self.f["bundle"])
        self.assertEqual(ctx.exception.stage, "intuition_teacher")
        teach = next(r for r in llm.requests if r.agent == "intuition_teacher")
        self.assertNotIn('"id": "P2"', teach.user)  # only as an uncertainty, never as professor context
        self.assertIn("P2 is not in this concept's professor_context", str(ctx.exception))

    def test_recording_backend_writes_requests_and_responses(self):
        with tempfile.TemporaryDirectory() as tmp:
            llm = RecordingLLM(ReplayLLM(RECORDED), tmp)
            Orchestrator(llm).run(self.f["bundle"])
            files = sorted(p.name for p in Path(tmp).iterdir())
            self.assertIn("material_analyst.1.json", files)
            self.assertIn("note_editor.1.request.md", files)


if __name__ == "__main__":
    unittest.main()
