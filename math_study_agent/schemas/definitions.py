"""Versioned semantic JSON schemas for every agent boundary.

Schema ids look like ``<name>/<version>`` (e.g. ``math_material_analysis/1``).
Every payload carries its id in the top-level ``schema`` field.

Versioning rule: a published schema is never changed in a breaking way. When a
new shape is needed, register ``<name>/<version+1>`` next to the old one
(see ``math_learning_context/1`` and ``/2``).
"""

from __future__ import annotations

from ..epistemics import STATUSES
from .builders import (
    Schema,
    arr,
    boolean,
    const,
    enum,
    integer,
    nullable,
    number,
    obj,
    string,
    text,
)

# ---------------------------------------------------------------------------
# Shared vocabulary
# ---------------------------------------------------------------------------

EPISTEMIC_STATUSES = list(STATUSES)

SOURCE_KINDS = [
    "lecture_slides",
    "lecture_pdf",
    "professor_notes",
    "handwritten_notes",
    "user_notes",
]
SOURCE_AUTHORS = ["professor", "user", "unknown"]

CONCEPT_ID = r"^C\d+$"
DEFINITION_ID = r"^D\d+$"
FORMULA_ID = r"^F\d+$"
THEOREM_ID = r"^T\d+$"
EXAMPLE_ID = r"^E\d+$"
EMPHASIS_ID = r"^P\d+$"
RELATIONSHIP_ID = r"^R\d+$"
UNCERTAINTY_ID = r"^U\d+$"
PREREQUISITE_ID = r"^K\d+$"

RELATION_TYPES = [
    "prerequisite_of",
    "motivates",
    "generalizes",
    "special_case_of",
    "uses",
    "equivalent_to",
    "contrasts_with",
    "leads_to",
]

CONCEPT_ROLES = ["core", "supporting", "prerequisite", "application"]

LEVELS = ["LOW", "LOW_MEDIUM", "MEDIUM", "HIGH"]

NOTE_SECTION_KEYS = [
    "one_line",
    "why",
    "core",
    "intuition",
    "relations",
    "formulas",
    "example",
    "professor",
    "pitfalls",
    "previous_link",
    "review",
]

QUALITY_CATEGORIES = [
    "schema",
    "source_fidelity",
    "conceptual_clarity",
    "intuition",
    "logicality",
    "mathematical_correctness",
    "user_readability",
]
SEVERITIES = ["error", "warning", "info"]


def status_field(description: str = "observed: 자료에 실제로 있음 / inferred: 자료 구조로부터 합리적으로 추론 / uncertain: 자료만으로 판단 어려움") -> Schema:
    return enum(EPISTEMIC_STATUSES, description)


def evidence_item() -> Schema:
    return obj(
        {
            "chunk_id": text("인용한 source chunk의 id (입력 bundle에 존재해야 함)"),
            "quote": text("chunk 원문에서 그대로 복사한 짧은 인용. 바꿔 쓰지 않는다."),
        }
    )


def epistemic_props() -> dict[str, Schema]:
    """Fields attached to every extracted or interpreted item."""
    return {
        "status": status_field(),
        "confidence": number("0~1 사이 확신도", minimum=0, maximum=1),
        "evidence": arr(evidence_item(), "observed 항목은 최소 1개의 원문 인용이 필요"),
        "rationale": string("inferred/uncertain인 이유 또는 추론 근거. observed면 빈 문자열 가능"),
    }


# ---------------------------------------------------------------------------
# Input: material bundle
# ---------------------------------------------------------------------------


def chunk_schema() -> Schema:
    return obj(
        {
            "chunk_id": text(),
            "page": nullable(integer(minimum=1)),
            "section": string(),
            "text": string(),
        }
    )


def source_schema() -> Schema:
    return obj(
        {
            "material_id": text(),
            "kind": enum(SOURCE_KINDS),
            "author": enum(SOURCE_AUTHORS, "누가 작성한 자료인가. 교수님 발언/강조의 근거는 professor 자료여야 한다."),
            "title": string(),
            "chunks": arr(chunk_schema()),
        }
    )


MATERIAL_BUNDLE_V1 = obj(
    {
        "schema": const("math_material_bundle/1"),
        "bundle_id": text(),
        "title": string(),
        "sources": arr(source_schema(), min_items=1),
    },
    "Agent 1(Material Analyst)의 입력. 교안/필기를 주소 지정 가능한 chunk로 나눈 것.",
)


STYLE_PROFILE_V1 = obj(
    {
        "schema": const("math_style_profile/1"),
        "language": text(),
        "conceptual_understanding": enum(LEVELS),
        "mathematical_formalism": enum(LEVELS),
        "proof_detail": enum(LEVELS),
        "terminology_complexity": enum(LEVELS),
        "intuition": enum(LEVELS),
        "preferences": arr(string()),
        "avoid": arr(string()),
    }
)


# ---------------------------------------------------------------------------
# Agent 1 output: material analysis
# ---------------------------------------------------------------------------


def analysis_concept() -> Schema:
    return obj(
        {
            "id": string(pattern=CONCEPT_ID),
            "name": text(),
            "description": text("자료에서 이 개념이 무엇으로 다뤄지는지 한두 문장"),
            **epistemic_props(),
        }
    )


def analysis_definition() -> Schema:
    return obj(
        {
            "id": string(pattern=DEFINITION_ID),
            "concept_id": string(pattern=CONCEPT_ID),
            "term": text(),
            "statement": text("정의 문장. 조건/정의역을 빠뜨리지 않는다."),
            "conditions": arr(string(), "정의가 성립하기 위한 조건, domain 등"),
            **epistemic_props(),
        }
    )


def analysis_formula() -> Schema:
    return obj(
        {
            "id": string(pattern=FORMULA_ID),
            "concept_id": string(pattern=CONCEPT_ID),
            "latex": text(),
            "meaning": text("수식이 표현하는 관계를 말로"),
            "variables": arr(obj({"symbol": text(), "meaning": text()})),
            "conditions": arr(string()),
            **epistemic_props(),
        }
    )


def analysis_theorem() -> Schema:
    return obj(
        {
            "id": string(pattern=THEOREM_ID),
            "concept_ids": arr(string(pattern=CONCEPT_ID)),
            "name": string(),
            "statement": text(),
            "hypotheses": arr(string()),
            "conclusion": string(),
            **epistemic_props(),
        }
    )


def analysis_example() -> Schema:
    return obj(
        {
            "id": string(pattern=EXAMPLE_ID),
            "concept_ids": arr(string(pattern=CONCEPT_ID)),
            "title": string(),
            "content": text(),
            **epistemic_props(),
        }
    )


def analysis_emphasis() -> Schema:
    return obj(
        {
            "id": string(pattern=EMPHASIS_ID),
            "concept_ids": arr(string(pattern=CONCEPT_ID)),
            "kind": enum(["emphasis", "explanation", "warning"]),
            "content": text("자료에 적힌 교수님의 강조/설명/주의. 원문에 없는 말을 만들지 않는다."),
            "attribution": enum(
                ["professor_material", "user_reported"],
                "professor_material: 교수님 자료에 직접 있음 / user_reported: 사용자 필기에 '교수님이 ~라고 함'처럼 기록됨",
            ),
            **epistemic_props(),
        }
    )


def analysis_relationship() -> Schema:
    return obj(
        {
            "id": string(pattern=RELATIONSHIP_ID),
            "from_concept": string(pattern=CONCEPT_ID),
            "to_concept": string(pattern=CONCEPT_ID),
            "type": enum(RELATION_TYPES),
            "description": text(),
            **epistemic_props(),
        }
    )


def analysis_uncertainty() -> Schema:
    return obj(
        {
            "id": string(pattern=UNCERTAINTY_ID),
            "concept_ids": arr(string(pattern=CONCEPT_ID)),
            "question": text("무엇이 불명확하거나 빠져 있는가"),
            "reason": text(),
            "evidence": arr(evidence_item()),
        }
    )


MATERIAL_ANALYSIS_V1 = obj(
    {
        "schema": const("math_material_analysis/1"),
        "material_id": text(),
        "concepts": arr(analysis_concept()),
        "definitions": arr(analysis_definition()),
        "formulas": arr(analysis_formula()),
        "theorems": arr(analysis_theorem()),
        "examples": arr(analysis_example()),
        "professor_emphasis": arr(analysis_emphasis()),
        "relationships": arr(analysis_relationship()),
        "uncertainties": arr(analysis_uncertainty()),
    },
    "Agent 1(Material Analyst)의 출력",
)


# ---------------------------------------------------------------------------
# Agent 2: concept map
# ---------------------------------------------------------------------------

CONCEPT_MAPPING_REQUEST_V1 = obj(
    {
        "schema": const("math_concept_mapping_request/1"),
        "title": string(),
        "analysis": MATERIAL_ANALYSIS_V1,
    }
)


def map_concept() -> Schema:
    return obj(
        {
            "id": string(pattern=CONCEPT_ID),
            "name": text(),
            "role": enum(CONCEPT_ROLES),
            "what": text("이 개념은 무엇인가"),
            "why_needed": text("왜 필요한가 (어떤 문제를 해결하려고 등장했나)"),
            "why_needed_status": status_field("why_needed가 자료에 있으면 observed, 구조로부터 추론했으면 inferred"),
            "intuition": text("한 줄 직관"),
            "prerequisites": arr(string(pattern=CONCEPT_ID)),
            "leads_to": arr(string(pattern=CONCEPT_ID)),
            "analysis_refs": arr(text(), "근거가 된 analysis 항목 id (D1, F2, P1 ...)"),
            **epistemic_props(),
        }
    )


def map_dependency() -> Schema:
    return obj(
        {
            "from": string(pattern=CONCEPT_ID),
            "to": string(pattern=CONCEPT_ID),
            "kind": enum(["requires", "motivates", "generalizes", "special_case_of", "uses", "contrasts_with"]),
            "explanation": text("from이 to에 왜/어떻게 필요한지"),
            **epistemic_props(),
        }
    )


def map_flow_step() -> Schema:
    return obj(
        {
            "step": integer(minimum=1),
            "concept_id": string(pattern=CONCEPT_ID),
            "transition": text("이전 단계에서 이 개념으로 넘어오는 자연스러운 연결 문장"),
            "status": status_field(),
            "rationale": string(),
        }
    )


def map_prerequisite() -> Schema:
    return obj(
        {
            "id": string(pattern=PREREQUISITE_ID),
            "name": text(),
            "why_needed": text(),
            "needed_for": arr(string(pattern=CONCEPT_ID)),
            "covered_in_material": boolean("이번 자료 안에서 다뤄지는가"),
            "status": status_field(),
            "rationale": string(),
        }
    )


CONCEPT_MAP_V1 = obj(
    {
        "schema": const("math_concept_map/1"),
        "concepts": arr(map_concept()),
        "dependencies": arr(map_dependency()),
        "learning_flow": arr(map_flow_step()),
        "core_concepts": arr(string(pattern=CONCEPT_ID)),
        "prerequisites": arr(map_prerequisite()),
    },
    "Agent 2(Concept Mapper)의 출력",
)


# ---------------------------------------------------------------------------
# Semantic contract: per-concept learning context
# ---------------------------------------------------------------------------


def _learning_context_props() -> dict[str, Schema]:
    ref_list = arr(string(), "항목 id 또는 'interpretation.why' 같은 필드 경로")
    return {
        "source": obj(
            {
                "material_id": string(),
                "page": nullable(integer(minimum=1)),
                "section": string(),
            }
        ),
        "concept": obj({"id": string(pattern=CONCEPT_ID), "name": text()}),
        "content": obj(
            {
                "definitions": arr(analysis_definition()),
                "formulas": arr(analysis_formula()),
                "examples": arr(analysis_example()),
                "relationships": arr(analysis_relationship()),
            }
        ),
        "professor_context": obj(
            {
                "emphasis": arr(analysis_emphasis()),
                "explanation": arr(analysis_emphasis()),
                "warnings": arr(analysis_emphasis()),
            }
        ),
        "interpretation": obj(
            {
                "why": string(),
                "intuition": string(),
                "conceptual_relation": arr(
                    obj(
                        {
                            "concept_id": string(pattern=CONCEPT_ID),
                            "relation": text(),
                            "description": string(),
                        }
                    )
                ),
            }
        ),
        "epistemic_status": obj({"observed": ref_list, "inferred": ref_list, "uncertain": ref_list}),
    }


LEARNING_CONTEXT_V1 = obj(
    {"schema": const("math_learning_context/1"), **_learning_context_props()},
    "Agent 간 개념 단위 semantic contract (기본형)",
)


def _learning_context_v2() -> Schema:
    props = _learning_context_props()
    content = props["content"]
    content["properties"]["theorems"] = arr(analysis_theorem())
    content["required"].append("theorems")
    return obj(
        {
            "schema": const("math_learning_context/2"),
            **props,
            "sources": arr(
                obj(
                    {
                        "chunk_id": text(),
                        "material_id": text(),
                        "page": nullable(integer(minimum=1)),
                        "section": string(),
                    }
                ),
                "이 개념의 모든 근거 위치 (v2 추가)",
            ),
            "role": enum(CONCEPT_ROLES),
            "prerequisites": arr(string(pattern=CONCEPT_ID)),
            "leads_to": arr(string(pattern=CONCEPT_ID)),
            "open_questions": arr(analysis_uncertainty(), "이 개념과 관련된 불확실성 (v2 추가)"),
        },
        "math_learning_context/1의 하위 호환 확장: theorems, sources, role, prerequisites, leads_to, open_questions 추가",
    )


LEARNING_CONTEXT_V2 = _learning_context_v2()


# ---------------------------------------------------------------------------
# Agent 3: intuition teacher
# ---------------------------------------------------------------------------

TEACHING_REQUEST_V1 = obj(
    {
        "schema": const("math_teaching_request/1"),
        "title": string(),
        "style_profile": STYLE_PROFILE_V1,
        "concept_map": CONCEPT_MAP_V1,
        "learning_contexts": arr(LEARNING_CONTEXT_V2),
    }
)


def lesson_schema() -> Schema:
    return obj(
        {
            "concept_id": string(pattern=CONCEPT_ID),
            "name": text(),
            "one_line_intuition": text(),
            "why_needed": obj({"text": text(), "status": status_field()}),
            "meaning": text("무엇을 의미하는가 (수식 없이)"),
            "intuition": obj(
                {
                    "intuitive": text("직관적으로는: ..."),
                    "rigorous": nullable(text("엄밀하게는: ... (비유/직관이 단순화한 부분을 바로잡음)")),
                    "analogy_caveat": nullable(text("비유가 성립하지 않는 지점")),
                }
            ),
            "connections": obj(
                {
                    "from_previous": nullable(text()),
                    "to_next": nullable(text()),
                    "related": arr(obj({"concept_id": string(pattern=CONCEPT_ID), "relation": text()})),
                }
            ),
            "example": nullable(
                obj(
                    {
                        "title": text(),
                        "setup": text(),
                        "walkthrough": text(),
                        "takeaway": text(),
                        "example_ref": nullable(string(pattern=EXAMPLE_ID)),
                    }
                )
            ),
            "formulas": arr(
                obj(
                    {
                        "formula_ref": nullable(string(pattern=FORMULA_ID)),
                        "origin": enum(["material", "supplementary"], "supplementary: 교안에 없는 보충 수식"),
                        "latex": text(),
                        "plain_meaning": text("수식이 말하는 관계를 한 문장으로"),
                        "parts": arr(obj({"symbol": text(), "meaning": text()})),
                    }
                )
            ),
            "rigorous_note": nullable(text("필요한 경우에만: 조건, 정의역, 필요/충분조건 등")),
            "professor_points": arr(
                obj(
                    {
                        "emphasis_ref": string(pattern=EMPHASIS_ID),
                        "kind": enum(["emphasis", "explanation", "warning"]),
                        "paraphrase": text(),
                    }
                )
            ),
            "pitfalls": arr(obj({"text": text(), "basis_refs": arr(string()), "status": status_field()})),
            "review_points": arr(text()),
            "epistemic_notes": arr(obj({"text": text(), "status": status_field()})),
        }
    )


INTUITION_LESSON_V1 = obj(
    {
        "schema": const("math_intuition_lesson/1"),
        "lessons": arr(lesson_schema()),
    },
    "Agent 3(Intuition Teacher)의 출력",
)


# ---------------------------------------------------------------------------
# Agent 4: note editor
# ---------------------------------------------------------------------------


def revision_item() -> Schema:
    return obj({"check_id": text(), "message": text(), "targets": arr(string())})


NOTE_REQUEST_V1 = obj(
    {
        "schema": const("math_note_request/1"),
        "title": string(),
        "style_profile": STYLE_PROFILE_V1,
        "concept_map": CONCEPT_MAP_V1,
        "lesson": INTUITION_LESSON_V1,
        "learning_contexts": arr(LEARNING_CONTEXT_V2),
        "revision_feedback": arr(revision_item(), "이전 초안에 대한 품질 검사 결과. 비어 있으면 첫 작성"),
    }
)


def note_section() -> Schema:
    return obj(
        {
            "key": enum(NOTE_SECTION_KEYS),
            "body_markdown": text(),
            "refs": arr(string(), "근거 id (P*, F*, D*, E*, T*, C*). professor 섹션은 P*가 필수"),
            "status": enum(EPISTEMIC_STATUSES + ["mixed"]),
        }
    )


STUDY_NOTE_V1 = obj(
    {
        "schema": const("math_study_note/1"),
        "title": text(),
        "big_picture": text("이번 강의 전체가 무엇을 하려는지 몇 문장으로"),
        "concept_order": arr(string(pattern=CONCEPT_ID)),
        "entries": arr(
            obj(
                {
                    "concept_id": string(pattern=CONCEPT_ID),
                    "title": text(),
                    "depth": enum(["full", "brief"], "핵심 개념은 full, 보조 개념은 brief"),
                    "sections": arr(note_section()),
                }
            )
        ),
        "open_questions": arr(obj({"question": text(), "reason": text(), "refs": arr(string())})),
    },
    "Agent 4(Note Editor)의 출력. Markdown은 Orchestrator가 이 구조로부터 렌더링한다.",
)


# ---------------------------------------------------------------------------
# Orchestrator quality check
# ---------------------------------------------------------------------------

REVIEW_REQUEST_V1 = obj(
    {
        "schema": const("math_review_request/1"),
        "analysis": MATERIAL_ANALYSIS_V1,
        "concept_map": CONCEPT_MAP_V1,
        "note": STUDY_NOTE_V1,
    }
)


def review_finding() -> Schema:
    return obj(
        {
            "category": enum(QUALITY_CATEGORIES),
            "severity": enum(SEVERITIES),
            "message": text(),
            "targets": arr(string(), "concept id 또는 'C1.formulas' 같은 섹션 경로"),
            "suggestion": string(),
        }
    )


QUALITY_REVIEW_V1 = obj(
    {
        "schema": const("math_quality_review/1"),
        "findings": arr(review_finding()),
        "overall_comment": string(),
    },
    "LLM 기반 품질 검토자(수학적 정확성, 논리성, 가독성)의 출력",
)


QUALITY_REPORT_V1 = obj(
    {
        "schema": const("math_quality_report/1"),
        "passed": boolean(),
        "checks": arr(
            obj(
                {
                    "check_id": text(),
                    "category": enum(QUALITY_CATEGORIES),
                    "severity": enum(SEVERITIES),
                    "passed": boolean(),
                    "message": text(),
                    "targets": arr(string()),
                    "origin": enum(["deterministic", "reviewer", "guard"]),
                }
            )
        ),
        "summary": obj({"errors": integer(minimum=0), "warnings": integer(minimum=0), "infos": integer(minimum=0)}),
    }
)


ALL_SCHEMAS: dict[str, Schema] = {
    "math_material_bundle/1": MATERIAL_BUNDLE_V1,
    "math_style_profile/1": STYLE_PROFILE_V1,
    "math_material_analysis/1": MATERIAL_ANALYSIS_V1,
    "math_concept_mapping_request/1": CONCEPT_MAPPING_REQUEST_V1,
    "math_concept_map/1": CONCEPT_MAP_V1,
    "math_learning_context/1": LEARNING_CONTEXT_V1,
    "math_learning_context/2": LEARNING_CONTEXT_V2,
    "math_teaching_request/1": TEACHING_REQUEST_V1,
    "math_intuition_lesson/1": INTUITION_LESSON_V1,
    "math_note_request/1": NOTE_REQUEST_V1,
    "math_study_note/1": STUDY_NOTE_V1,
    "math_review_request/1": REVIEW_REQUEST_V1,
    "math_quality_review/1": QUALITY_REVIEW_V1,
    "math_quality_report/1": QUALITY_REPORT_V1,
}
