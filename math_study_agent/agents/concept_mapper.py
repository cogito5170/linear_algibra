"""Agent 2: builds the conceptual structure of the lecture."""

from __future__ import annotations

from .base import Agent, analysis_ids, duplicate_ids, find_cycle


class ConceptMapper(Agent):
    name = "concept_mapper"
    input_schema = "math_concept_mapping_request/1"
    output_schema = "math_concept_map/1"
    prompt_files = ("shared_principles", "concept_mapper")
    task_instruction = (
        "아래 분석 결과로 강의의 개념 구조 `math_concept_map/1`을 작성하세요. "
        "각 개념이 무엇인지, 왜 필요한지, 무엇에서 오고 어디로 가는지가 드러나야 합니다."
    )

    def semantic_issues(self, output: dict, payload: dict) -> list[str]:
        analysis = payload["analysis"]
        issues = []
        concepts = {c["id"]: c for c in output["concepts"]}
        for dupe in duplicate_ids(output["concepts"]):
            issues.append(f"concepts: duplicate id {dupe}")

        for c in analysis["concepts"]:
            if c["id"] not in concepts:
                issues.append(f"concept {c['id']} ({c['name']}) from the analysis is missing from the map")

        known_refs = analysis_ids(analysis)
        for c in output["concepts"]:
            for ref in c["prerequisites"] + c["leads_to"]:
                if ref not in concepts:
                    issues.append(f"concepts[{c['id']}]: unknown concept reference {ref}")
            if c["id"] in c["prerequisites"]:
                issues.append(f"concepts[{c['id']}]: a concept cannot be its own prerequisite")
            for ref in c["analysis_refs"]:
                if ref not in known_refs:
                    issues.append(f"concepts[{c['id']}]: analysis_refs contains unknown id {ref}")
            if c["id"] not in {a["id"] for a in analysis["concepts"]} and c["status"] == "observed":
                issues.append(f"concepts[{c['id']}]: a concept added by the mapper must be inferred or uncertain")

        for dep in output["dependencies"]:
            for ref in (dep["from"], dep["to"]):
                if ref not in concepts:
                    issues.append(f"dependencies {dep['from']}->{dep['to']}: unknown concept {ref}")

        for cid in output["core_concepts"]:
            if cid not in concepts:
                issues.append(f"core_concepts: unknown concept {cid}")
        if not output["core_concepts"]:
            issues.append("core_concepts is empty: mark the concepts the lecture is really about")

        for k in output["prerequisites"]:
            for ref in k["needed_for"]:
                if ref not in concepts:
                    issues.append(f"prerequisites[{k['id']}]: unknown concept {ref}")

        flow = output["learning_flow"]
        order = [step["concept_id"] for step in flow]
        if [step["step"] for step in flow] != list(range(1, len(flow) + 1)):
            issues.append("learning_flow steps must be numbered 1..n in order")
        if sorted(order) != sorted(concepts) or len(set(order)) != len(order):
            missing = sorted(set(concepts) - set(order))
            extra = sorted(set(order) - set(concepts))
            issues.append(
                f"learning_flow must list every concept exactly once (missing={missing}, unknown={extra})"
            )

        graph = {cid: [p for p in c["prerequisites"] if p in concepts] for cid, c in concepts.items()}
        cycle = find_cycle(graph)
        if cycle:
            issues.append("prerequisite cycle: " + " -> ".join(cycle))
        else:
            position = {cid: i for i, cid in enumerate(order)}
            for cid, prereqs in graph.items():
                for p in prereqs:
                    if cid in position and p in position and position[p] > position[cid]:
                        issues.append(f"learning_flow puts {cid} before its prerequisite {p}")
        return issues
