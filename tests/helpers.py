import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "linear_independence"
RECORDED = EXAMPLE / "recorded"


def load(name: str) -> dict:
    """Load a recorded agent output (or 'bundle') from the worked example."""
    path = EXAMPLE / "bundle.json" if name == "bundle" else RECORDED / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def fixtures() -> dict:
    return {
        "bundle": load("bundle"),
        "analysis": load("material_analyst"),
        "concept_map": load("concept_mapper"),
        "lesson": load("intuition_teacher"),
        "note": load("note_editor"),
        "review": load("quality_reviewer"),
    }


def script_from_example(**overrides) -> dict:
    """A ScriptedLLM script that reproduces the worked example, with per-agent overrides."""
    f = fixtures()
    script = {
        "material_analyst": [f["analysis"]],
        "concept_mapper": [f["concept_map"]],
        "intuition_teacher": [f["lesson"]],
        "note_editor": [f["note"]],
        "quality_reviewer": [f["review"]],
    }
    script.update(overrides)
    return copy.deepcopy(script)
