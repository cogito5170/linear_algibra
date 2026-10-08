"""Epistemic status vocabulary shared by all agents.

observed  : 교안이나 교수님 필기에 실제로 존재한다.
inferred  : 직접 쓰여 있지 않지만 자료의 구조로부터 합리적으로 추론했다.
uncertain : 자료만으로는 판단하기 어렵다.
"""

from __future__ import annotations

STATUSES = ("observed", "inferred", "uncertain")

# Short Korean labels used when rendering notes.
STATUS_LABELS_KO = {
    "observed": "자료",
    "inferred": "추론",
    "uncertain": "불확실",
    "mixed": "자료+추론",
}
