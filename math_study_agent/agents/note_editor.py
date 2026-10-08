"""Agent 4: edits the lessons into the final study-note structure."""

from __future__ import annotations

from .base import Agent

SECTION_ORDER = [
    "one_line",
    "why",
    "core",
    "intuition",
    "relations",
    "formulas",
    "example",
    "professor",
    "pitfalls",
    "previous_link",
    "review",
]


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


class NoteEditor(Agent):
    name = "note_editor"
    input_schema = "math_note_request/1"
    output_schema = "math_study_note/1"
    prompt_files = ("shared_principles", "shared_style", "note_editor")
    task_instruction = (
        "아래 lesson을 공부 노트 `math_study_note/1`로 편집하세요. "
        "필요한 섹션만, 정해진 순서로. revision_feedback이 있으면 모두 반영하세요."
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
            keys = [s["key"] for s in entry["sections"]]
            if len(set(keys)) != len(keys):
                issues.append(f"{where}: duplicate section keys {keys}")
            positions = [SECTION_ORDER.index(k) for k in keys]
            if positions != sorted(positions):
                issues.append(f"{where}: sections must follow the order {SECTION_ORDER}")
            for section in entry["sections"]:
                for ref in section["refs"]:
                    if ref not in refs:
                        issues.append(f"{where}.{section['key']}: unknown ref {ref}")
                if section["key"] == "professor":
                    cited = [r for r in section["refs"] if r in prof]
                    if not cited:
                        issues.append(
                            f"{where}.professor: the professor section must cite at least one verified P id"
                        )
        for q in output["open_questions"]:
            for ref in q["refs"]:
                if ref not in refs:
                    issues.append(f"open_questions: unknown ref {ref}")
        return issues
