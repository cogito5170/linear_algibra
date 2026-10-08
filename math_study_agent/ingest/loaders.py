"""Turn lecture materials into a `math_material_bundle/1`.

Every piece of text gets a stable `chunk_id` together with its material,
page and section. Agents cite chunks by id and quote them verbatim, which lets
the orchestrator verify every "observed" claim against the original text.

Supported inputs: `.md`, `.txt` (any UTF-8 text) and `.pdf` (needs `pdfplumber`
or `pypdf`). Handwritten notes must already be converted to text.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from ..errors import MathStudyError
from ..schemas import assert_valid

DEFAULT_AUTHOR = {
    "lecture_slides": "professor",
    "lecture_pdf": "professor",
    "professor_notes": "professor",
    "handwritten_notes": "professor",
    "user_notes": "user",
}

MAX_CHUNK_CHARS = 900

_PAGE_MARKERS = [
    re.compile(r"^\s*<!--\s*(?:page|slide)\s*:?\s*(\d+)\s*-->\s*$", re.IGNORECASE),
    re.compile(r"^\s*-{2,}\s*(?:page|slide|p\.?|페이지|슬라이드)\s*(\d+)\s*-{2,}\s*$", re.IGNORECASE),
    re.compile(r"^\s*\[(?:page|slide|p\.?|페이지|슬라이드)\s*(\d+)\]\s*$", re.IGNORECASE),
]
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*\S)\s*$")


class IngestError(MathStudyError):
    pass


def _page_marker(line: str) -> int | None:
    for pattern in _PAGE_MARKERS:
        match = pattern.match(line)
        if match:
            return int(match.group(1))
    return None


def _paragraphs(lines: list[str]) -> list[str]:
    paragraphs, current = [], []
    for line in lines:
        if line.strip():
            current.append(line.rstrip())
        elif current:
            paragraphs.append("\n".join(current))
            current = []
    if current:
        paragraphs.append("\n".join(current))
    return paragraphs


def _pack(paragraphs: list[str], limit: int = MAX_CHUNK_CHARS) -> list[str]:
    """Merge short paragraphs so chunks are neither tiny nor huge."""
    packed, current = [], ""
    for para in paragraphs:
        if current and len(current) + len(para) + 2 > limit:
            packed.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        packed.append(current)
    return packed


def chunk_text(text: str, *, start_page: int | None = None, default_section: str = "") -> list[dict]:
    """Split text into chunks of {page, section, text}, following headings and page markers."""
    blocks: list[tuple[int | None, str, list[str]]] = []
    page, section, lines = start_page, default_section, []

    def flush():
        if any(line.strip() for line in lines):
            blocks.append((page, section, list(lines)))
        lines.clear()

    for line in text.splitlines():
        marker = _page_marker(line)
        if marker is not None:
            flush()
            page = marker
            continue
        heading = _HEADING.match(line)
        if heading:
            flush()
            section = heading.group(2).strip()
            lines.append(line)
            continue
        lines.append(line)
    flush()

    chunks = []
    for blk_page, blk_section, blk_lines in blocks:
        for piece in _pack(_paragraphs(blk_lines)):
            chunks.append({"page": blk_page, "section": blk_section, "text": piece})
    return chunks


def _read_pdf_pages(path: Path) -> list[str]:
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            return [(page.extract_text() or "") for page in pdf.pages]
    except ImportError:
        pass
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise IngestError("PDF input needs 'pdfplumber' or 'pypdf': pip install 'math-study-agent[pdf]'") from exc
    return [(page.extract_text() or "") for page in PdfReader(str(path)).pages]


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:80]
    return ""


def load_source(
    path: str | Path,
    kind: str,
    *,
    material_id: str | None = None,
    author: str | None = None,
    title: str | None = None,
) -> dict:
    """Load one file as a source entry of the bundle."""
    path = Path(path)
    if not path.is_file():
        raise IngestError(f"input file not found: {path}")
    if kind not in DEFAULT_AUTHOR:
        raise IngestError(f"unknown source kind {kind!r}; expected one of {sorted(DEFAULT_AUTHOR)}")
    material_id = material_id or re.sub(r"[^A-Za-z0-9_-]+", "_", path.stem) or "material"

    if path.suffix.lower() == ".pdf":
        raw_chunks = []
        for number, page_text in enumerate(_read_pdf_pages(path), start=1):
            raw_chunks.extend(chunk_text(page_text, start_page=number, default_section=_first_line(page_text)))
    else:
        raw_chunks = chunk_text(path.read_text(encoding="utf-8"))

    if not raw_chunks:
        raise IngestError(f"no text could be extracted from {path} (scanned PDF? OCR is not supported yet)")

    chunks = [
        {"chunk_id": f"{material_id}#{i:03d}", "page": c["page"], "section": c["section"], "text": c["text"]}
        for i, c in enumerate(raw_chunks, start=1)
    ]
    return {
        "material_id": material_id,
        "kind": kind,
        "author": author or DEFAULT_AUTHOR[kind],
        "title": title or path.name,
        "chunks": chunks,
    }


def build_bundle(sources: Iterable[dict], *, title: str = "", bundle_id: str = "lecture") -> dict:
    sources = list(sources)
    ids = [s["material_id"] for s in sources]
    duplicates = {m for m in ids if ids.count(m) > 1}
    if duplicates:
        raise IngestError(f"duplicate material ids: {sorted(duplicates)}")
    bundle = {"schema": "math_material_bundle/1", "bundle_id": bundle_id, "title": title, "sources": sources}
    assert_valid(bundle, context="material bundle")
    return bundle


def chunk_index(bundle: dict) -> dict[str, dict]:
    """chunk_id -> {chunk fields + material_id, kind, author}."""
    index = {}
    for source in bundle["sources"]:
        for chunk in source["chunks"]:
            index[chunk["chunk_id"]] = {
                **chunk,
                "material_id": source["material_id"],
                "kind": source["kind"],
                "author": source["author"],
            }
    return index
