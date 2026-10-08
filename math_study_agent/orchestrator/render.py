"""Markdown rendering of a `math_study_note/2` (fallback next to the HTML page).

The HTML page (`render_html`) is the primary output. This Markdown version
keeps the same order and labels so the note is readable in any Markdown viewer.
"""

from __future__ import annotations

from fractions import Fraction

from ..epistemics import STATUS_LABELS_KO
from .render_html import DIFFICULTY_LABELS, EXAM_TYPE_LABELS, KIND_LABELS, PROOF_METHOD_LABELS


def _tex_entry(value: str) -> str:
    v = value.strip().replace("−", "-")
    if v == "*":
        return "\\ast"
    try:
        frac = Fraction(v)
        if frac.denominator == 1:
            return str(frac.numerator)
        sign = "-" if frac < 0 else ""
        return f"{sign}\\tfrac{{{abs(frac.numerator)}}}{{{frac.denominator}}}"
    except (ValueError, ZeroDivisionError):
        return v


def _tex_matrix(step: dict) -> str:
    rows = step["matrix"]
    width = len(rows[0])
    aug = step["augmented_col"]
    spec = "c" * width if aug is None else "c" * aug + "|" + "c" * (width - aug)
    body = " \\\\ ".join(" & ".join(_tex_entry(v) for v in row) for row in rows)
    return f"\\left[\\begin{{array}}{{{spec}}} {body} \\end{{array}}\\right]"


def figure_markdown(figure: dict) -> str:
    out = []
    if figure["title"]:
        out.append(f"**{figure['title']}**")
    if figure["kind"] in ("row_reduction", "matrix"):
        for i, step in enumerate(figure["steps"]):
            ops = [f"R_{{{r + 1}}} \\leftarrow {op}" if "\\leftarrow" not in op and "\\leftrightarrow" not in op else op
                   for r, op in enumerate(step["row_ops"]) if op.strip()]
            arrow = f"\\xrightarrow{{{', '.join(ops)}}}" if ops else ("\\longrightarrow" if i else "")
            label = f"\\text{{{step['label']}}}\\;" if step["label"] else ""
            out.append(f"$$ {arrow} \\; {label}{_tex_matrix(step)} $$")
    elif figure["kind"] == "lines_2d":
        out += [f"- ${_fmt(l['a'])}x + {_fmt(l['b'])}y = {_fmt(l['c'])}$ ({l['label']})" for l in figure["lines"]]
    elif figure["kind"] == "flow":
        labels = {n["id"]: n["label"] for n in figure["nodes"]}
        out += [f"- {labels[e['from']]} → **{e['label']}** → {labels[e['to']]}" for e in figure["edges"]]
    if figure["caption"]:
        out.append(f"*{figure['caption']}*")
    return "\n\n".join(out)


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


def render_markdown(note: dict, concept_map: dict, contexts: list[dict], *, quality_report: dict | None = None) -> str:
    names = {c["id"]: c["name"] for c in concept_map["concepts"]}
    core = set(concept_map["core_concepts"])
    out = [f"# {note['title']}", ""]
    if quality_report is not None and not quality_report["passed"]:
        out.append("> **검토 필요**: 자동 품질 검사에서 해결되지 않은 문제가 있습니다.")
        out += [f"> - `{c['check_id']}` {c['message']}" for c in quality_report["checks"]
                if not c["passed"] and c["severity"] == "error"]
        out.append("")
    out += [note["big_picture"].strip(), ""]
    if note["objectives"]:
        out += ["## 이 절을 마치면 할 수 있어야 하는 것", ""] + [f"- {o}" for o in note["objectives"]] + [""]
    if note["key_ideas"]:
        out += ["## 핵심 요약", ""] + [f"{i}. {k}" for i, k in enumerate(note["key_ideas"], 1)] + [""]
    out += ["**개념 흐름:** " + " → ".join(
        (f"**{names.get(c, c)}**" if c in core else names.get(c, c)) for c in note["concept_order"]), ""]

    for number, entry in enumerate(note["entries"], 1):
        out += ["---", "", f"## {number}. {entry['title']}" + (" · 핵심" if entry["concept_id"] in core else ""), ""]
        for block in entry["blocks"]:
            tag = "" if block["status"] == "observed" else f" `[{STATUS_LABELS_KO[block['status']]}]`"
            method = f" ({PROOF_METHOD_LABELS[block['proof_method']]})" if block["kind"] == "proof" and block["proof_method"] else ""
            title = f" · {block['title']}" if block["title"] else ""
            out += [f"### {KIND_LABELS[block['kind']]}{title}{method}{tag}", ""]
            if block["body_markdown"].strip():
                out += [block["body_markdown"].strip(), ""]
            if block["kind"] == "proof":
                out += ["∎", ""]
            if block["figure"]:
                out += [figure_markdown(block["figure"]), ""]
            if block["reconstruction"]:
                out += ["> **수업 설명 재구성 · 추정** (교안 근거로 추정한 설명이며 실제 발언 인용이 아닙니다)", ">"]
                out += [f"> {line}" if line.strip() else ">" for line in block["reconstruction"].strip().split("\n")]
                out.append("")

    if note["summary"]:
        out += ["---", "", "## 핵심 정리", ""] + [f"{i}. {s}" for i, s in enumerate(note["summary"], 1)] + [""]
    exam = note["exam"]
    if exam["true_false"] or exam["problems"]:
        out += ["---", "", "## 시험 대비", ""]
        for i, tf in enumerate(exam["true_false"], 1):
            out += [f"**OX {i}.** {tf['statement_markdown']}", "",
                    f"<details><summary>정답</summary>\n\n**{'참' if tf['answer'] else '거짓'}**. {tf['explanation_markdown']}\n\n</details>", ""]
        for p in exam["problems"]:
            out += [f"**{p['id']}** · {DIFFICULTY_LABELS[p['difficulty']]} · {EXAM_TYPE_LABELS[p['type']]}", "",
                    p["prompt_markdown"], ""]
            if p["figure"]:
                out += [figure_markdown(p["figure"]), ""]
            out += [f"*출제 근거: {p['why_likely']}*", "",
                    f"<details><summary>답과 풀이</summary>\n\n**답** {p['answer_markdown']}\n\n**풀이**\n\n{p['solution_markdown']}\n\n</details>", ""]
    if note["open_questions"]:
        out += ["---", "", "## 아직 확인이 필요한 부분", ""]
        out += [f"- **{q['question']}** {q['reason']}" for q in note["open_questions"]] + [""]
    return "\n".join(out).rstrip() + "\n"
