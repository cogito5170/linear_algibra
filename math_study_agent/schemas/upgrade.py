"""Lossless upgrades from v2 to v3 payloads.

v3 is a superset of v2: it adds the domain, board reconstructions and the
schematic/plot figure fields. A v2 lesson or note becomes a v3 one by filling
those with empty values, so old runs can still be rendered and exported.
"""

from __future__ import annotations

import copy


def figure_v2_to_v3(figure: dict | None) -> dict | None:
    if figure is None or "elements" in figure:
        return figure
    return {**figure, "elements": [], "x_label": "", "y_label": "", "series": [], "marks": []}


def lesson_v2_to_v3(lesson: dict, domain: str = "math") -> dict:
    if lesson["schema"] != "math_intuition_lesson/2":
        return lesson
    out = copy.deepcopy(lesson)
    out["schema"] = "math_intuition_lesson/3"
    out = {"schema": out.pop("schema"), "domain": domain, **out}
    for item in out["lessons"]:
        item["figures"] = [figure_v2_to_v3(f) for f in item["figures"]]
        item["board_notes"] = []
    return out


def note_v2_to_v3(note: dict, domain: str = "math") -> dict:
    if note["schema"] != "math_study_note/2":
        return note
    out = copy.deepcopy(note)
    out.pop("schema")
    out = {"schema": "math_study_note/3", "domain": domain, **out}
    for entry in out["entries"]:
        for block in entry["blocks"]:
            block["figure"] = figure_v2_to_v3(block["figure"])
            block["basis"] = None
    for problem in out["exam"]["problems"]:
        problem["figure"] = figure_v2_to_v3(problem["figure"])
    return out
