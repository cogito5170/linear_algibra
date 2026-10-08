"""Final quality check run by the orchestrator before a note is released.

Two layers:

1. Deterministic checks (always run): structure, source fidelity of professor
   attributions, intuition-before-formula, ordering, readability heuristics.
2. `QualityReviewer` (LLM): mathematical correctness, logic and readability
   judgements that cannot be checked mechanically.

The report passes only when no check of severity "error" failed.
"""

from __future__ import annotations

import re

from ..agents.base import Agent
from ..agents.note_editor import professor_refs
from ..schemas import assert_valid

PROFESSOR_WORD = re.compile(r"교수님|professor", re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+")
_MATH = re.compile(r"\$\$.*?\$\$|\$[^$]*\$", re.DOTALL)

MAX_AVG_SENTENCE_CHARS = 90
MAX_BRIEF_SECTIONS = 5


class QualityReviewer(Agent):
    name = "quality_reviewer"
    input_schema = "math_review_request/1"
    output_schema = "math_quality_review/1"
    prompt_files = ("shared_principles", "shared_style", "quality_reviewer")
    task_instruction = (
        "아래 공부 노트를 검토해 `math_quality_review/1`을 작성하세요. "
        "analysis의 정의/정리와 대조해 수학적 의미가 바뀐 곳을 특히 주의 깊게 찾으세요."
    )


def _check(check_id, category, severity, passed, message, targets=None, origin="deterministic") -> dict:
    return {
        "check_id": check_id,
        "category": category,
        "severity": severity,
        "passed": bool(passed),
        "message": message,
        "targets": list(targets or []),
        "origin": origin,
    }


def _sections(entry: dict) -> dict[str, dict]:
    return {s["key"]: s for s in entry["sections"]}


def _avg_sentence_length(text: str) -> float:
    text = _MATH.sub("수식", text)
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s and s.strip()]
    if not sentences:
        return 0.0
    return sum(len(s) for s in sentences) / len(sentences)


def deterministic_checks(note: dict, lesson: dict, concept_map: dict, contexts: list[dict]) -> list[dict]:
    checks: list[dict] = []
    map_concepts = {c["id"]: c for c in concept_map["concepts"]}
    core = set(concept_map["core_concepts"])
    entries = {e["concept_id"]: e for e in note["entries"]}
    lessons = {item["concept_id"]: item for item in lesson["lessons"]}
    prof = professor_refs({"learning_contexts": contexts})

    # -- source fidelity -----------------------------------------------------
    for entry in note["entries"]:
        cid = entry["concept_id"]
        for section in entry["sections"]:
            where = f"{cid}.{section['key']}"
            cites_prof = any(r in prof for r in section["refs"])
            mentions_prof = bool(PROFESSOR_WORD.search(section["body_markdown"]))
            if section["key"] == "professor" or mentions_prof:
                checks.append(
                    _check(
                        "SF1.professor_attribution",
                        "source_fidelity",
                        "error",
                        cites_prof,
                        f"{where}: 교수님 관련 서술은 검증된 교수님 자료(P id)를 근거로 가져야 함",
                        [where],
                    )
                )
        lesson_item = lessons.get(cid)
        formulas = _sections(entry).get("formulas")
        if lesson_item and formulas and any(f["origin"] == "supplementary" for f in lesson_item["formulas"]):
            checks.append(
                _check(
                    "SF2.supplementary_formula_label",
                    "source_fidelity",
                    "warning",
                    "보충" in formulas["body_markdown"],
                    f"{cid}.formulas: 교안에 없는 보충 수식은 '보충'이라고 표시해야 함",
                    [f"{cid}.formulas"],
                )
            )

    open_uncertainties = [u["id"] for ctx in contexts for u in ctx["open_questions"]]
    if open_uncertainties:
        surfaced = {r for q in note["open_questions"] for r in q["refs"]}
        surfaced |= {r for e in note["entries"] for s in e["sections"] for r in s["refs"]}
        missing = sorted(set(open_uncertainties) - surfaced)
        checks.append(
            _check(
                "SF3.uncertainties_surfaced",
                "source_fidelity",
                "warning",
                not missing,
                "자료의 불확실한 부분이 노트에 드러나야 함" + (f" (누락: {', '.join(missing)})" if missing else ""),
                missing,
            )
        )

    # -- conceptual clarity --------------------------------------------------
    for cid in concept_map["core_concepts"]:
        entry = entries.get(cid)
        if entry is None:
            checks.append(_check("CC1.core_entry", "conceptual_clarity", "error", False, f"핵심 개념 {cid}의 항목이 없음", [cid]))
            continue
        secs = _sections(entry)
        checks.append(
            _check("CC1.core_depth", "conceptual_clarity", "error", entry["depth"] == "full", f"{cid}: 핵심 개념은 depth=full", [cid])
        )
        missing = [k for k in ("one_line", "core") if k not in secs]
        checks.append(
            _check(
                "CC2.core_sections",
                "conceptual_clarity",
                "error",
                not missing,
                f"{cid}: 핵심 개념에는 한 줄 직관과 핵심 개념 섹션이 필요" + (f" (누락: {missing})" if missing else ""),
                [cid],
            )
        )
    uncovered = sorted(set(map_concepts) - set(entries))
    checks.append(
        _check(
            "CC3.all_concepts_present",
            "conceptual_clarity",
            "warning",
            not uncovered,
            "모든 개념이 노트에 등장해야 함" + (f" (누락: {uncovered})" if uncovered else ""),
            uncovered,
        )
    )

    # -- intuition -----------------------------------------------------------
    for entry in note["entries"]:
        cid = entry["concept_id"]
        secs = _sections(entry)
        if cid in core:
            checks.append(
                _check("IN1.why_present", "intuition", "error", "why" in secs, f"{cid}: '왜 배우는가?'가 있어야 함", [cid])
            )
        if "formulas" in secs:
            checks.append(
                _check(
                    "IN2.meaning_before_formula",
                    "intuition",
                    "error",
                    "core" in secs or "intuition" in secs,
                    f"{cid}: 수식 이전에 의미 설명(핵심 개념/직관)이 있어야 함",
                    [f"{cid}.formulas"],
                )
            )
        why = secs.get("why")
        if why and map_concepts.get(cid, {}).get("why_needed_status") in ("inferred", "uncertain"):
            checks.append(
                _check(
                    "IN3.inferred_why_marked",
                    "source_fidelity",
                    "warning",
                    why["status"] != "observed",
                    f"{cid}.why: 자료에 없는 동기를 observed로 표시하면 안 됨",
                    [f"{cid}.why"],
                )
            )

    # -- logicality ----------------------------------------------------------
    order = note["concept_order"]
    position = {cid: i for i, cid in enumerate(order)}
    violations = [
        f"{cid}<-{p}"
        for cid in order
        for p in map_concepts.get(cid, {}).get("prerequisites", [])
        if p in position and position[p] > position[cid]
    ]
    checks.append(
        _check(
            "LG1.prerequisite_order",
            "logicality",
            "error",
            not violations,
            "선수 개념이 먼저 설명되어야 함" + (f" (위반: {violations})" if violations else ""),
            violations,
        )
    )
    flow = [s["concept_id"] for s in concept_map["learning_flow"]]
    checks.append(
        _check(
            "LG2.follows_learning_flow",
            "logicality",
            "warning",
            [c for c in flow if c in position] == order,
            "노트 순서가 Concept Map의 learning_flow와 다름",
            order,
        )
    )

    # -- readability ---------------------------------------------------------
    for entry in note["entries"]:
        cid = entry["concept_id"]
        body = "\n".join(s["body_markdown"] for s in entry["sections"])
        avg = _avg_sentence_length(body)
        checks.append(
            _check(
                "UR1.sentence_length",
                "user_readability",
                "warning",
                avg <= MAX_AVG_SENTENCE_CHARS,
                f"{cid}: 평균 문장 길이 {avg:.0f}자 (권장 {MAX_AVG_SENTENCE_CHARS}자 이하)",
                [cid],
            )
        )
        if entry["depth"] == "brief":
            checks.append(
                _check(
                    "UR2.brief_is_brief",
                    "user_readability",
                    "warning",
                    len(entry["sections"]) <= MAX_BRIEF_SECTIONS,
                    f"{cid}: 보조 개념에 섹션이 {len(entry['sections'])}개 (과도한 분할)",
                    [cid],
                )
            )
    return checks


def reviewer_checks(review: dict) -> list[dict]:
    return [
        _check(
            f"RV.{f['category']}",
            f["category"],
            f["severity"],
            f["severity"] == "info",
            f["message"] + (f" → {f['suggestion']}" if f["suggestion"] else ""),
            f["targets"],
            origin="reviewer",
        )
        for f in review["findings"]
    ]


def build_report(checks: list[dict]) -> dict:
    failed = [c for c in checks if not c["passed"]]
    report = {
        "schema": "math_quality_report/1",
        "passed": not any(c["severity"] == "error" for c in failed),
        "checks": checks,
        "summary": {
            "errors": sum(1 for c in failed if c["severity"] == "error"),
            "warnings": sum(1 for c in failed if c["severity"] == "warning"),
            "infos": sum(1 for c in checks if c["severity"] == "info"),
        },
    }
    assert_valid(report, context="quality report")
    return report


def revision_feedback(report: dict) -> list[dict]:
    """Failed error/warning checks that the note editor can act on."""
    return [
        {"check_id": c["check_id"], "message": c["message"], "targets": c["targets"]}
        for c in report["checks"]
        if not c["passed"] and c["severity"] in ("error", "warning") and c["origin"] != "guard"
    ]
