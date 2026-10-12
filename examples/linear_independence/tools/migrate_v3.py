"""Upgrade the recorded v2 outputs of this example to v3 (math domain).

    python3 examples/linear_independence/tools/migrate_v3.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from math_study_agent.schemas import assert_valid  # noqa: E402
from math_study_agent.schemas.upgrade import lesson_v2_to_v3, note_v2_to_v3  # noqa: E402

RECORDED = Path(__file__).resolve().parents[1] / "recorded"


def main() -> None:
    for name, upgrade in (("intuition_teacher", lesson_v2_to_v3), ("note_editor", note_v2_to_v3)):
        path = RECORDED / f"{name}.json"
        data = upgrade(json.loads(path.read_text(encoding="utf-8")))
        assert_valid(data, context=name)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{path.name}: {data['schema']}")


if __name__ == "__main__":
    main()
