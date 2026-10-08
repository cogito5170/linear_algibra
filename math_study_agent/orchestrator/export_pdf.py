"""Export one or more finished notes as a single print-ready PDF.

The web page typesets math with MathJax from a CDN. For printing, the math
is converted ahead of time to MathML with pandoc, which browsers render
natively, so the PDF can be produced offline. Headless Chromium prints it.

    math-study pdf runs/1.1-1.2 runs/1.3-1.5 --out notes.pdf
"""

from __future__ import annotations

import glob
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..errors import MathStudyError
from .render_html import CSS, FLOW_JS, render_main

_MATH_IN_HTML = re.compile(r"\$\$(.+?)\$\$|\$((?:\\\$|[^$<>\n])+?)\$", re.DOTALL)
_ARRAY_SPEC = re.compile(r"\\begin\{array\}\{([^}]*)\}")
# Without an OpenType MATH font Chromium cannot stretch delimiters, so matrix brackets
# are drawn with CSS on the table instead (square brackets get corner ticks).
_DELIMITED_TABLE = re.compile(
    r'<mo stretchy="true" form="prefix">([\[(∣|‖])</mo>(<mtable\b)(.*?</mtable>)<mo stretchy="true" form="postfix">[\])∣|‖]</mo>',
    re.DOTALL,
)
_DELIM_CLASS = {"[": "d-bracket", "(": "d-paren", "∣": "d-vbar", "|": "d-vbar", "‖": "d-dbar"}

PRINT_CSS = """
/* Print: fixed A4 text width so the flowchart connectors drawn on load stay aligned. */
:root { color-scheme: light; }
@page { size: A4; margin: 16mm 14mm 18mm; @bottom-center { content: counter(page); font-size: 9pt; color: #334155; } }
html, body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-size: 10.5pt; line-height: 1.65; background: #ffffff; }
body, .page { --font-body: "IBM Plex Sans KR", "Noto Sans KR", "Noto Sans CJK KR", "Apple SD Gothic Neo", "Malgun Gothic", "WenQuanYi Zen Hei", sans-serif;
  --font-display: "Noto Serif KR", "Noto Sans CJK KR", "Apple SD Gothic Neo", "Malgun Gothic", "WenQuanYi Zen Hei", serif; }
.page { width: 182mm; max-width: none; padding-inline: 0; padding-block: 0; gap: 16px; }
.lecture { break-before: page; }
.cover { min-height: 240mm; display: grid; align-content: center; gap: 18px; }
.cover h1 { font-size: 26pt; }
.cover ol { font-size: 12pt; line-height: 2; }
/* Small boxes stay whole; long ones (examples, proofs, professor notes) may break between lines. */
.b-definition, .b-theorem, .b-warning, .b-intuition, .b-why, .b-connection, .b-recipe,
.q, .panel, .rr-row, .flowchart, .fig-grid .block, table, .mat-wrap { break-inside: avoid; }
h1, h2, h3, .concept-head, .block-head, .fig-title, .rr-label, .support-label { break-after: avoid; }
.fig-grid { grid-template-columns: repeat(3, 1fr); }
.fig-grid .plot { width: 100%; }
mtable.d-bracket, mtable.d-vbar, mtable.d-paren, mtable.d-dbar { border-left: 1.3px solid currentColor; border-right: 1.3px solid currentColor; padding: 1px 5px; margin: 0 2px; }
mtable.d-bracket { background:
  linear-gradient(currentColor, currentColor) left top / 5px 1.3px no-repeat,
  linear-gradient(currentColor, currentColor) left bottom / 5px 1.3px no-repeat,
  linear-gradient(currentColor, currentColor) right top / 5px 1.3px no-repeat,
  linear-gradient(currentColor, currentColor) right bottom / 5px 1.3px no-repeat; }
mtable.d-paren { border-radius: 9px / 50%; border-top: 0; border-bottom: 0; }
mtable.d-dbar { border-left-style: double; border-right-style: double; border-left-width: 3.5px; border-right-width: 3.5px; }
details > summary { list-style: none; color: #1d4ed8; }
details > summary::-webkit-details-marker { display: none; }
.toc a { border-color: #cbd5e1; }
math { font-size: 1.08em; }
math[display="block"] { margin: 6px 0; }
.math-raw { font-family: ui-monospace, monospace; font-size: 0.85em; background: #eef4ff; }
"""


def _find_pandoc() -> str:
    path = shutil.which("pandoc")
    if not path:
        raise MathStudyError("PDF export needs pandoc (math → MathML). Install pandoc and retry.")
    return path


def find_chromium() -> str:
    """Locate a Chromium/Chrome binary: $CHROME_PATH, Playwright's bundled browser, or the PATH."""
    candidates = [os.environ.get("CHROME_PATH", "")]
    for root in (os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""), "/opt/pw-browsers", str(Path.home() / ".cache/ms-playwright")):
        if root:
            candidates += sorted(glob.glob(f"{root}/chromium-*/chrome-linux/chrome"), reverse=True)
    candidates += [shutil.which(n) or "" for n in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")]
    for c in candidates:
        if c and os.access(c, os.X_OK):
            return c
    raise MathStudyError("PDF export needs Chromium or Chrome. Set CHROME_PATH to its binary.")


def _add_array_bars(tex: str, mathml: str) -> str:
    """pandoc drops `|` in array column specs; draw it as a cell border instead."""
    spec = _ARRAY_SPEC.search(tex)
    if not spec or "|" not in spec.group(1):
        return mathml
    letters = 0
    bars = set()
    for ch in spec.group(1):
        if ch == "|":
            bars.add(letters)
        elif ch in "lcr":
            letters += 1

    def fix_row(row: re.Match) -> str:
        count = [0]

        def fix_cell(cell: re.Match) -> str:
            index = count[0]
            count[0] += 1
            if index in bars and index > 0:
                tag = cell.group(0)
                if 'style="' in tag:
                    return tag.replace('style="', 'style="border-left: 1.2px solid currentColor; padding-left: 0.4em; ', 1)
                return tag[:-1] + ' style="border-left: 1.2px solid currentColor; padding-left: 0.4em">'
            return cell.group(0)

        return re.sub(r"<mtd\b[^>]*>", fix_cell, row.group(0))

    return re.sub(r"<mtr\b.*?</mtr>", fix_row, mathml, flags=re.DOTALL)


def tex_to_mathml(segments: list[tuple[str, bool]]) -> list[str | None]:
    """Convert (tex, display) pairs to MathML in one pandoc call. None where conversion failed."""
    if not segments:
        return []
    pandoc = _find_pandoc()
    parts = []
    for i, (tex, display) in enumerate(segments):
        body = f"\\[{tex}\\]" if display else f"\\({tex}\\)"
        parts.append(f"MATHSEP{i}ZZ\n\n{body}\n\n")
    result = subprocess.run(
        [pandoc, "-f", "latex", "-t", "html", "--mathml"],
        input="".join(parts),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise MathStudyError(f"pandoc failed: {result.stderr.strip()[:500]}")
    out: list[str | None] = [None] * len(segments)
    pieces = re.split(r"MATHSEP(\d+)ZZ", result.stdout)
    for idx in range(1, len(pieces), 2):
        i = int(pieces[idx])
        chunk = pieces[idx + 1]
        match = re.search(r"<math\b.*?</math>", chunk, re.DOTALL)
        if match:
            mathml = re.sub(r"<annotation\b.*?</annotation>", "", match.group(0), flags=re.DOTALL)
            mathml = _DELIMITED_TABLE.sub(
                lambda m: f'{m.group(2)} class="{_DELIM_CLASS[m.group(1)]}"{m.group(3)}', mathml
            )
            out[i] = _add_array_bars(segments[i][0], mathml)
    return out


def math_to_mathml(page: str) -> tuple[str, int]:
    """Replace $...$ / $$...$$ in rendered HTML by MathML. Returns the page and the number of failures."""
    found = []
    for m in _MATH_IN_HTML.finditer(page):
        display = m.group(1) is not None
        tex = html.unescape(m.group(1) if display else m.group(2))
        found.append((m, tex, display))
    converted = tex_to_mathml([(tex, display) for _, tex, display in found])
    failures = 0
    pieces, last = [], 0
    for (m, tex, display), mathml in zip(found, converted):
        pieces.append(page[last:m.start()])
        if mathml:
            pieces.append(mathml)
        else:
            failures += 1
            pieces.append(f'<code class="math-raw">{html.escape(tex)}</code>')
        last = m.end()
    pieces.append(page[last:])
    return "".join(pieces), failures


def load_run(run_dir: str | Path) -> dict:
    run_dir = Path(run_dir)

    def read(name: str):
        path = run_dir / f"{name}.json"
        if not path.is_file():
            raise MathStudyError(f"{path} not found; run the pipeline first")
        return json.loads(path.read_text(encoding="utf-8"))

    return {
        "note": read("note"),
        "concept_map": read("concept_map"),
        "contexts": read("learning_contexts"),
        "quality_report": read("quality_report"),
    }


def print_document(runs: list[dict], *, title: str = "공부 노트") -> tuple[str, int]:
    """One HTML document with a cover page and every note, math converted to MathML."""
    items = "".join(f"<li>{html.escape(r['note']['title'])}</li>" for r in runs)
    body = [
        '<main class="page cover"><div class="eyebrow">공부 노트</div>'
        f"<h1>{html.escape(title)}</h1><ol>{items}</ol>"
        '<p class="legend">상자의 <strong>추론</strong>은 자료에 직접 없지만 흐름상 추론한 내용, <strong>불확실</strong>은 자료만으로 확인이 어려운 내용입니다. '
        '"수업 설명 재구성"은 교안 근거로 추정한 설명이며 실제 발언 인용이 아닙니다.</p></main>'
    ]
    for i, run in enumerate(runs, start=1):
        main = render_main(
            run["note"], run["concept_map"], run["contexts"], quality_report=run["quality_report"],
            prefix=f"l{i}-", eyebrow=f"{i}강",
        )
        body.append(f'<div class="lecture">{main}</div>')
    content = "\n".join(body).replace("<details>", "<details open>")
    content, failures = math_to_mathml(content)
    doc = (
        "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(title)}</title><style>{CSS}{PRINT_CSS}</style></head><body>"
        f"{content}<script>{FLOW_JS}</script></body></html>"
    )
    return doc, failures


def export_pdf(run_dirs: list[str | Path], out_pdf: str | Path, *, title: str = "공부 노트",
               keep_html: str | Path | None = None) -> dict:
    runs = [load_run(d) for d in run_dirs]
    doc, failures = print_document(runs, title=title)
    out_pdf = Path(out_pdf)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(keep_html) if keep_html else Path(tmp) / "print.html"
        html_path.write_text(doc, encoding="utf-8")
        chrome = find_chromium()
        result = subprocess.run(
            [chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
             "--run-all-compositor-stages-before-draw", "--virtual-time-budget=8000",
             f"--print-to-pdf={out_pdf.resolve()}", html_path.resolve().as_uri()],
            capture_output=True, text=True, timeout=300, check=False,
        )
        if result.returncode != 0 or not out_pdf.is_file():
            raise MathStudyError(f"Chromium could not print the PDF: {result.stderr.strip()[-500:]}")
    return {"pdf": str(out_pdf), "notes": len(runs), "math_failures": failures}
