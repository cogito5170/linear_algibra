"""Subject domains.

The pipeline, contracts and epistemic rules are the same for every subject.
A domain adds only what is subject-specific: an extra prompt with its style
and notation rules, and the names the note uses for its boxes ("정리/증명" in
math, "핵심 결과/유도" in circuits).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .schemas.definitions import DOMAINS


@dataclass(frozen=True)
class Domain:
    name: str
    title_ko: str
    prompt_files: tuple[str, ...] = ()
    """Prompts appended after the shared prompts of every agent."""
    kind_labels: dict[str, str] = field(default_factory=dict)
    """Overrides of the default block names (render_html.KIND_LABELS)."""


_DOMAINS = {
    "math": Domain(name="math", title_ko="수학"),
    "circuits": Domain(
        name="circuits",
        title_ko="회로",
        prompt_files=("domain_circuits",),
        kind_labels={"theorem": "핵심 결과", "proof": "유도", "recipe": "해석 절차"},
    ),
}
assert set(_DOMAINS) == set(DOMAINS), "every schema domain needs a profile"


def get_domain(name: str) -> Domain:
    try:
        return _DOMAINS[name]
    except KeyError:
        raise ValueError(f"unknown domain {name!r} (known: {', '.join(sorted(_DOMAINS))})") from None
