"""Command line interface.

    math-study run --slides lec03.pdf --prof-notes board.md --user-notes mine.md \
        --title "3강: 선형독립과 기저" --out runs/lec03

    math-study ingest --slides lec03.pdf --out bundle.json      # inspect chunk ids
    math-study validate runs/lec03/concept_map.json             # check any payload
    math-study schemas schemas/                                 # export JSON schemas

Exit codes: 0 = note ready, 2 = note produced but needs review, 1 = failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .errors import MathStudyError, PipelineError
from .ingest import build_bundle, load_source
from .schemas import export_schemas, validate

_SOURCE_FLAGS = [
    ("--slides", "lecture_slides", "slides"),
    ("--pdf", "lecture_pdf", "pdf"),
    ("--prof-notes", "professor_notes", "prof"),
    ("--handwritten", "handwritten_notes", "hand"),
    ("--user-notes", "user_notes", "mine"),
]


def _add_source_args(parser: argparse.ArgumentParser) -> None:
    for flag, kind, _ in _SOURCE_FLAGS:
        parser.add_argument(flag, action="append", default=[], metavar="FILE", help=f"{kind} (repeatable)")
    parser.add_argument(
        "--handwritten-author",
        choices=["professor", "user", "unknown"],
        default="professor",
        help="who wrote the handwritten notes (default: professor)",
    )
    parser.add_argument("--title", default="", help="lecture title")
    parser.add_argument("--bundle-id", default="lecture")
    parser.add_argument("--bundle", help="use an existing math_material_bundle/1 JSON instead of files")


def _bundle_from_args(args) -> dict:
    if args.bundle:
        return json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    sources = []
    for flag, kind, short in _SOURCE_FLAGS:
        files = getattr(args, flag.lstrip("-").replace("-", "_"))
        for i, path in enumerate(files, start=1):
            material_id = short if len(files) == 1 else f"{short}{i}"
            author = args.handwritten_author if kind == "handwritten_notes" else None
            sources.append(load_source(path, kind, material_id=material_id, author=author))
    if not sources:
        raise MathStudyError("no input: give at least one of " + ", ".join(f for f, _, _ in _SOURCE_FLAGS))
    return build_bundle(sources, title=args.title, bundle_id=args.bundle_id)


def _make_llm(args):
    from .llm import AnthropicLLM, RecordingLLM, ReplayLLM

    if args.replay:
        llm = ReplayLLM(args.replay)
    else:
        llm = AnthropicLLM(model=args.model, effort=args.effort, fallbacks=not args.no_fallbacks)
    if args.out and not args.no_record:
        llm = RecordingLLM(llm, Path(args.out) / "llm")
    return llm


def cmd_run(args) -> int:
    from .orchestrator import Orchestrator, OrchestratorConfig

    bundle = _bundle_from_args(args)
    config = OrchestratorConfig(
        max_attempts=args.max_attempts,
        max_revisions=args.max_revisions,
        use_reviewer=not args.no_reviewer,
    )
    orchestrator = Orchestrator(_make_llm(args), config)
    try:
        result = orchestrator.run(bundle, output_dir=args.out)
    except PipelineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if args.out:
            print(f"run record: {Path(args.out) / 'manifest.json'}", file=sys.stderr)
        return 1

    if args.out:
        print(f"study note: {Path(args.out) / 'study_note.md'}")
    else:
        print(result.markdown)
    summary = result.manifest["quality"]
    print(
        f"status: {result.status} (errors={summary['errors']}, warnings={summary['warnings']})",
        file=sys.stderr,
    )
    return 0 if result.status == "ok" else 2


def cmd_ingest(args) -> int:
    bundle = _bundle_from_args(args)
    text = json.dumps(bundle, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out} ({sum(len(s['chunks']) for s in bundle['sources'])} chunks)")
    else:
        print(text)
    return 0


def cmd_validate(args) -> int:
    payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    errors = validate(payload, args.schema)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"valid: {args.schema or payload.get('schema')}")
    return 0


def cmd_schemas(args) -> int:
    for path in export_schemas(args.directory):
        print(path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    from .llm import DEFAULT_MODEL

    parser = argparse.ArgumentParser(prog="math-study", description="Math Study Agent System")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="analyse materials and write a study note")
    _add_source_args(run)
    run.add_argument("--out", help="run directory for artifacts (JSON per stage, manifest, study_note.md)")
    run.add_argument("--replay", metavar="DIR", help="replay recorded agent outputs instead of calling the API")
    run.add_argument("--no-record", action="store_true", help="do not save raw LLM requests/responses under --out/llm")
    run.add_argument("--model", default=DEFAULT_MODEL)
    run.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    run.add_argument("--no-fallbacks", action="store_true", help="disable server-side refusal fallback")
    run.add_argument("--max-attempts", type=int, default=2)
    run.add_argument("--max-revisions", type=int, default=1)
    run.add_argument("--no-reviewer", action="store_true", help="skip the LLM quality reviewer")
    run.set_defaults(func=cmd_run)

    ingest = sub.add_parser("ingest", help="build the material bundle only")
    _add_source_args(ingest)
    ingest.add_argument("--out")
    ingest.set_defaults(func=cmd_ingest)

    val = sub.add_parser("validate", help="validate a JSON payload against its schema")
    val.add_argument("file")
    val.add_argument("--schema", help="schema id (default: the payload's 'schema' field)")
    val.set_defaults(func=cmd_validate)

    sch = sub.add_parser("schemas", help="export all JSON schemas")
    sch.add_argument("directory")
    sch.set_defaults(func=cmd_schemas)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except MathStudyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
