import copy
import unittest

from math_study_agent.agents import ConceptMapper, IntuitionTeacher, MaterialAnalyst, NoteEditor, load_prompt
from math_study_agent.errors import AgentError, LLMError, SchemaValidationError
from math_study_agent.llm import ScriptedLLM
from math_study_agent.orchestrator import build_learning_contexts, default_style_profile

from .helpers import fixtures


class AgentDriverTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures()

    def test_valid_output_on_first_attempt(self):
        llm = ScriptedLLM({"material_analyst": [self.f["analysis"]]})
        result = MaterialAnalyst(llm).run(self.f["bundle"])
        self.assertEqual(result.output, self.f["analysis"])
        self.assertEqual([a["outcome"] for a in result.attempts], ["ok"])
        request = llm.requests[0]
        self.assertEqual(request.output_schema_id, "math_material_analysis/1")
        self.assertIn('<chunk id="slides#004" page="4"', request.user)
        self.assertIn("근거 상태", request.system)  # shared principles are always included

    def test_retry_feeds_back_validation_errors(self):
        broken = copy.deepcopy(self.f["analysis"])
        broken["concepts"][0]["status"] = "maybe"
        llm = ScriptedLLM({"material_analyst": [broken, self.f["analysis"]]})
        result = MaterialAnalyst(llm, max_attempts=2).run(self.f["bundle"])
        self.assertEqual([a["outcome"] for a in result.attempts], ["schema_error", "ok"])
        self.assertNotIn("previous_attempt_problems", llm.requests[0].user)
        self.assertIn("previous_attempt_problems", llm.requests[1].user)
        self.assertIn("concepts/0/status", llm.requests[1].user)

    def test_failure_is_never_returned_as_a_result(self):
        broken = copy.deepcopy(self.f["analysis"])
        broken["definitions"][0]["concept_id"] = "C99"
        llm = ScriptedLLM({"material_analyst": [broken, broken]})
        with self.assertRaises(AgentError) as ctx:
            MaterialAnalyst(llm, max_attempts=2).run(self.f["bundle"])
        self.assertEqual([a["outcome"] for a in ctx.exception.attempts], ["semantic_error", "semantic_error"])
        self.assertIn("C99", str(ctx.exception))

    def test_error_message_keeps_the_rejected_output_reason(self):
        broken = copy.deepcopy(self.f["analysis"])
        broken["definitions"][0]["concept_id"] = "C99"
        llm = ScriptedLLM({"material_analyst": [broken, LLMError("declined", kind="refusal")]})
        with self.assertRaises(AgentError) as ctx:
            MaterialAnalyst(llm, max_attempts=2).run(self.f["bundle"])
        self.assertIn("declined", str(ctx.exception))
        self.assertIn("C99", str(ctx.exception))

    def test_refusal_is_not_retried(self):
        llm = ScriptedLLM({"material_analyst": [LLMError("declined", kind="refusal"), self.f["analysis"]]})
        with self.assertRaises(AgentError) as ctx:
            MaterialAnalyst(llm, max_attempts=3).run(self.f["bundle"])
        self.assertEqual(len(ctx.exception.attempts), 1)
        self.assertEqual(ctx.exception.attempts[0]["kind"], "refusal")

    def test_truncation_is_retried(self):
        llm = ScriptedLLM({"material_analyst": [LLMError("cut", kind="truncated"), self.f["analysis"]]})
        result = MaterialAnalyst(llm, max_attempts=2).run(self.f["bundle"])
        self.assertEqual([a["outcome"] for a in result.attempts], ["llm_error", "ok"])

    def test_invalid_input_is_rejected_before_calling_the_model(self):
        llm = ScriptedLLM({})
        with self.assertRaises(SchemaValidationError):
            MaterialAnalyst(llm).run({"schema": "math_material_bundle/1"})
        self.assertEqual(llm.requests, [])

    def test_prompts_exist_for_every_agent(self):
        for agent in (MaterialAnalyst, ConceptMapper, IntuitionTeacher, NoteEditor):
            for name in agent.prompt_files:
                self.assertTrue(load_prompt(name).strip())


class MaterialAnalystChecksTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures()
        self.agent = MaterialAnalyst(None)

    def issues(self, analysis):
        return self.agent.semantic_issues(analysis, self.f["bundle"])

    def test_example_is_clean(self):
        self.assertEqual(self.issues(self.f["analysis"]), [])

    def test_observed_without_evidence(self):
        self.f["analysis"]["formulas"][0]["evidence"] = []
        self.assertTrue(any("evidence is empty" in i for i in self.issues(self.f["analysis"])))

    def test_unknown_chunk_and_duplicate_id(self):
        a = self.f["analysis"]
        a["examples"][0]["evidence"][0]["chunk_id"] = "slides#404"
        a["examples"][1]["id"] = a["examples"][0]["id"]
        issues = self.issues(a)
        self.assertTrue(any("unknown chunk slides#404" in i for i in issues))
        self.assertTrue(any("duplicate id E1" in i for i in issues))

    def test_material_id_must_match_bundle(self):
        self.f["analysis"]["material_id"] = "other"
        self.assertTrue(self.issues(self.f["analysis"]))


class ConceptMapperChecksTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures()
        self.payload = {"schema": "math_concept_mapping_request/1", "title": "", "analysis": self.f["analysis"]}

    def issues(self, concept_map):
        return ConceptMapper(None).semantic_issues(concept_map, self.payload)

    def concept(self, concept_map, cid):
        return next(c for c in concept_map["concepts"] if c["id"] == cid)

    def test_example_is_clean(self):
        self.assertEqual(self.issues(self.f["concept_map"]), [])

    def test_missing_concept(self):
        m = self.f["concept_map"]
        m["concepts"] = [c for c in m["concepts"] if c["id"] != "C4"]
        issues = self.issues(m)
        self.assertTrue(any("C4" in i and "missing from the map" in i for i in issues))

    def test_prerequisite_cycle(self):
        m = self.f["concept_map"]
        self.concept(m, "C1")["prerequisites"] = ["C3"]
        self.assertTrue(any("cycle" in i for i in self.issues(m)))

    def test_flow_must_respect_prerequisites(self):
        m = self.f["concept_map"]
        m["learning_flow"][1]["concept_id"], m["learning_flow"][2]["concept_id"] = "C3", "C2"
        self.concept(m, "C3")["prerequisites"] = ["C1", "C2"]
        self.assertTrue(any("before its prerequisite C2" in i for i in self.issues(m)))

    def test_new_concepts_cannot_claim_observed(self):
        m = self.f["concept_map"]
        extra = copy.deepcopy(self.concept(m, "C4"))
        extra["id"] = "C5"
        m["concepts"].append(extra)
        m["learning_flow"].append({"step": 5, "concept_id": "C5", "transition": "t", "status": "inferred", "rationale": ""})
        self.assertTrue(any("added by the mapper" in i for i in self.issues(m)))

    def test_unknown_analysis_ref_and_empty_core(self):
        m = self.f["concept_map"]
        self.concept(m, "C2")["analysis_refs"].append("D42")
        m["core_concepts"] = []
        issues = self.issues(m)
        self.assertTrue(any("D42" in i for i in issues))
        self.assertTrue(any("core_concepts is empty" in i for i in issues))


class TeacherAndEditorChecksTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures()
        contexts = build_learning_contexts(self.f["analysis"], self.f["concept_map"], self.f["bundle"])
        self.teach_payload = {
            "schema": "math_teaching_request/1",
            "title": "",
            "style_profile": default_style_profile(),
            "concept_map": self.f["concept_map"],
            "learning_contexts": contexts,
        }
        self.note_payload = {
            **self.teach_payload,
            "schema": "math_note_request/2",
            "lesson": self.f["lesson"],
            "revision_feedback": [],
        }

    def lesson_for(self, cid):
        return next(item for item in self.f["lesson"]["lessons"] if item["concept_id"] == cid)

    def entry_for(self, cid):
        return next(e for e in self.f["note"]["entries"] if e["concept_id"] == cid)

    def test_examples_are_clean(self):
        self.assertEqual(IntuitionTeacher(None).semantic_issues(self.f["lesson"], self.teach_payload), [])
        self.assertEqual(NoteEditor(None).semantic_issues(self.f["note"], self.note_payload), [])

    def test_teacher_cannot_invent_professor_points(self):
        self.lesson_for("C2")["professor_points"].append(
            {"emphasis_ref": "P1", "kind": "emphasis", "paraphrase": "C3의 강조를 C2에 붙임", "detail": "d", "reconstruction": None}
        )
        issues = IntuitionTeacher(None).semantic_issues(self.f["lesson"], self.teach_payload)
        self.assertTrue(any("P1 is not in this concept's professor_context" in i for i in issues))

    def test_teacher_formula_provenance(self):
        formulas = self.lesson_for("C3")["formulas"]
        formulas[0]["formula_ref"] = None  # material formula without reference
        formulas[1]["formula_ref"] = "F1"  # supplementary formula pretending to be from the material
        issues = IntuitionTeacher(None).semantic_issues(self.f["lesson"], self.teach_payload)
        self.assertTrue(any("origin=material needs a formula_ref" in i for i in issues))
        self.assertTrue(any("supplementary formulas must have formula_ref=null" in i for i in issues))

    def test_teacher_must_cover_every_concept(self):
        self.f["lesson"]["lessons"].pop()
        issues = IntuitionTeacher(None).semantic_issues(self.f["lesson"], self.teach_payload)
        self.assertIn("no lesson for concept C4", issues)

    def test_editor_professor_block_needs_verified_ref(self):
        block = next(b for b in self.entry_for("C2")["blocks"] if b["kind"] == "professor")
        block["refs"] = ["D2"]
        issues = NoteEditor(None).semantic_issues(self.f["note"], self.note_payload)
        self.assertTrue(any("must cite at least one verified P id" in i for i in issues))

    def test_editor_main_content_first_and_refs(self):
        blocks = self.entry_for("C3")["blocks"]
        why = next(b for b in blocks if b["kind"] == "why")
        blocks.remove(why)
        blocks.insert(0, why)
        blocks[1]["refs"].append("X1")
        issues = NoteEditor(None).semantic_issues(self.f["note"], self.note_payload)
        self.assertTrue(any("come before the main content" in i for i in issues))
        self.assertTrue(any("unknown ref X1" in i for i in issues))

    def test_editor_reconstruction_only_in_professor_blocks(self):
        self.entry_for("C3")["blocks"][0]["reconstruction"] = "교수님은 이렇게 말했을 거예요."
        issues = NoteEditor(None).semantic_issues(self.f["note"], self.note_payload)
        self.assertTrue(any("reconstruction is only allowed in professor blocks" in i for i in issues))

    def test_figures_are_validated(self):
        figure = self.lesson_for("C3")["figures"][0]
        figure["steps"][1]["highlight"].append({"row": 5, "col": 0, "role": "pivot"})
        figure["steps"][1]["row_ops"] = ["R_1"]
        issues = IntuitionTeacher(None).semantic_issues(self.f["lesson"], self.teach_payload)
        self.assertTrue(any("outside the 2x2 matrix" in i for i in issues))
        self.assertTrue(any("one entry per row" in i for i in issues))

    def test_teacher_proof_refs_must_exist(self):
        self.lesson_for("C2")["proofs"][0]["theorem_ref"] = "T9"
        issues = IntuitionTeacher(None).semantic_issues(self.f["lesson"], self.teach_payload)
        self.assertTrue(any("unknown theorem_ref T9" in i for i in issues))

if __name__ == "__main__":
    unittest.main()
