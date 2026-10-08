"""Agent 1: extracts mathematical content from lecture materials."""

from __future__ import annotations

from ..ingest import chunk_index
from .base import ANALYSIS_COLLECTIONS, Agent, duplicate_ids


class MaterialAnalyst(Agent):
    name = "material_analyst"
    input_schema = "math_material_bundle/1"
    output_schema = "math_material_analysis/1"
    prompt_files = ("shared_principles", "material_analyst")
    task_instruction = (
        "아래 강의 자료를 분석해 `math_material_analysis/1`을 작성하세요. "
        "chunk를 인용할 때는 chunk id와 원문 그대로의 짧은 quote를 쓰세요."
    )

    def render_input(self, payload: dict) -> str:
        lines = [f'<bundle bundle_id="{payload["bundle_id"]}" title="{payload["title"]}">']
        for source in payload["sources"]:
            lines.append(
                f'<source material_id="{source["material_id"]}" kind="{source["kind"]}" '
                f'author="{source["author"]}" title="{source["title"]}">'
            )
            for chunk in source["chunks"]:
                page = chunk["page"] if chunk["page"] is not None else ""
                lines.append(f'<chunk id="{chunk["chunk_id"]}" page="{page}" section="{chunk["section"]}">')
                lines.append(chunk["text"])
                lines.append("</chunk>")
            lines.append("</source>")
        lines.append("</bundle>")
        return "\n".join(lines)

    def semantic_issues(self, output: dict, payload: dict) -> list[str]:
        issues = []
        if output["material_id"] != payload["bundle_id"]:
            issues.append(f"material_id must be the bundle_id {payload['bundle_id']!r}, got {output['material_id']!r}")

        for name in ANALYSIS_COLLECTIONS:
            for dupe in duplicate_ids(output[name]):
                issues.append(f"{name}: duplicate id {dupe}")

        concepts = {c["id"] for c in output["concepts"]}
        if not concepts:
            issues.append("concepts is empty: at least one concept must be extracted")

        def check_concepts(where: str, ids: list[str]):
            for cid in ids:
                if cid not in concepts:
                    issues.append(f"{where}: unknown concept id {cid}")

        for d in output["definitions"]:
            check_concepts(f"definitions[{d['id']}]", [d["concept_id"]])
        for f in output["formulas"]:
            check_concepts(f"formulas[{f['id']}]", [f["concept_id"]])
        for name in ("theorems", "examples", "professor_emphasis", "uncertainties"):
            for item in output[name]:
                check_concepts(f"{name}[{item['id']}]", item["concept_ids"])
        for r in output["relationships"]:
            check_concepts(f"relationships[{r['id']}]", [r["from_concept"], r["to_concept"]])

        chunks = chunk_index(payload)
        for name in ANALYSIS_COLLECTIONS:
            for item in output[name]:
                for ev in item.get("evidence", []):
                    if ev["chunk_id"] not in chunks:
                        issues.append(f"{name}[{item['id']}]: evidence cites unknown chunk {ev['chunk_id']}")
                if item.get("status") == "observed" and not item.get("evidence"):
                    issues.append(f"{name}[{item['id']}]: status is observed but evidence is empty")
        return issues
