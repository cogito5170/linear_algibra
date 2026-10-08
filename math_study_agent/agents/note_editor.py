"""Agent 4: edits the lessons into a textbook-style study note."""

from __future__ import annotations

from ..figures import figure_issues
from ..schemas.definitions import MAIN_BLOCK_KINDS, SUPPORT_BLOCK_KINDS
from .base import Agent


def known_refs(payload: dict) -> set[str]:
    """Every id the note may cite: concepts, prerequisites and analysis items in the contexts."""
    refs = {c["id"] for c in payload["concept_map"]["concepts"]}
    refs |= {k["id"] for k in payload["concept_map"]["prerequisites"]}
    for ctx in payload["learning_contexts"]:
        for group in ctx["content"].values():
            refs |= {item["id"] for item in group}
        for group in ctx["professor_context"].values():
            refs |= {item["id"] for item in group}
        refs |= {u["id"] for u in ctx["open_questions"]}
    return refs


def professor_refs(payload: dict) -> set[str]:
    return {
        item["id"]
        for ctx in payload["learning_contexts"]
        for group in ctx["professor_context"].values()
        for item in group
    }


def block_order_issues(entry: dict, where: str) -> list[str]:
    """Main content comes first: no supporting block before the first main block."""
    kinds = [b["kind"] for b in entry["blocks"]]
    first_main = next((i for i, k in enumerate(kinds) if k in MAIN_BLOCK_KINDS), None)
    if first_main is None:
        return [f"{where}: needs at least one {'/'.join(MAIN_BLOCK_KINDS)} block"]
    early = [k for k in kinds[:first_main] if k in SUPPORT_BLOCK_KINDS]
    if early:
        return [f"{where}: supporting blocks {early} come before the main content; move them after it"]
    return []


class NoteEditor(Agent):
    name = "note_editor"
    input_schema = "math_note_request/2"
    output_schema = "math_study_note/2"
    prompt_files = ("shared_principles", "shared_style", "note_editor")
    task_instruction = (
        "아래 lesson을 교재형 공부 노트 `math_study_note/2`로 편집하세요. "
        "개념마다 정의·정리·절차 같은 핵심 내용을 먼저, 직관과 동기는 뒤에 둡니다. "
        "revision_feedback이 있으면 모두 반영하세요."
    )

    def semantic_issues(self, output: dict, payload: dict) -> list[str]:
        issues = []
        concept_map = payload["concept_map"]
        concept_ids = {c["id"] for c in concept_map["concepts"]}
        refs = known_refs(payload)
        prof = professor_refs(payload)

        entry_ids = [e["concept_id"] for e in output["entries"]]
        if output["concept_order"] != entry_ids:
            issues.append("concept_order must list the entries' concept ids in the same order")
        if len(set(entry_ids)) != len(entry_ids):
            issues.append("each concept may appear in only one entry")
        for cid in set(entry_ids) - concept_ids:
            issues.append(f"entry for unknown concept {cid}")
        for cid in concept_map["core_concepts"]:
            if cid not in entry_ids:
                issues.append(f"core concept {cid} has no entry")

        for entry in output["entries"]:
            where = f"entries[{entry['concept_id']}]"
            issues += block_order_issues(entry, where)
            for i, block in enumerate(entry["blocks"]):
                at = f"{where}.blocks[{i}:{block['kind']}]"
                for ref in block["refs"]:
                    if ref not in refs:
                        issues.append(f"{at}: unknown ref {ref}")
                if block["kind"] == "professor":
                    if not any(r in prof for r in block["refs"]):
                        issues.append(f"{at}: a professor block must cite at least one verified P id")
                elif block["reconstruction"] is not None:
                    issues.append(f"{at}: reconstruction is only allowed in professor blocks")
                if block["kind"] == "proof" and block["proof_method"] is None:
                    issues.append(f"{at}: proof blocks need a proof_method")
                if block["kind"] in ("figure", "example") and block["figure"] is not None:
                    issues += figure_issues(block["figure"], at)
                elif block["figure"] is not None:
                    issues.append(f"{at}: figures belong in figure or example blocks")
                if block["kind"] == "figure" and block["figure"] is None:
                    issues.append(f"{at}: figure block without figure data")

        for problem in output["exam"]["problems"]:
            for ref in problem["refs"]:
                if ref not in refs:
                    issues.append(f"exam.problems[{problem['id']}]: unknown ref {ref}")
            if problem["figure"] is not None:
                issues += figure_issues(problem["figure"], f"exam.problems[{problem['id']}]")
        for i, tf in enumerate(output["exam"]["true_false"]):
            for ref in tf["refs"]:
                if ref not in refs:
                    issues.append(f"exam.true_false[{i}]: unknown ref {ref}")
        for q in output["open_questions"]:
            for ref in q["refs"]:
                if ref not in refs:
                    issues.append(f"open_questions: unknown ref {ref}")
        return issues
