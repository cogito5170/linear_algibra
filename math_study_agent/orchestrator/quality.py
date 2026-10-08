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
from ..agents.note_editor import block_order_issues, professor_refs
from ..figures import figure_issues
from ..schemas import assert_valid

PROFESSOR_WORD = re.compile(r"교수님|professor", re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+")
_MATH = re.compile(r"\$\$.*?\$\$|\$[^$]*\$", re.DOTALL)

MAX_AVG_SENTENCE_CHARS = 90
MAX_BRIEF_BLOCKS = 6


class QualityReviewer(Agent):
    name = "quality_reviewer"
    input_schema = "math_review_request/2"
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


def _avg_sentence_length(text: str) -> float:
    text = _MATH.sub("수식", text)
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s and s.strip()]
    if not sentences:
        return 0.0
    return sum(len(s) for s in sentences) / len(sentences)


def latex_problems(text: str) -> list[str]:
    """Structural LaTeX errors that make MathJax fail or print raw source."""
    problems = []
    stripped = text.replace("\\$", "")
    if stripped.count("$") % 2:
        problems.append("odd number of '$' delimiters")
    for segment in _MATH.findall(stripped):
        body = segment.strip("$")
        depth = 0
        for ch in body.replace("\\{", "").replace("\\}", ""):
            depth += {"{": 1, "}": -1}.get(ch, 0)
            if depth < 0:
                break
        if depth != 0:
            problems.append(f"unbalanced braces in {segment[:40]!r}")
        begins = re.findall(r"\\begin\{(\w+\*?)\}", body)
        ends = re.findall(r"\\end\{(\w+\*?)\}", body)
        if sorted(begins) != sorted(ends):
            problems.append(f"\\begin/\\end mismatch in {segment[:40]!r}")
        if len(re.findall(r"\\left\b", body)) != len(re.findall(r"\\right\b", body)):
            problems.append(f"\\left/\\right mismatch in {segment[:40]!r}")
    return problems


def _texts(note: dict):
    """Every markdown-bearing field of a v2 note, with a location label."""
    yield "big_picture", note["big_picture"]
    for i, t in enumerate(note["objectives"]):
        yield f"objectives[{i}]", t
    for i, t in enumerate(note["key_ideas"]):
        yield f"key_ideas[{i}]", t
    for i, t in enumerate(note["summary"]):
        yield f"summary[{i}]", t
    for entry in note["entries"]:
        for i, b in enumerate(entry["blocks"]):
            where = f"{entry['concept_id']}.{b['kind']}[{i}]"
            yield where, b["body_markdown"]
            if b["reconstruction"]:
                yield where + ".reconstruction", b["reconstruction"]
            if b["figure"]:
                yield where + ".figure", b["figure"]["caption"]
    for i, tf in enumerate(note["exam"]["true_false"]):
        yield f"exam.tf[{i}]", tf["statement_markdown"] + "\n" + tf["explanation_markdown"]
    for p in note["exam"]["problems"]:
        yield f"exam.{p['id']}", "\n".join([p["prompt_markdown"], p["answer_markdown"], p["solution_markdown"]])


def _figures(note: dict):
    for entry in note["entries"]:
        for i, b in enumerate(entry["blocks"]):
            if b["figure"]:
                yield f"{entry['concept_id']}.{b['kind']}[{i}]", b["figure"]
    for p in note["exam"]["problems"]:
        if p["figure"]:
            yield f"exam.{p['id']}", p["figure"]


def deterministic_checks(note: dict, lesson: dict, concept_map: dict, contexts: list[dict]) -> list[dict]:
    checks: list[dict] = []
    map_concepts = {c["id"]: c for c in concept_map["concepts"]}
    core = set(concept_map["core_concepts"])
    entries = {e["concept_id"]: e for e in note["entries"]}
    prof = professor_refs({"learning_contexts": contexts})

    # -- source fidelity -----------------------------------------------------
    for entry in note["entries"]:
        cid = entry["concept_id"]
        for i, block in enumerate(entry["blocks"]):
            where = f"{cid}.{block['kind']}[{i}]"
            cites_prof = any(r in prof for r in block["refs"])
            if block["kind"] == "professor" or PROFESSOR_WORD.search(block["body_markdown"]):
                checks.append(
                    _check("SF1.professor_attribution", "source_fidelity", "error", cites_prof,
                           f"{where}: 교수님 관련 서술은 검증된 교수님 자료(P id)를 근거로 가져야 함", [where])
                )
            if block["reconstruction"] is not None:
                ok = block["kind"] == "professor" and cites_prof
                checks.append(
                    _check("SF2.reconstruction_scope", "source_fidelity", "error", ok,
                           f"{where}: 교수님 설명 재구성은 P 근거가 있는 교수님 강조 상자에만 쓸 수 있음", [where])
                )

    open_uncertainties = [u["id"] for ctx in contexts for u in ctx["open_questions"]]
    if open_uncertainties:
        surfaced = {r for q in note["open_questions"] for r in q["refs"]}
        surfaced |= {r for e in note["entries"] for b in e["blocks"] for r in b["refs"]}
        missing = sorted(set(open_uncertainties) - surfaced)
        checks.append(
            _check("SF3.uncertainties_surfaced", "source_fidelity", "warning", not missing,
                   "자료의 불확실한 부분이 노트에 드러나야 함" + (f" (누락: {', '.join(missing)})" if missing else ""), missing)
        )

    # -- conceptual clarity / main content first ------------------------------
    for cid in concept_map["core_concepts"]:
        entry = entries.get(cid)
        if entry is None:
            checks.append(_check("CC1.core_entry", "conceptual_clarity", "error", False, f"핵심 개념 {cid}의 항목이 없음", [cid]))
            continue
        checks.append(
            _check("CC1.core_depth", "conceptual_clarity", "error", entry["depth"] == "full", f"{cid}: 핵심 개념은 depth=full", [cid])
        )
        kinds = {b["kind"] for b in entry["blocks"]}
        checks.append(
            _check("IN1.why_present", "intuition", "warning", "why" in kinds, f"{cid}: '왜 배우는가' 보조 설명이 있으면 좋음", [cid])
        )
    for entry in note["entries"]:
        order = block_order_issues(entry, entry["concept_id"])
        checks.append(
            _check("CC2.main_content_first", "conceptual_clarity", "error", not order,
                   "; ".join(order) or f"{entry['concept_id']}: 핵심 내용이 먼저 나옴", [entry["concept_id"]])
        )
    uncovered = sorted(set(map_concepts) - set(entries))
    checks.append(
        _check("CC3.all_concepts_present", "conceptual_clarity", "warning", not uncovered,
               "모든 개념이 노트에 등장해야 함" + (f" (누락: {uncovered})" if uncovered else ""), uncovered)
    )

    # -- proofs ----------------------------------------------------------------
    for entry in note["entries"]:
        kinds = [b["kind"] for b in entry["blocks"]]
        for i, kind in enumerate(kinds):
            if kind != "theorem":
                continue
            following = kinds[i + 1:]
            nxt = next((k for k in following if k in ("theorem", "proof")), None)
            where = f"{entry['concept_id']}.theorem[{i}]"
            checks.append(
                _check("PR1.theorem_has_proof", "logicality", "warning", nxt == "proof",
                       f"{where}: 정리 뒤에 증명이 있어야 함", [where])
            )

    # -- logicality --------------------------------------------------------------
    order = note["concept_order"]
    position = {cid: i for i, cid in enumerate(order)}
    violations = [
        f"{cid}<-{p}"
        for cid in order
        for p in map_concepts.get(cid, {}).get("prerequisites", [])
        if p in position and position[p] > position[cid]
    ]
    checks.append(
        _check("LG1.prerequisite_order", "logicality", "error", not violations,
               "선수 개념이 먼저 설명되어야 함" + (f" (위반: {violations})" if violations else ""), violations)
    )
    flow = [s["concept_id"] for s in concept_map["learning_flow"]]
    checks.append(
        _check("LG2.follows_learning_flow", "logicality", "warning", [c for c in flow if c in position] == order,
               "노트 순서가 Concept Map의 learning_flow와 다름", order)
    )

    # -- exam prep -----------------------------------------------------------------
    checks.append(
        _check("EX1.exam_problems", "user_readability", "warning", bool(note["exam"]["problems"]),
               "시험 대비 예상 문제가 있어야 함", ["exam"])
    )

    # -- readability, LaTeX and figures -------------------------------------------------
    for entry in note["entries"]:
        cid = entry["concept_id"]
        body = "\n".join(b["body_markdown"] for b in entry["blocks"])
        avg = _avg_sentence_length(body)
        checks.append(
            _check("UR1.sentence_length", "user_readability", "warning", avg <= MAX_AVG_SENTENCE_CHARS,
                   f"{cid}: 평균 문장 길이 {avg:.0f}자 (권장 {MAX_AVG_SENTENCE_CHARS}자 이하)", [cid])
        )
        if entry["depth"] == "brief":
            checks.append(
                _check("UR2.brief_is_brief", "user_readability", "warning", len(entry["blocks"]) <= MAX_BRIEF_BLOCKS,
                       f"{cid}: 보조 개념에 상자가 {len(entry['blocks'])}개 (과도한 분할)", [cid])
            )
    latex_errors = [f"{where}: {p}" for where, text in _texts(note) for p in latex_problems(text)]
    checks.append(
        _check("UR3.latex_well_formed", "user_readability", "error", not latex_errors,
               "; ".join(latex_errors[:5]) or "LaTeX 구조 이상 없음", [e.split(":")[0] for e in latex_errors])
    )
    figure_errors = [i for where, f in _figures(note) for i in figure_issues(f, where)]
    checks.append(
        _check("FG1.figures_valid", "mathematical_correctness", "error", not figure_errors,
               "; ".join(figure_errors[:5]) or "그림 데이터 이상 없음", [])
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
