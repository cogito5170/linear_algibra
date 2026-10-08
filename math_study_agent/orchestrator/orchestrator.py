"""The Orchestrator: runs the four agents, guards every hand-off, checks quality.

    bundle ─► Material Analyst ─► [evidence guard] ─► Concept Mapper ─► [guard]
          ─► learning contexts ─► Intuition Teacher ─► Note Editor
          ─► quality check (deterministic + reviewer) ─► revise? ─► Markdown

Each stage's output is schema-validated. A stage that fails stops the run with
`PipelineError`; the run manifest records what happened. A note that fails the
quality check is still returned but marked `needs_review`, and the Markdown
starts with a visible warning.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..agents import ConceptMapper, IntuitionTeacher, MaterialAnalyst, NoteEditor
from ..errors import AgentError, PipelineError
from ..llm.base import LLMClient
from ..schemas import assert_valid
from .contexts import build_learning_contexts
from .guards import verify_analysis, verify_concept_map
from .quality import QualityReviewer, build_report, deterministic_checks, reviewer_checks, revision_feedback
from .render import render_markdown
from .style import default_style_profile


@dataclass
class OrchestratorConfig:
    max_attempts: int = 2
    """LLM attempts per agent call (retries get the validation errors as feedback)."""
    max_revisions: int = 1
    """Extra Note Editor rounds when the quality check finds problems."""
    use_reviewer: bool = True
    """Run the LLM quality reviewer in addition to deterministic checks."""
    style_profile: dict = field(default_factory=default_style_profile)


@dataclass
class PipelineResult:
    status: str  # "ok" | "needs_review"
    markdown: str
    artifacts: dict[str, Any]
    manifest: dict


class Orchestrator:
    def __init__(self, llm: LLMClient, config: OrchestratorConfig | None = None):
        self.config = config or OrchestratorConfig()
        n = self.config.max_attempts
        self.analyst = MaterialAnalyst(llm, max_attempts=n)
        self.mapper = ConceptMapper(llm, max_attempts=n)
        self.teacher = IntuitionTeacher(llm, max_attempts=n)
        self.editor = NoteEditor(llm, max_attempts=n)
        self.reviewer = QualityReviewer(llm, max_attempts=n)

    # ------------------------------------------------------------------

    def run(self, bundle: dict, output_dir: str | Path | None = None) -> PipelineResult:
        assert_valid(self.config.style_profile, "math_style_profile/1", context="style profile")
        manifest: dict[str, Any] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "bundle_id": bundle.get("bundle_id"),
            "stages": [],
        }
        artifacts: dict[str, Any] = {}
        out = Path(output_dir) if output_dir else None

        def stage(name: str, fn, *args):
            started = time.monotonic()
            entry: dict[str, Any] = {"stage": name}
            manifest["stages"].append(entry)
            try:
                value = fn(*args)
            except Exception as exc:
                entry.update(status="failed", error=str(exc), seconds=round(time.monotonic() - started, 3))
                if isinstance(exc, AgentError):
                    entry["attempts"] = exc.attempts
                manifest["status"] = "failed"
                manifest["failed_stage"] = name
                self._save(out, artifacts, manifest, None)
                raise PipelineError(name, exc, manifest) from exc
            entry.update(status="ok", seconds=round(time.monotonic() - started, 3))
            if hasattr(value, "attempts"):
                entry["attempts"] = value.attempts
            return value

        stage("validate_input", lambda: assert_valid(bundle, "math_material_bundle/1", context="input bundle"))
        artifacts["bundle"] = bundle

        analysis_raw = stage("material_analyst", self.analyst.run, bundle).output
        artifacts["analysis_raw"] = analysis_raw
        analysis, guard_a = stage("evidence_guard:analysis", verify_analysis, analysis_raw, bundle)
        assert_valid(analysis, "math_material_analysis/1", context="guarded analysis")
        artifacts["analysis"] = analysis

        mapping_request = {"schema": "math_concept_mapping_request/1", "title": bundle["title"], "analysis": analysis}
        concept_map_raw = stage("concept_mapper", self.mapper.run, mapping_request).output
        artifacts["concept_map_raw"] = concept_map_raw
        concept_map, guard_m = stage("evidence_guard:concept_map", verify_concept_map, concept_map_raw, bundle)
        artifacts["concept_map"] = concept_map
        guard_findings = guard_a + guard_m
        artifacts["guard_findings"] = guard_findings

        contexts = stage("learning_contexts", build_learning_contexts, analysis, concept_map, bundle)
        artifacts["learning_contexts"] = contexts

        teaching_request = {
            "schema": "math_teaching_request/1",
            "title": bundle["title"],
            "style_profile": self.config.style_profile,
            "concept_map": concept_map,
            "learning_contexts": contexts,
        }
        lesson = stage("intuition_teacher", self.teacher.run, teaching_request).output
        artifacts["lesson"] = lesson

        note_request = {
            "schema": "math_note_request/1",
            "title": bundle["title"],
            "style_profile": self.config.style_profile,
            "concept_map": concept_map,
            "lesson": lesson,
            "learning_contexts": contexts,
            "revision_feedback": [],
        }
        note = stage("note_editor", self.editor.run, note_request).output
        report = stage("quality_check", self._quality, note, lesson, analysis, concept_map, contexts, guard_findings)

        for round_no in range(1, self.config.max_revisions + 1):
            if report["passed"]:
                break
            feedback = revision_feedback(report)
            if not feedback:
                break  # only guard findings failed; re-editing the note cannot fix those
            note_request = {**note_request, "revision_feedback": feedback}
            note = stage(f"note_editor:revision_{round_no}", self.editor.run, note_request).output
            report = stage(
                f"quality_check:revision_{round_no}",
                self._quality,
                note,
                lesson,
                analysis,
                concept_map,
                contexts,
                guard_findings,
            )

        artifacts["note"] = note
        artifacts["quality_report"] = report
        markdown = render_markdown(note, concept_map, contexts, quality_report=report)
        status = "ok" if report["passed"] else "needs_review"
        manifest.update(status=status, finished_at=datetime.now(timezone.utc).isoformat(), quality=report["summary"])
        self._save(out, artifacts, manifest, markdown)
        return PipelineResult(status=status, markdown=markdown, artifacts=artifacts, manifest=manifest)

    # ------------------------------------------------------------------

    def _quality(self, note, lesson, analysis, concept_map, contexts, guard_findings) -> dict:
        checks = list(guard_findings) + deterministic_checks(note, lesson, concept_map, contexts)
        if self.config.use_reviewer:
            request = {"schema": "math_review_request/1", "analysis": analysis, "concept_map": concept_map, "note": note}
            try:
                review = self.reviewer.run(request).output
            except AgentError as exc:
                # A reviewer that could not run is a failed check, not a pass.
                checks.append(
                    {
                        "check_id": "RV.unavailable",
                        "category": "mathematical_correctness",
                        "severity": "error",
                        "passed": False,
                        "message": f"수학적 정확성 검토를 수행하지 못함: {exc}",
                        "targets": [],
                        "origin": "reviewer",
                    }
                )
            else:
                checks += reviewer_checks(review)
        return build_report(checks)

    @staticmethod
    def _save(out: Path | None, artifacts: dict, manifest: dict, markdown: str | None) -> None:
        if out is None:
            return
        out.mkdir(parents=True, exist_ok=True)
        for name, value in artifacts.items():
            (out / f"{name}.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if markdown is not None:
            (out / "study_note.md").write_text(markdown, encoding="utf-8")
