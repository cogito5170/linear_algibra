"""Builds per-concept `math_learning_context` packets from analysis + concept map.

This is deterministic glue owned by the orchestrator: agents downstream of the
Concept Mapper see each concept through exactly one context packet that
carries content, professor context, interpretation, sources and epistemic status.
"""

from __future__ import annotations

from ..ingest import chunk_index
from ..schemas import assert_valid

_V1_ONLY_KEYS = ("source", "concept", "content", "professor_context", "interpretation", "epistemic_status")


def _concept_items(analysis: dict, cid: str) -> dict[str, list[dict]]:
    return {
        "definitions": [d for d in analysis["definitions"] if d["concept_id"] == cid],
        "formulas": [f for f in analysis["formulas"] if f["concept_id"] == cid],
        "theorems": [t for t in analysis["theorems"] if cid in t["concept_ids"]],
        "examples": [e for e in analysis["examples"] if cid in e["concept_ids"]],
        "relationships": [r for r in analysis["relationships"] if cid in (r["from_concept"], r["to_concept"])],
        "emphasis": [p for p in analysis["professor_emphasis"] if cid in p["concept_ids"]],
    }


def build_learning_contexts(analysis: dict, concept_map: dict, bundle: dict) -> list[dict]:
    """One `math_learning_context/2` per concept, in learning-flow order."""
    chunks = chunk_index(bundle)
    analysis_concepts = {c["id"]: c for c in analysis["concepts"]}
    map_concepts = {c["id"]: c for c in concept_map["concepts"]}
    contexts = []

    for step in concept_map["learning_flow"]:
        cid = step["concept_id"]
        mc = map_concepts[cid]
        items = _concept_items(analysis, cid)
        base = analysis_concepts.get(cid)

        cited_items = ([base] if base else []) + [i for group in items.values() for i in group] + [mc]
        sources, seen = [], set()
        for item in cited_items:
            for ev in item.get("evidence", []):
                chunk = chunks.get(ev["chunk_id"])
                if chunk and ev["chunk_id"] not in seen:
                    seen.add(ev["chunk_id"])
                    sources.append(
                        {
                            "chunk_id": ev["chunk_id"],
                            "material_id": chunk["material_id"],
                            "page": chunk["page"],
                            "section": chunk["section"],
                        }
                    )
        order = {chunk_id: i for i, chunk_id in enumerate(chunks)}
        sources.sort(key=lambda src: order[src["chunk_id"]])
        primary = sources[0] if sources else {"material_id": analysis["material_id"], "page": None, "section": ""}

        epistemic = {"observed": [], "inferred": [], "uncertain": []}
        for item in ([base] if base else []) + [i for group in items.values() for i in group]:
            epistemic[item["status"]].append(item["id"])
        epistemic[mc["why_needed_status"]].append("interpretation.why")
        # An intuition is an interpretation by construction, never a fact from the material.
        epistemic["inferred"].append("interpretation.intuition")

        relations = []
        for dep in concept_map["dependencies"]:
            if cid in (dep["from"], dep["to"]):
                other = dep["to"] if dep["from"] == cid else dep["from"]
                direction = "→" if dep["from"] == cid else "←"
                relations.append(
                    {"concept_id": other, "relation": f"{dep['kind']} {direction}", "description": dep["explanation"]}
                )

        context = {
            "schema": "math_learning_context/2",
            "source": {"material_id": primary["material_id"], "page": primary["page"], "section": primary["section"]},
            "concept": {"id": cid, "name": mc["name"]},
            "content": {
                "definitions": items["definitions"],
                "formulas": items["formulas"],
                "examples": items["examples"],
                "relationships": items["relationships"],
                "theorems": items["theorems"],
            },
            "professor_context": {
                "emphasis": [p for p in items["emphasis"] if p["kind"] == "emphasis"],
                "explanation": [p for p in items["emphasis"] if p["kind"] == "explanation"],
                "warnings": [p for p in items["emphasis"] if p["kind"] == "warning"],
            },
            "interpretation": {"why": mc["why_needed"], "intuition": mc["intuition"], "conceptual_relation": relations},
            "epistemic_status": epistemic,
            "sources": sources,
            "role": mc["role"],
            "prerequisites": mc["prerequisites"],
            "leads_to": mc["leads_to"],
            "open_questions": [u for u in analysis["uncertainties"] if cid in u["concept_ids"]],
        }
        assert_valid(context, "math_learning_context/2", context=f"learning context {cid}")
        contexts.append(context)
    return contexts


def to_v1(context: dict) -> dict:
    """Project a v2 context onto the v1 contract (v2 is a strict superset)."""
    v1 = {key: context[key] for key in _V1_ONLY_KEYS}
    v1["content"] = {k: v for k, v in context["content"].items() if k != "theorems"}
    v1["schema"] = "math_learning_context/1"
    assert_valid(v1, "math_learning_context/1")
    return v1
