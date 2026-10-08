"""A small Markdown-to-HTML converter that leaves LaTeX untouched.

Supports what study notes use: paragraphs, **bold**, *italic*, `code`,
bullet and numbered lists, block quotes and pipe tables. Math between `$...$`
or `$$...$$` is protected from Markdown processing and HTML-escaped only, so
MathJax receives it exactly as written.
"""

from __future__ import annotations

import html
import re

_MATH = re.compile(r"\$\$.+?\$\$|\$(?:\\\$|[^$\n])+?\$", re.DOTALL)
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
_CODE = re.compile(r"`([^`]+)`")
_OL = re.compile(r"^\s*\d+[.)]\s+")
_UL = re.compile(r"^\s*[-*•]\s+")


def _protect(text: str) -> tuple[str, list[str]]:
    stash: list[str] = []

    def keep(match: re.Match) -> str:
        stash.append(html.escape(match.group(0), quote=False))
        return f"\x00{len(stash) - 1}\x00"

    return _MATH.sub(keep, text), stash


def _restore(text: str, stash: list[str]) -> str:
    return re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], text)


def _inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = _CODE.sub(r"<code>\1</code>", text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)
    return text


def _table(lines: list[str]) -> str:
    def cells(line: str) -> list[str]:
        return [c.strip() for c in line.strip().strip("|").split("|")]

    head = cells(lines[0])
    body = [cells(l) for l in lines[2:]]
    out = ['<div class="table-wrap"><table><thead><tr>']
    out += [f"<th>{_inline(c)}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for row in body:
        out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def _list(lines: list[str], ordered: bool) -> str:
    marker = _OL if ordered else _UL
    items: list[str] = []
    for line in lines:
        if marker.match(line):
            items.append(marker.sub("", line, count=1))
        elif items:
            items[-1] += " " + line.strip()
    tag = "ol" if ordered else "ul"
    start = ""
    if ordered:
        first = int(re.match(r"\s*(\d+)", lines[0]).group(1))
        if first != 1:
            start = f' start="{first}"'
    return f"<{tag}{start}>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + f"</{tag}>"


def to_html(markdown: str) -> str:
    """Convert a Markdown fragment to HTML."""
    protected, stash = _protect(markdown.strip())
    blocks = re.split(r"\n\s*\n", protected) if protected else []
    out: list[str] = []
    for block in blocks:
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        if len(lines) >= 2 and lines[0].lstrip().startswith("|") and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[1]):
            out.append(_table(lines))
        elif all(_UL.match(l) or not _OL.match(l) and l.startswith((" ", "\t")) for l in lines) and _UL.match(lines[0]):
            out.append(_list(lines, ordered=False))
        elif _OL.match(lines[0]) and all(_OL.match(l) or l.startswith((" ", "\t")) for l in lines):
            out.append(_list(lines, ordered=True))
        elif all(l.lstrip().startswith(">") for l in lines):
            inner = "\n".join(re.sub(r"^\s*>\s?", "", l) for l in lines)
            out.append(f"<blockquote>{_inline(inner)}</blockquote>")
        elif len(lines) == 1 and re.fullmatch(r"\x00\d+\x00", lines[0].strip()):
            out.append(f'<div class="display-math">{lines[0].strip()}</div>')
        else:
            out.append("<p>" + "<br>".join(_inline(l.strip()) for l in lines) + "</p>")
    return _restore("".join(out), stash)
