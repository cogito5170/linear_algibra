"""Checks for figure data (`figure_schema`) shared by agents and the renderer.

Figures are drawn from numbers, so a malformed figure is a content error,
not a drawing glitch: it is rejected before it reaches the note.
"""

from __future__ import annotations


def figure_issues(figure: dict, where: str) -> list[str]:
    issues: list[str] = []
    kind = figure["kind"]
    if kind in ("row_reduction", "matrix"):
        steps = figure["steps"]
        if not steps:
            issues.append(f"{where}: {kind} figure needs at least one step")
        if kind == "matrix" and len(steps) > 1:
            issues.append(f"{where}: a matrix figure has exactly one step")
        if kind == "row_reduction" and len(steps) < 2:
            issues.append(f"{where}: a row_reduction figure needs at least two steps")
        for i, step in enumerate(steps):
            at = f"{where}.steps[{i}]"
            rows = step["matrix"]
            if not rows or not rows[0]:
                issues.append(f"{at}: empty matrix")
                continue
            width = len(rows[0])
            if any(len(r) != width for r in rows):
                issues.append(f"{at}: rows have different lengths {[len(r) for r in rows]}")
            aug = step["augmented_col"]
            if aug is not None and not 0 < aug < width:
                issues.append(f"{at}: augmented_col {aug} must be between 1 and {width - 1}")
            if step["row_ops"] and len(step["row_ops"]) != len(rows):
                issues.append(f"{at}: row_ops must be empty or have one entry per row ({len(rows)})")
            if i == 0 and any(op.strip() for op in step["row_ops"]):
                issues.append(f"{at}: the first step cannot have row operations")
            for h in step["highlight"]:
                if h["row"] >= len(rows) or h["col"] >= width:
                    issues.append(f"{at}: highlight ({h['row']}, {h['col']}) is outside the {len(rows)}x{width} matrix")
    elif kind == "lines_2d":
        if not figure["lines"]:
            issues.append(f"{where}: lines_2d figure needs at least one line")
        for line in figure["lines"]:
            if line["a"] == 0 and line["b"] == 0:
                issues.append(f"{where}: line '{line['label']}' has a = b = 0")
    elif kind == "flow":
        ids = [n["id"] for n in figure["nodes"]]
        if not ids:
            issues.append(f"{where}: flow figure needs nodes")
        if len(set(ids)) != len(ids):
            issues.append(f"{where}: duplicate flow node ids")
        for e in figure["edges"]:
            if e["from"] not in ids or e["to"] not in ids:
                issues.append(f"{where}: edge {e['from']}->{e['to']} references an unknown node")
    return issues
