"""Deterministic Markdown rendering of a `math_study_note/1`.

The Note Editor decides *what* to say; the renderer owns the layout, so that
section order, numbering, epistemic labels and source citations are always
consistent and empty sections never appear.
"""

from __future__ import annotations

from ..epistemics import STATUS_LABELS_KO

SECTION_TITLES = {
    "one_line": "한 줄 직관",
    "why": "왜 배우는가?",
    "core": "핵심 개념",
    "intuition": "직관적으로 이해하기",
    "relations": "개념 사이의 관계",
    "formulas": "핵심 수식",
    "example": "간단한 예",
    "professor": "교수님이 강조한 부분",
    "pitfalls": "헷갈리기 쉬운 부분",
    "previous_link": "이전 개념과 연결",
    "review": "복습 포인트",
}

LEGEND = (
    "> 이 노트는 교안과 필기를 바탕으로 재구성한 것입니다. "
    "섹션 제목의 `[추론]`은 자료에 직접 쓰여 있지 않지만 흐름상 추론한 내용, "
    "`[불확실]`은 자료만으로 확인하기 어려운 내용, `[자료+추론]`은 둘이 섞인 내용입니다. "
    "교수님에 관한 내용은 자료에서 근거를 확인한 것만 실었습니다."
)


def _location(source: dict) -> str:
    if source.get("page") is not None:
        return f"{source['material_id']} p.{source['page']}"
    if source.get("section"):
        return f"{source['material_id']} · {source['section']}"
    return source["material_id"]


def _locations(sources: list[dict]) -> str:
    seen, out = set(), []
    for s in sources:
        label = _location(s)
        if label not in seen:
            seen.add(label)
            out.append(label)
    return ", ".join(out)


def render_markdown(
    note: dict,
    concept_map: dict,
    contexts: list[dict],
    *,
    quality_report: dict | None = None,
) -> str:
    ctx_by_id = {c["concept"]["id"]: c for c in contexts}
    names = {c["id"]: c["name"] for c in concept_map["concepts"]}
    emphasis = {
        p["id"]: p for ctx in contexts for group in ctx["professor_context"].values() for p in group
    }
    source_of_chunk = {s["chunk_id"]: s for ctx in contexts for s in ctx["sources"]}

    out: list[str] = [f"# {note['title']}", ""]

    if quality_report is not None and not quality_report["passed"]:
        out += ["> ⚠️ **검토 필요**: 자동 품질 검사에서 해결되지 않은 문제가 있습니다. 아래 항목을 확인하세요."]
        for c in quality_report["checks"]:
            if not c["passed"] and c["severity"] == "error":
                out.append(f"> - `{c['check_id']}` {c['message']}")
        out.append("")

    out += [LEGEND, "", "## 큰 그림", "", note["big_picture"].strip(), ""]

    if len(note["concept_order"]) > 1:
        flow = " → ".join(names.get(cid, cid) for cid in note["concept_order"])
        out += ["**개념 흐름:** " + flow, ""]

    for entry in note["entries"]:
        cid = entry["concept_id"]
        out += ["---", "", f"# {entry['title']}", ""]
        for number, section in enumerate(entry["sections"], start=1):
            title = SECTION_TITLES[section["key"]]
            label = "" if section["status"] == "observed" else f" `[{STATUS_LABELS_KO[section['status']]}]`"
            out += [f"## {number}. {title}{label}", "", section["body_markdown"].strip(), ""]
            if section["key"] == "professor":
                cited = []
                for ref in section["refs"]:
                    p = emphasis.get(ref)
                    if not p:
                        continue
                    where = _locations([source_of_chunk[ev["chunk_id"]] for ev in p["evidence"] if ev["chunk_id"] in source_of_chunk])
                    who = "내 필기 기록" if p["attribution"] == "user_reported" else "교수님 자료"
                    cited.append(f"{ref} ({who}{': ' + where if where else ''})")
                if cited:
                    out += [f"<sub>근거: {'; '.join(cited)}</sub>", ""]
        ctx = ctx_by_id.get(cid)
        if ctx and ctx["sources"]:
            out += [f"<sub>이 개념의 자료 위치: {_locations(ctx['sources'])}</sub>", ""]

    if note["open_questions"]:
        out += ["---", "", "# 아직 확인이 필요한 부분", ""]
        out += ["자료만으로는 확인할 수 없었던 부분입니다. 교안을 다시 보거나 교수님/조교에게 확인해 보세요.", ""]
        for q in note["open_questions"]:
            out.append(f"- **{q['question'].strip()}** — {q['reason'].strip()}")
        out.append("")

    return "\n".join(out).rstrip() + "\n"
