"""Hallucination guards that run between agents.

The model is asked to quote its sources verbatim. Here the orchestrator checks
every quote against the original chunk text:

- evidence whose chunk does not exist or whose quote is not in the chunk is dropped
- an `observed` item left without valid evidence is downgraded to `uncertain`
- a professor emphasis/explanation/warning that is not verifiably observed is
  removed from `professor_emphasis` and recorded as an uncertainty instead
- an emphasis attributed to professor material but supported only by the
  user's own notes is re-attributed to `user_reported`

Every change is reported as a check in the quality report, never applied silently.
"""

from __future__ import annotations

import copy
import re
import unicodedata

from ..ingest import chunk_index

_WS = re.compile(r"\s+")
# Formatting that may differ between the source and a faithful quote.
_NOISE = re.compile(r"[*_`>|]")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _NOISE.sub("", text)
    return _WS.sub(" ", text).strip().casefold()


def quote_in_chunk(quote: str, chunk_text: str) -> bool:
    q = normalize(quote)
    return bool(q) and q in normalize(chunk_text)


def finding(check_id: str, severity: str, message: str, targets: list[str], category: str = "source_fidelity") -> dict:
    return {
        "check_id": check_id,
        "category": category,
        "severity": severity,
        "passed": severity == "info",
        "message": message,
        "targets": targets,
        "origin": "guard",
    }


def _filter_evidence(item: dict, where: str, chunks: dict, findings: list[dict]) -> list[dict]:
    valid = []
    for ev in item.get("evidence", []):
        chunk = chunks.get(ev["chunk_id"])
        if chunk is None:
            findings.append(
                finding("GUARD.EVIDENCE_CHUNK", "warning", f"{where}: cites unknown chunk {ev['chunk_id']}; evidence dropped", [where])
            )
        elif not quote_in_chunk(ev["quote"], chunk["text"]):
            findings.append(
                finding(
                    "GUARD.EVIDENCE_QUOTE",
                    "warning",
                    f"{where}: quote not found in {ev['chunk_id']} ({ev['quote'][:60]!r}); evidence dropped",
                    [where],
                )
            )
        else:
            valid.append(ev)
    item["evidence"] = valid
    return valid


def _downgrade_if_unsupported(item: dict, where: str, findings: list[dict]) -> None:
    if item.get("status") == "observed" and not item.get("evidence"):
        item["status"] = "uncertain"
        item["confidence"] = min(item.get("confidence", 0.4), 0.4)
        note = "[검증] 원문에서 인용을 확인하지 못해 observed에서 uncertain으로 낮춤."
        item["rationale"] = f"{item.get('rationale', '')} {note}".strip()
        findings.append(
            finding("GUARD.DOWNGRADED", "warning", f"{where}: observed claim had no verifiable evidence; downgraded to uncertain", [where])
        )


def _next_id(items: list[dict], prefix: str) -> int:
    numbers = [int(i["id"][len(prefix):]) for i in items if re.fullmatch(prefix + r"\d+", i.get("id", ""))]
    return max(numbers, default=0) + 1


def verify_analysis(analysis: dict, bundle: dict) -> tuple[dict, list[dict]]:
    """Return a sanitized copy of the analysis and the guard findings."""
    result = copy.deepcopy(analysis)
    chunks = chunk_index(bundle)
    findings: list[dict] = []

    for name in ("concepts", "definitions", "formulas", "theorems", "examples", "relationships"):
        for item in result[name]:
            where = f"analysis.{name}[{item['id']}]"
            _filter_evidence(item, where, chunks, findings)
            _downgrade_if_unsupported(item, where, findings)

    for item in result["uncertainties"]:
        _filter_evidence(item, f"analysis.uncertainties[{item['id']}]", chunks, findings)

    kept = []
    next_u = _next_id(result["uncertainties"], "U")
    for item in result["professor_emphasis"]:
        where = f"analysis.professor_emphasis[{item['id']}]"
        valid = _filter_evidence(item, where, chunks, findings)
        if item["status"] != "observed" or not valid:
            result["uncertainties"].append(
                {
                    "id": f"U{next_u}",
                    "concept_ids": item["concept_ids"],
                    "question": f"자료로 확인되지 않은 교수님 {item['kind']}: {item['content']}",
                    "reason": "교수님 자료에서 근거를 확인할 수 없어 교수님의 말로 다루지 않음",
                    "evidence": valid,
                }
            )
            findings.append(
                finding(
                    "GUARD.EMPHASIS_UNVERIFIED",
                    "warning",
                    f"{where}: not verifiably observed; moved to uncertainties as U{next_u}",
                    [where, f"U{next_u}"],
                )
            )
            next_u += 1
            continue
        authors = {chunks[ev["chunk_id"]]["author"] for ev in valid}
        if "professor" not in authors and item["attribution"] == "professor_material":
            item["attribution"] = "user_reported"
            findings.append(
                finding(
                    "GUARD.ATTRIBUTION",
                    "info",
                    f"{where}: only supported by non-professor material; attribution set to user_reported",
                    [where],
                )
            )
        kept.append(item)
    result["professor_emphasis"] = kept
    return result, findings


def verify_concept_map(concept_map: dict, bundle: dict) -> tuple[dict, list[dict]]:
    result = copy.deepcopy(concept_map)
    chunks = chunk_index(bundle)
    findings: list[dict] = []
    for c in result["concepts"]:
        where = f"concept_map.concepts[{c['id']}]"
        _filter_evidence(c, where, chunks, findings)
        _downgrade_if_unsupported(c, where, findings)
    for dep in result["dependencies"]:
        where = f"concept_map.dependencies[{dep['from']}->{dep['to']}]"
        _filter_evidence(dep, where, chunks, findings)
        _downgrade_if_unsupported(dep, where, findings)
    return result, findings
