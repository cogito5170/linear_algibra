"""Agent 3: turns the concept map into intuitive, conceptual explanations."""

from __future__ import annotations

from ..figures import figure_issues
from .base import Agent
from .note_editor import known_refs


def _context_index(payload: dict) -> dict[str, dict]:
    return {ctx["concept"]["id"]: ctx for ctx in payload["learning_contexts"]}


class IntuitionTeacher(Agent):
    name = "intuition_teacher"
    input_schema = "math_teaching_request/1"
    output_schema = "math_intuition_lesson/2"
    prompt_files = ("shared_principles", "shared_style", "intuition_teacher")
    task_instruction = (
        "아래 개념 구조와 개념별 learning context로 `math_intuition_lesson/2`를 작성하세요. "
        "learning_flow 순서대로, 모든 개념에 대해 lesson을 하나씩 씁니다. "
        "정리에는 증명을, 교수님 강조에는 자세한 설명과 재구성을, 핵심 계산에는 시각자료를, "
        "시험에 나올 만한 내용에는 예상 문항을 붙이세요."
    )

    def semantic_issues(self, output: dict, payload: dict) -> list[str]:
        issues = []
        concept_ids = {c["id"] for c in payload["concept_map"]["concepts"]}
        contexts = _context_index(payload)
        lessons = output["lessons"]
        covered = [lesson["concept_id"] for lesson in lessons]

        for cid in concept_ids - set(covered):
            issues.append(f"no lesson for concept {cid}")
        for cid in set(covered) - concept_ids:
            issues.append(f"lesson for unknown concept {cid}")
        if len(set(covered)) != len(covered):
            issues.append("each concept must have exactly one lesson")

        for lesson in lessons:
            cid = lesson["concept_id"]
            ctx = contexts.get(cid)
            if ctx is None:
                continue
            where = f"lessons[{cid}]"
            emphasis = {
                p["id"]: p
                for group in ("emphasis", "explanation", "warnings")
                for p in ctx["professor_context"][group]
            }
            for point in lesson["professor_points"]:
                if point["emphasis_ref"] not in emphasis:
                    issues.append(
                        f"{where}.professor_points: {point['emphasis_ref']} is not in this concept's professor_context "
                        "(only verified professor material may be attributed to the professor)"
                    )
            # A lesson may reuse another concept's formula, so check against all contexts.
            all_formula_ids = {f["id"] for c in contexts.values() for f in c["content"]["formulas"]}
            for formula in lesson["formulas"]:
                ref = formula["formula_ref"]
                if formula["origin"] == "material":
                    if ref is None:
                        issues.append(f"{where}.formulas: origin=material needs a formula_ref")
                    elif ref not in all_formula_ids:
                        issues.append(f"{where}.formulas: unknown formula_ref {ref}")
                elif ref is not None:
                    issues.append(f"{where}.formulas: supplementary formulas must have formula_ref=null")
            example = lesson["example"]
            if example and example["example_ref"]:
                all_examples = {e["id"] for c in contexts.values() for e in c["content"]["examples"]}
                if example["example_ref"] not in all_examples:
                    issues.append(f"{where}.example: unknown example_ref {example['example_ref']}")
            for rel in lesson["connections"]["related"]:
                if rel["concept_id"] not in concept_ids:
                    issues.append(f"{where}.connections: unknown concept {rel['concept_id']}")
            all_theorems = {t["id"] for c in contexts.values() for t in c["content"]["theorems"]}
            for proof in lesson["proofs"]:
                if proof["theorem_ref"] and proof["theorem_ref"] not in all_theorems:
                    issues.append(f"{where}.proofs: unknown theorem_ref {proof['theorem_ref']}")
            for i, figure in enumerate(lesson["figures"]):
                issues += figure_issues(figure, f"{where}.figures[{i}]")
            known = known_refs(payload)
            for item in lesson["exam_items"]:
                for ref in item["basis_refs"]:
                    if ref not in known:
                        issues.append(f"{where}.exam_items: unknown basis ref {ref}")
        return issues

