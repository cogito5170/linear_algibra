"""Default reader profile (section 11, Difficulty Policy)."""

from __future__ import annotations

import copy

DEFAULT_STYLE_PROFILE = {
    "schema": "math_style_profile/1",
    "language": "ko",
    "conceptual_understanding": "HIGH",
    "mathematical_formalism": "MEDIUM",
    "proof_detail": "LOW_MEDIUM",
    "terminology_complexity": "LOW",
    "intuition": "HIGH",
    "preferences": [
        "직관적",
        "conceptual",
        "논리적",
        "이해하기 쉬운 용어",
        "soft한 설명",
        "수식보다 개념을 먼저",
        "개념과 개념 사이의 관계가 명확함",
        "왜 이것을 배우는가가 설명됨",
        "soft but logically correct > hard but complete",
    ],
    "avoid": [
        "불필요하게 어려운 용어",
        "논문 같은 formal한 문체",
        "수식만 나열",
        "정의만 나열",
        "교안의 단순 복사",
        "불필요하게 긴 증명",
        "의미 없는 비유",
        "과도한 섹션 분할",
        "모든 내용을 동일한 중요도로 설명",
    ],
}


def default_style_profile() -> dict:
    return copy.deepcopy(DEFAULT_STYLE_PROFILE)
