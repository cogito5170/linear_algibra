"""Textbook-style HTML rendering of a `math_study_note/2`.

Layout follows the common structure of well-known math textbooks:
objectives and key ideas up front (Margalit-Rabinoff "Objectives"),
boxed definitions / theorems / procedures with proofs, worked examples with
step-by-step figures, a "review of the key ideas" at the end (Strang) and
practice/exam problems with written-out solutions (Lay, Anton).

Math is typeset by MathJax (SVG output, so no web fonts are needed).
Figures are drawn here from the note's numeric figure data.
"""

from __future__ import annotations

import html
import json
import math
from fractions import Fraction

from ..epistemics import STATUS_LABELS_KO
from .mdlite import to_html

MATHJAX = "https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-svg.js"
FONTS = (
    "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500&"
    "family=IBM+Plex+Sans+KR:wght@400;600;700&family=Noto+Serif+KR:wght@600;800&display=swap"
)

KIND_LABELS = {
    "definition": "정의",
    "theorem": "정리",
    "proof": "증명",
    "recipe": "계산 절차",
    "explanation": "핵심 설명",
    "example": "예제",
    "figure": "그림",
    "professor": "교수님 강조",
    "warning": "주의",
    "intuition": "직관",
    "why": "왜 배우는가",
    "connection": "개념 연결",
}
PROOF_METHOD_LABELS = {
    "intuitive": "직관적 논증",
    "counterexample": "반례",
    "via_proposition": "명제 이용",
    "direct": "직접 계산",
}
DIFFICULTY_LABELS = {"basic": "기본", "standard": "표준", "advanced": "심화"}
EXAM_TYPE_LABELS = {
    "true_false": "참/거짓",
    "short_answer": "단답",
    "computation": "계산",
    "proof": "증명",
    "concept": "개념",
}

CSS = """
/* Layout: one reading column like a textbook page; boxed blocks colored by role. */
:root {
  --bg: #f6f7f9; --paper: #ffffff; --ink: #1c2230; --muted: #5d6676; --rule: #dde2ea; --tint: #eef1f6;
  --accent: #2450b8;
  --def: #2450b8; --def-bg: #eef3fd;
  --thm: #6f3bb0; --thm-bg: #f4effb;
  --rec: #17775a; --rec-bg: #ebf7f2;
  --prof: #a35a07; --prof-bg: #fdf4e6;
  --warn: #b5352a; --warn-bg: #fcefed;
  --pivot: #2450b8; --pivot-ink: #ffffff; --elim: #d9f0e3; --free: #fff1cc;
  --c1: #2450b8; --c2: #c2410c; --c3: #17775a;
  --font-display: "Noto Serif KR", "Apple SD Gothic Neo", serif;
  --font-body: "IBM Plex Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #11141b; --paper: #181c25; --ink: #e5e8ee; --muted: #9aa3b3; --rule: #2b3241; --tint: #202634;
  --accent: #86a8ff;
  --def: #86a8ff; --def-bg: #1a2338; --thm: #c4a1ff; --thm-bg: #241d36; --rec: #5ccfa3; --rec-bg: #15291f;
  --prof: #f0aa55; --prof-bg: #2c2214; --warn: #ff8a7a; --warn-bg: #2e1a19;
  --pivot: #86a8ff; --pivot-ink: #11141b; --elim: #1d3a2c; --free: #3a3016;
  --c1: #86a8ff; --c2: #ff9a62; --c3: #5ccfa3; color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #11141b; --paper: #181c25; --ink: #e5e8ee; --muted: #9aa3b3; --rule: #2b3241; --tint: #202634;
  --accent: #86a8ff;
  --def: #86a8ff; --def-bg: #1a2338; --thm: #c4a1ff; --thm-bg: #241d36; --rec: #5ccfa3; --rec-bg: #15291f;
  --prof: #f0aa55; --prof-bg: #2c2214; --warn: #ff8a7a; --warn-bg: #2e1a19;
  --pivot: #86a8ff; --pivot-ink: #11141b; --elim: #1d3a2c; --free: #3a3016;
  --c1: #86a8ff; --c2: #ff9a62; --c3: #5ccfa3; color-scheme: dark; }
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--ink); font-family: var(--font-body); font-size: 16px; line-height: 1.75; }
.page { max-width: 46rem; margin: 0 auto; padding-inline: 16px; padding-block: 32px 64px; display: grid; gap: 28px; }
h1, h2, h3 { font-family: var(--font-display); text-wrap: balance; line-height: 1.35; margin: 0; }
h1 { font-size: 1.9rem; font-weight: 800; }
h2 { font-size: 1.45rem; font-weight: 800; }
h3 { font-size: 1.05rem; font-weight: 600; }
p { margin: 0; }
.flow > * + * { margin-top: 0.7em; }
ul, ol { margin: 0; padding-left: 1.4em; }
li + li { margin-top: 0.25em; }
code { font-family: var(--font-mono); font-size: 0.9em; background: var(--tint); padding: 0 4px; border-radius: 4px; }
blockquote { margin: 0; padding: 8px 14px; border-left: 3px solid var(--rule); color: var(--muted); }
.eyebrow { font-family: var(--font-mono); font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
.lede { color: var(--muted); }
.panel { background: var(--paper); border: 1px solid var(--rule); border-radius: 10px; padding: 18px 20px; }
.panel h2 { font-size: 1.1rem; margin-bottom: 10px; }
.objectives li::marker { color: var(--accent); }
.keyideas ol { padding-left: 1.6em; }
.keyideas li::marker { font-family: var(--font-mono); color: var(--accent); }
.toc { display: flex; flex-wrap: wrap; gap: 6px 4px; align-items: center; font-size: 0.88rem; }
.toc a { color: var(--ink); text-decoration: none; border: 1px solid var(--rule); background: var(--paper); border-radius: 999px; padding: 2px 10px; }
.toc a.core { border-color: var(--accent); color: var(--accent); font-weight: 600; }
.toc a:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.toc .sep { color: var(--muted); }
.legend { font-size: 0.82rem; color: var(--muted); }
.concept { display: grid; gap: 14px; scroll-margin-top: 16px; }
.concept-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; border-bottom: 2px solid var(--ink); padding-bottom: 6px; }
.concept-head .num { font-family: var(--font-mono); color: var(--accent); font-size: 1rem; }
.concept-head .badge { font-family: var(--font-mono); font-size: 0.7rem; letter-spacing: 0.06em; border: 1px solid var(--accent); color: var(--accent); border-radius: 4px; padding: 0 6px; }
.block { border-radius: 8px; padding: 14px 16px; min-width: 0; }
.block-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.kind { font-family: var(--font-mono); font-size: 0.72rem; letter-spacing: 0.08em; font-weight: 500; }
.block-title { font-weight: 700; }
.tag { font-size: 0.72rem; border-radius: 999px; padding: 0 8px; background: var(--tint); color: var(--muted); }
.b-definition { background: var(--def-bg); border-left: 4px solid var(--def); } .b-definition .kind { color: var(--def); }
.b-theorem { background: var(--thm-bg); border-left: 4px solid var(--thm); } .b-theorem .kind { color: var(--thm); }
.b-proof { background: var(--paper); border: 1px solid var(--rule); margin-left: 12px; } .b-proof .kind { color: var(--thm); }
.b-proof .qed { float: right; color: var(--thm); }
.b-recipe { background: var(--rec-bg); border-left: 4px solid var(--rec); } .b-recipe .kind { color: var(--rec); }
.b-explanation { background: transparent; padding-inline: 0; } .b-explanation .kind { color: var(--muted); }
.b-example, .b-figure { background: var(--paper); border: 1px solid var(--rule); } .b-example .kind, .b-figure .kind { color: var(--ink); }
.b-professor { background: var(--prof-bg); border: 1px solid var(--prof); } .b-professor .kind { color: var(--prof); }
.b-warning { background: var(--warn-bg); border-left: 4px solid var(--warn); } .b-warning .kind { color: var(--warn); }
.b-intuition, .b-why, .b-connection { background: var(--tint); font-size: 0.95rem; } .b-intuition .kind, .b-why .kind, .b-connection .kind { color: var(--muted); }
.support-label { font-size: 0.78rem; color: var(--muted); font-family: var(--font-mono); letter-spacing: 0.06em; margin-top: 6px; }
.recon { margin-top: 12px; border-top: 1px dashed var(--prof); padding-top: 10px; }
.recon .recon-label { font-size: 0.78rem; color: var(--prof); font-weight: 700; }
.recon .recon-note { font-size: 0.75rem; color: var(--muted); }
.recon .speech { margin-top: 4px; font-family: var(--font-display); font-weight: 600; line-height: 1.8; }
.cite { font-size: 0.78rem; color: var(--muted); margin-top: 8px; }
.display-math { overflow-x: auto; overflow-y: hidden; padding: 2px 0; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; font-size: 0.92rem; }
th, td { border: 1px solid var(--rule); padding: 4px 10px; text-align: left; }
th { background: var(--tint); }
/* figures */
.fig { margin-top: 10px; }
.fig-title { font-weight: 700; font-size: 0.92rem; margin-bottom: 6px; }
.fig-caption { font-size: 0.85rem; color: var(--muted); margin-top: 6px; }
.rr { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 8px; overflow-x: auto; }
.rr-step { display: grid; gap: 4px; justify-items: start; }
.rr-label { font-size: 0.75rem; color: var(--muted); font-family: var(--font-mono); }
.rr-arrow { font-size: 1.3rem; color: var(--muted); padding-inline: 2px; }
.mat { display: grid; align-items: center; column-gap: 0; position: relative; padding-inline: 8px; font-variant-numeric: tabular-nums; }
.mat::before, .mat::after { content: ""; position: absolute; top: 2px; bottom: 2px; width: 7px; border: 1.5px solid var(--ink); }
.mat::before { left: 0; border-right: none; }
.mat::after { right: 0; border-left: none; }
.cell { min-width: 2.1em; height: 2.1em; display: grid; place-items: center; padding-inline: 4px; border-radius: 50%; font-size: 0.95rem; }
.cell.pivot { background: var(--pivot); color: var(--pivot-ink); font-weight: 700; }
.cell.eliminate { background: var(--elim); border-radius: 6px; }
.cell.free { background: var(--free); border-radius: 0; }
.cell.focus { outline: 2px solid var(--c2); border-radius: 6px; }
.cell.aug { border-left: 1.5px solid var(--ink); border-radius: 0; }
.ops { display: grid; align-items: center; font-size: 0.8rem; color: var(--accent); }
.op { height: 2.1em; display: flex; align-items: center; white-space: nowrap; padding-left: 6px; }
.mat-wrap { display: flex; align-items: stretch; }
.plot { max-width: 100%; height: auto; display: block; }
.plot text { fill: var(--muted); font-size: 11px; font-family: var(--font-body); }
.plot .lbl { font-size: 12px; font-weight: 600; }
.flowchart { position: relative; display: grid; gap: 40px; padding: 6px 0; }
.flow-row { display: flex; justify-content: center; gap: 48px; flex-wrap: wrap; position: relative; z-index: 1; }
.flow-node { background: var(--paper); border: 1.5px solid var(--ink); border-radius: 8px; padding: 6px 12px; font-size: 0.9rem; max-width: 18rem; text-align: center; }
.flow-svg { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; overflow: visible; }
.flow-svg line { stroke: var(--muted); stroke-width: 1.5; }
.flow-svg text { fill: var(--accent); font-size: 12px; font-weight: 700; }
.legend-dot { display: inline-block; width: 0.9em; height: 0.9em; border-radius: 50%; vertical-align: -0.1em; margin-right: 4px; }
/* exam */
.exam { display: grid; gap: 14px; }
.tf-list { display: grid; gap: 8px; }
.q { background: var(--paper); border: 1px solid var(--rule); border-radius: 8px; padding: 12px 14px; }
.q-head { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 6px; }
.q-id { font-family: var(--font-mono); font-weight: 500; color: var(--accent); }
.diff { font-size: 0.72rem; border-radius: 4px; padding: 0 6px; border: 1px solid currentColor; }
.diff-basic { color: var(--rec); } .diff-standard { color: var(--accent); } .diff-advanced { color: var(--warn); }
details { margin-top: 8px; }
summary { cursor: pointer; color: var(--accent); font-size: 0.88rem; font-weight: 600; }
details > div { margin-top: 8px; padding: 10px 12px; background: var(--tint); border-radius: 6px; }
.why-likely { font-size: 0.82rem; color: var(--muted); margin-top: 6px; }
.banner { background: var(--warn-bg); border: 1px solid var(--warn); border-radius: 8px; padding: 12px 14px; }
@media (max-width: 480px) { body { font-size: 15px; } h1 { font-size: 1.55rem; } .b-proof { margin-left: 0; } }
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto; } }
"""

FLOW_JS = """
function drawFlows(){document.querySelectorAll('.flowchart').forEach(function(fc){
  var svg=fc.querySelector('.flow-svg'); if(!svg) return;
  var edges=JSON.parse(fc.getAttribute('data-edges')||'[]'); var box=fc.getBoundingClientRect();
  var ns='http://www.w3.org/2000/svg'; while(svg.firstChild) svg.removeChild(svg.firstChild);
  var marker=document.createElementNS(ns,'defs'); marker.innerHTML='<marker id="ah'+fc.id+'" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" style="fill:var(--muted)"/></marker>'; svg.appendChild(marker);
  edges.forEach(function(e){
    var a=fc.querySelector('[data-node="'+e.from+'"]'), b=fc.querySelector('[data-node="'+e.to+'"]'); if(!a||!b) return;
    var ra=a.getBoundingClientRect(), rb=b.getBoundingClientRect();
    var x1=ra.left+ra.width/2-box.left, y1=ra.bottom-box.top, x2=rb.left+rb.width/2-box.left, y2=rb.top-box.top;
    if (rb.top < ra.bottom) { y1=ra.top+ra.height/2-box.top; y2=rb.top+rb.height/2-box.top; x1 = x2>x1 ? ra.right-box.left : ra.left-box.left; x2 = x2>x1 ? rb.left-box.left : rb.right-box.left; }
    var l=document.createElementNS(ns,'line'); l.setAttribute('x1',x1); l.setAttribute('y1',y1); l.setAttribute('x2',x2); l.setAttribute('y2',y2-2);
    l.setAttribute('marker-end','url(#ah'+fc.id+')'); svg.appendChild(l);
    if(e.label){var t=document.createElementNS(ns,'text'); var mx=x1+(x2-x1)*0.35, my=y1+(y2-y1)*0.35;
      var dx=x2-x1; t.setAttribute('text-anchor', dx>4?'start':(dx<-4?'end':'start'));
      t.setAttribute('x', mx+(dx<-4?-8:8)); t.setAttribute('y', my+4); t.textContent=e.label; svg.appendChild(t);}
  });
});}
window.addEventListener('load', drawFlows); window.addEventListener('resize', drawFlows);
"""


def _e(text: str) -> str:
    return html.escape(text, quote=True)


def _math_cell(value: str) -> str:
    """Render a matrix entry: integers plain, fractions and symbols through MathJax."""
    v = value.strip().replace("−", "-")
    if v in ("", "*"):
        return "∗" if v == "*" else ""
    try:
        frac = Fraction(v)
        if frac.denominator == 1:
            return _e(str(frac.numerator).replace("-", "−"))
        sign = "-" if frac < 0 else ""
        return _e(f"${sign}\\frac{{{abs(frac.numerator)}}}{{{frac.denominator}}}$")
    except (ValueError, ZeroDivisionError):
        pass
    if "\\" in v or "_" in v or "^" in v:
        return _e(f"${v}$")
    return _e(v)


def _op_label(op: str, row: int) -> str:
    op = op.strip()
    if not op:
        return ""
    if "\\leftarrow" in op or "\\leftrightarrow" in op or "\\to" in op:
        return _e(f"${op}$")
    return _e(f"$R_{{{row + 1}}} \\leftarrow {op}$")


def _matrix_html(step: dict) -> str:
    rows = step["matrix"]
    width = len(rows[0]) if rows else 0
    roles = {(h["row"], h["col"]): h["role"] for h in step["highlight"]}
    free_cols = {h["col"] for h in step["highlight"] if h["role"] == "free"}
    aug = step["augmented_col"]
    cells = []
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            classes = ["cell"]
            role = roles.get((r, c))
            if role and role != "free":
                classes.append(role)
            if c in free_cols:
                classes.append("free")
            if aug is not None and c == aug:
                classes.append("aug")
            cells.append(f'<div class="{" ".join(classes)}">{_math_cell(value)}</div>')
    grid = f'<div class="mat" style="grid-template-columns: repeat({width}, auto)">{"".join(cells)}</div>'
    ops = step["row_ops"]
    if any(o.strip() for o in ops):
        op_cells = "".join(f'<div class="op">{_op_label(op, i)}</div>' for i, op in enumerate(ops))
        return f'<div class="mat-wrap">{grid}<div class="ops">{op_cells}</div></div>'
    return f'<div class="mat-wrap">{grid}</div>'


def _lines_svg(figure: dict, fid: str) -> str:
    lines = figure["lines"]
    points = []
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            a1, b1, c1 = lines[i]["a"], lines[i]["b"], lines[i]["c"]
            a2, b2, c2 = lines[j]["a"], lines[j]["b"], lines[j]["c"]
            det = a1 * b2 - a2 * b1
            if abs(det) > 1e-12:
                points.append(((c1 * b2 - c2 * b1) / det, (a1 * c2 - a2 * c1) / det))
    extent = max([5.0] + [abs(v) * 1.5 for p in points for v in p])
    for line in lines:
        if line["a"]:
            extent = max(extent, min(abs(line["c"] / line["a"]) * 1.3, 40))
        if line["b"]:
            extent = max(extent, min(abs(line["c"] / line["b"]) * 1.3, 40))
    extent = float(math.ceil(extent))
    size, pad = 320, 24
    scale = (size - 2 * pad) / (2 * extent)

    def sx(x: float) -> float:
        return pad + (x + extent) * scale

    def sy(y: float) -> float:
        return size - pad - (y + extent) * scale

    parts = [
        f'<svg class="plot" viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img" aria-label="{_e(figure["title"] or "직선 그래프")}">',
        f'<defs><clipPath id="{fid}-clip"><rect x="{pad}" y="{pad}" width="{size - 2 * pad}" height="{size - 2 * pad}"/></clipPath></defs>',
    ]
    step = max(1, int(extent // 5))
    for k in range(-int(extent), int(extent) + 1, step):
        parts.append(f'<line x1="{sx(k):.1f}" y1="{sy(-extent):.1f}" x2="{sx(k):.1f}" y2="{sy(extent):.1f}" style="stroke:var(--rule);stroke-width:1"/>')
        parts.append(f'<line x1="{sx(-extent):.1f}" y1="{sy(k):.1f}" x2="{sx(extent):.1f}" y2="{sy(k):.1f}" style="stroke:var(--rule);stroke-width:1"/>')
    parts.append(f'<line x1="{sx(-extent):.1f}" y1="{sy(0):.1f}" x2="{sx(extent):.1f}" y2="{sy(0):.1f}" style="stroke:var(--muted);stroke-width:1.2"/>')
    parts.append(f'<line x1="{sx(0):.1f}" y1="{sy(-extent):.1f}" x2="{sx(0):.1f}" y2="{sy(extent):.1f}" style="stroke:var(--muted);stroke-width:1.2"/>')
    parts.append(f'<text x="{sx(extent) - 10:.1f}" y="{sy(0) - 6:.1f}">x</text><text x="{sx(0) + 6:.1f}" y="{sy(extent) + 12:.1f}">y</text>')
    colors = ["var(--c1)", "var(--c2)", "var(--c3)"]
    seen = []
    for i, line in enumerate(lines):
        a, b, c = line["a"], line["b"], line["c"]
        if b:
            x1, x2 = -extent, extent
            y1, y2 = (c - a * x1) / b, (c - a * x2) / b
        else:
            x1 = x2 = c / a
            y1, y2 = -extent, extent
        norm = math.hypot(a, b)
        key = (round(a / norm, 9), round(b / norm, 9), round(c / norm, 9))
        dashed = "stroke-dasharray:6 5;" if key in seen or (tuple(-k for k in key) in seen) else ""
        seen.append(key)
        color = colors[i % len(colors)]
        parts.append(
            f'<line x1="{sx(x1):.1f}" y1="{sy(y1):.1f}" x2="{sx(x2):.1f}" y2="{sy(y2):.1f}" '
            f'clip-path="url(#{fid}-clip)" style="stroke:{color};stroke-width:2.4;{dashed}"/>'
        )
    for x, y in points:
        parts.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="5" style="fill:var(--ink)"/>')
        label = f"({_fmt(x)}, {_fmt(y)})"
        parts.append(f'<text class="lbl" x="{sx(x) + 8:.1f}" y="{sy(y) - 8:.1f}" style="fill:var(--ink)">{_e(label)}</text>')
    parts.append("</svg>")
    legend = "".join(
        f'<div><span class="legend-dot" style="background:{colors[i % len(colors)]}"></span>{_e(line["label"])}</div>'
        for i, line in enumerate(lines)
    )
    return f'<div style="overflow-x:auto">{"".join(parts)}</div><div class="fig-caption">{legend}</div>'


def _fmt(v: float) -> str:
    frac = Fraction(v).limit_denominator(100)
    return str(frac.numerator) if frac.denominator == 1 else f"{frac.numerator}/{frac.denominator}"


def _flow_html(figure: dict, fid: str) -> str:
    nodes = figure["nodes"]
    edges = figure["edges"]
    order = [n["id"] for n in nodes]
    # Breadth-first layers from the first node; unreachable nodes go to a last layer.
    depth: dict[str, int] = {}
    if order:
        depth[order[0]] = 0
        queue = [order[0]]
        while queue:
            current = queue.pop(0)
            for e in edges:
                if e["from"] == current and e["to"] not in depth:
                    depth[e["to"]] = depth[current] + 1
                    queue.append(e["to"])
    last = max(depth.values(), default=-1) + 1
    for nid in order:
        depth.setdefault(nid, last)
    layers: dict[int, list[dict]] = {}
    for n in nodes:
        layers.setdefault(depth[n["id"]], []).append(n)
    rows = "".join(
        '<div class="flow-row">'
        + "".join(f'<div class="flow-node" data-node="{_e(n["id"])}">{to_html(n["label"])}</div>' for n in layers[d])
        + "</div>"
        for d in sorted(layers)
    )
    data = _e(json.dumps(edges, ensure_ascii=False))
    return f'<div class="flowchart" id="{fid}" data-edges="{data}"><svg class="flow-svg" aria-hidden="true"></svg>{rows}</div>'


def render_figure(figure: dict, fid: str) -> str:
    parts = ['<div class="fig">']
    if figure["title"]:
        parts.append(f'<div class="fig-title">{_e(figure["title"])}</div>')
    kind = figure["kind"]
    if kind in ("row_reduction", "matrix"):
        items = []
        for i, step in enumerate(figure["steps"]):
            if i:
                items.append('<div class="rr-arrow" aria-hidden="true">⟶</div>')
            label = f'<div class="rr-label">{_e(step["label"])}</div>' if step["label"] else ""
            items.append(f'<div class="rr-step">{label}{_matrix_html(step)}</div>')
        parts.append(f'<div class="rr">{"".join(items)}</div>')
    elif kind == "lines_2d":
        parts.append(_lines_svg(figure, fid))
    elif kind == "flow":
        parts.append(_flow_html(figure, fid))
    if figure["caption"]:
        parts.append(f'<div class="fig-caption">{to_html(figure["caption"])}</div>')
    parts.append("</div>")
    return "".join(parts)


def _status_tag(status: str) -> str:
    if status == "observed":
        return ""
    return f'<span class="tag">{STATUS_LABELS_KO[status]}</span>'


def _location(source: dict) -> str:
    if source.get("page") is not None:
        return f"{source['material_id']} p.{source['page']}"
    return source["material_id"]


def render_html(note: dict, concept_map: dict, contexts: list[dict], *, quality_report: dict | None = None) -> str:
    names = {c["id"]: c["name"] for c in concept_map["concepts"]}
    core = set(concept_map["core_concepts"])
    emphasis = {p["id"]: p for ctx in contexts for group in ctx["professor_context"].values() for p in group}
    source_of_chunk = {s["chunk_id"]: s for ctx in contexts for s in ctx["sources"]}
    ctx_by_id = {c["concept"]["id"]: c for c in contexts}
    fig_counter = [0]

    def fig(figure: dict) -> str:
        fig_counter[0] += 1
        return render_figure(figure, f"fig{fig_counter[0]}")

    out = [f"<title>{_e(note['title'])}</title>", f'<link rel="stylesheet" href="{FONTS}">', f"<style>{CSS}</style>"]
    out.append('<main class="page">')

    if quality_report is not None and not quality_report["passed"]:
        errs = "".join(
            f"<li><code>{_e(c['check_id'])}</code> {_e(c['message'])}</li>"
            for c in quality_report["checks"]
            if not c["passed"] and c["severity"] == "error"
        )
        out.append(f'<div class="banner"><strong>검토 필요</strong>: 자동 품질 검사에서 해결되지 않은 문제가 있습니다.<ul>{errs}</ul></div>')

    out.append(
        f'<header class="flow"><div class="eyebrow">공부 노트</div><h1>{_e(note["title"])}</h1>'
        f'<div class="lede flow">{to_html(note["big_picture"])}</div></header>'
    )
    if note["objectives"]:
        items = "".join(f"<li>{_inline(o)}</li>" for o in note["objectives"])
        out.append(f'<section class="panel objectives"><h2>이 절을 마치면 할 수 있어야 하는 것</h2><ul>{items}</ul></section>')
    if note["key_ideas"]:
        items = "".join(f"<li>{_inline(k)}</li>" for k in note["key_ideas"])
        out.append(f'<section class="panel keyideas"><h2>핵심 요약</h2><ol>{items}</ol></section>')

    toc = []
    for i, cid in enumerate(note["concept_order"], start=1):
        if i > 1:
            toc.append('<span class="sep" aria-hidden="true">→</span>')
        cls = ' class="core"' if cid in core else ""
        toc.append(f'<a{cls} href="#c-{_e(cid)}">{i}. {_e(names.get(cid, cid))}</a>')
    out.append(f'<nav class="toc" aria-label="개념 흐름">{"".join(toc)}</nav>')
    out.append(
        '<p class="legend">굵은 테두리는 핵심 개념입니다. 상자의 <span class="tag">추론</span>은 자료에 직접 없지만 흐름상 추론한 내용, '
        '<span class="tag">불확실</span>은 자료만으로 확인이 어려운 내용입니다. 교수님 강조 상자의 "수업 설명 재구성"은 교안 근거로 추정한 설명이며 실제 발언 인용이 아닙니다.</p>'
    )

    for number, entry in enumerate(note["entries"], start=1):
        cid = entry["concept_id"]
        badge = '<span class="badge">핵심</span>' if cid in core else ""
        out.append(f'<section class="concept" id="c-{_e(cid)}">')
        out.append(f'<div class="concept-head"><span class="num">{number}</span><h2>{_e(entry["title"])}</h2>{badge}</div>')
        support_started = False
        for block in entry["blocks"]:
            kind = block["kind"]
            if kind in ("intuition", "why", "connection") and not support_started:
                support_started = True
                out.append('<div class="support-label">이해를 돕는 설명</div>')
            title = f'<span class="block-title">{_e(block["title"])}</span>' if block["title"] else ""
            method = ""
            if kind == "proof" and block["proof_method"]:
                method = f'<span class="tag">{PROOF_METHOD_LABELS[block["proof_method"]]}</span>'
            head = f'<div class="block-head"><span class="kind">{KIND_LABELS[kind]}</span>{title}{method}{_status_tag(block["status"])}</div>'
            body = f'<div class="flow">{to_html(block["body_markdown"])}</div>' if block["body_markdown"].strip() else ""
            if kind == "proof":
                body += '<div class="qed" aria-label="증명 끝">∎</div><div style="clear:both"></div>'
            extra = ""
            if block["figure"] is not None:
                extra += fig(block["figure"])
            if kind == "professor":
                if block["reconstruction"]:
                    extra += (
                        '<div class="recon"><div class="recon-label">수업 설명 재구성 · 추정</div>'
                        '<div class="recon-note">교안의 강조 표시를 근거로 수업에서 했을 법한 설명을 재구성했습니다. 실제 발언 인용이 아닙니다.</div>'
                        f'<div class="speech flow">{to_html(block["reconstruction"])}</div></div>'
                    )
                cites = []
                for ref in block["refs"]:
                    p = emphasis.get(ref)
                    if not p:
                        continue
                    locs = sorted(
                        {_location(source_of_chunk[ev["chunk_id"]]) for ev in p["evidence"] if ev["chunk_id"] in source_of_chunk}
                    )
                    who = "내 필기 기록" if p["attribution"] == "user_reported" else "교안"
                    cites.append(f"{ref} ({who}{': ' + ', '.join(locs) if locs else ''})")
                if cites:
                    extra += f'<div class="cite">근거: {_e("; ".join(cites))}</div>'
            out.append(f'<div class="block b-{kind}">{head}{body}{extra}</div>')
        ctx = ctx_by_id.get(cid)
        if ctx and ctx["sources"]:
            locs = []
            for s in ctx["sources"]:
                loc = _location(s)
                if loc not in locs:
                    locs.append(loc)
            out.append(f'<div class="cite">자료 위치: {_e(", ".join(locs))}</div>')
        out.append("</section>")

    if note["summary"]:
        items = "".join(f"<li>{_inline(s)}</li>" for s in note["summary"])
        out.append(f'<section class="panel keyideas"><h2>핵심 정리</h2><ol>{items}</ol></section>')

    exam = note["exam"]
    if exam["true_false"] or exam["problems"]:
        out.append('<section class="exam" id="exam"><h2>시험 대비</h2>')
        if exam["true_false"]:
            out.append('<h3>개념 확인: 참일까 거짓일까</h3><div class="tf-list">')
            for i, tf in enumerate(exam["true_false"], start=1):
                verdict = "참" if tf["answer"] else "거짓"
                out.append(
                    f'<div class="q"><div class="q-head"><span class="q-id">OX {i}</span></div>'
                    f'<div class="flow">{to_html(tf["statement_markdown"])}</div>'
                    f'<details><summary>정답 보기</summary><div class="flow"><p><strong>{verdict}</strong></p>{to_html(tf["explanation_markdown"])}</div></details></div>'
                )
            out.append("</div>")
        if exam["problems"]:
            out.append("<h3>예상 문제</h3>")
            for p in exam["problems"]:
                figure = fig(p["figure"]) if p["figure"] else ""
                out.append(
                    f'<div class="q"><div class="q-head"><span class="q-id">{_e(p["id"])}</span>'
                    f'<span class="diff diff-{p["difficulty"]}">{DIFFICULTY_LABELS[p["difficulty"]]}</span>'
                    f'<span class="tag">{EXAM_TYPE_LABELS[p["type"]]}</span></div>'
                    f'<div class="flow">{to_html(p["prompt_markdown"])}</div>{figure}'
                    f'<div class="why-likely">출제 근거: {_inline(p["why_likely"])}</div>'
                    f'<details><summary>답과 풀이</summary><div class="flow"><p><strong>답</strong></p>{to_html(p["answer_markdown"])}'
                    f'<p><strong>풀이</strong></p>{to_html(p["solution_markdown"])}</div></details></div>'
                )
        out.append("</section>")

    if note["open_questions"]:
        items = "".join(f"<li><strong>{_inline(q['question'])}</strong> {_inline(q['reason'])}</li>" for q in note["open_questions"])
        out.append(f'<section class="panel"><h2>아직 확인이 필요한 부분</h2><p class="lede">자료만으로는 확인할 수 없었던 부분입니다. 수업 필기와 대조해 보세요.</p><ul>{items}</ul></section>')

    out.append("</main>")
    out.append(
        "<script>window.MathJax={tex:{inlineMath:[['$','$']],displayMath:[['$$','$$']]},"
        "svg:{fontCache:'global'},startup:{pageReady:function(){return MathJax.startup.defaultPageReady().then(function(){if(window.drawFlows)drawFlows();});}}};</script>"
    )
    out.append(f"<script>{FLOW_JS}</script>")
    out.append(f'<script src="{MATHJAX}" async></script>')
    return "\n".join(out) + "\n"


def _inline(text: str) -> str:
    """Single-paragraph markdown without the <p> wrapper."""
    rendered = to_html(text)
    if rendered.startswith("<p>") and rendered.endswith("</p>") and rendered.count("<p>") == 1:
        return rendered[3:-4]
    return rendered
