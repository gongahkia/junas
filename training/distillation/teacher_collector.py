#!/usr/bin/env python3
"""Teacher-verdict collector for the distillation pipeline (item 29 step a).

Walks one or more corpus directories, runs the deterministic engine on each `*.txt`
fixture to get findings, then calls the configured LLM adjudicator (intended to be
provider=openai with both gates set) to get the teacher verdict. Writes a JSONL
dataset that `distill_train.py` consumes.

Dataset row shape:
    {
      "doc_id":              "<labels.json doc_id or filename stem>",
      "text_hash":           "<sha256 of body, the cache key>",
      "document_type":       "...",
      "source_jurisdiction": "SG",
      "destination_jurisdiction": "SG",
      "input_mode":          "raw_text" | "structured_tokens",
      "user_content":        "<exact JSON string the LLM saw as the user turn>",
      "teacher_verdict":     { risk_label, public_status, confidence, ... }
    }

Re-runs are idempotent: rows already present in the output JSONL keyed by text_hash are
skipped unless `--force` is set. Every cloud call is recorded in the privacy ledger
under `${KAYPOH_JOURNAL_DIR}/training_ledger.jsonl` so the auditor can reconstruct
exactly which documents were sent to the teacher and when.

Usage:
    OPENAI_API_KEY=sk-... \\
    KAYPOH_LLM_TENANT_OPT_IN_OPENAI=true \\
    KAYPOH_LLM_ALLOW_REMOTE_BASE_URL=true \\
    python3 training/distillation/teacher_collector.py \\
        --corpus test/fixtures/legal-corpus \\
        --corpus test/fixtures/legal-corpus-adversarial \\
        --output training/distillation/teacher_verdicts.jsonl

    # tests / dry-run paths use --provider mock --output /tmp/dry.jsonl

Exit codes:
    0  collection succeeded; rows written
    1  one or more documents failed; partial dataset on disk
    2  no fixtures found / invalid args
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from kaypoh.review.engine import PreSendReviewEngine  # noqa: E402

DEFAULT_LEDGER_NAME = "training_ledger.jsonl"


@dataclass(frozen=True)
class CorpusDoc:
    doc_id: str
    text: str
    document_type: str
    source_jurisdiction: str
    destination_jurisdiction: str
    corpus_dir: str


def _load_doc(doc_path: Path) -> CorpusDoc:
    labels_path = doc_path.with_suffix(".labels.json")
    labels: dict[str, Any] = {}
    if labels_path.exists():
        try:
            labels = json.loads(labels_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            labels = {}
    return CorpusDoc(
        doc_id=str(labels.get("doc_id", doc_path.stem)),
        text=doc_path.read_text(encoding="utf-8"),
        document_type=str(labels.get("document_type", "generic")),
        source_jurisdiction=str(labels.get("source_jurisdiction", "SG")),
        destination_jurisdiction=str(labels.get("destination_jurisdiction", "SG")),
        corpus_dir=str(doc_path.parent.relative_to(REPO_ROOT)),
    )


def _enumerate_fixtures(corpora: list[Path]) -> list[CorpusDoc]:
    docs: list[CorpusDoc] = []
    for corpus_dir in corpora:
        for doc_path in sorted(corpus_dir.glob("*.txt")):
            docs.append(_load_doc(doc_path))
    return docs


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_findings_payload(findings: list) -> list[dict[str, Any]]:
    """Wire-safe finding summary. Includes the canonical fields the student needs to
    learn from but omits internal id strings (which are deterministic from rule/span
    and so add no information)."""
    return [
        {
            "rule": f.rule,
            "category": f.category,
            "severity": f.severity,
            "jurisdiction": f.jurisdiction,
            "matched_text": f.matched_text,
            "start_char": f.start_char,
            "end_char": f.end_char,
            "reason": f.reason,
        }
        for f in findings
    ]


def _load_existing_hashes(output: Path) -> set[str]:
    if not output.exists():
        return set()
    seen: set[str] = set()
    with output.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            h = row.get("text_hash")
            if isinstance(h, str):
                seen.add(h)
    return seen


def _ledger_path() -> Path:
    journal_dir = Path(os.environ.get("KAYPOH_JOURNAL_DIR", "./kaypoh-journal"))
    return journal_dir / DEFAULT_LEDGER_NAME


def _record_ledger(*, doc_id: str, text_hash: str, status: str, detail: str = "") -> None:
    """One-line append per teacher call. The journal-style format keeps the audit
    trail aligned with the runtime privacy ledger; it is NOT HMAC-chained because
    training-time collection is not a tenant-bearing event — that's deliberate, the
    ledger is for build-time visibility, not for tenant audit-pack export."""
    path = _ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": "teacher_call",
        "doc_id": doc_id,
        "text_hash": text_hash,
        "status": status,
        "detail": detail,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


class TeacherAdjudicator:
    """Wraps a LocalLLMAdjudicator-like object so the collector code paths are
    swappable for the mock adjudicator the tests inject."""

    def __init__(self, adjudicator: Any):
        self.adjudicator = adjudicator

    def adjudicate(self, *, text: str, current_classification: str,
                   findings: list, entity_id: str | None) -> dict[str, Any]:
        # the underlying adjudicator either has the modern signature (accepts findings
        # + entity_id) or the legacy one. catch TypeError to support both.
        try:
            return self.adjudicator.adjudicate(
                text=text,
                current_classification=current_classification,
                findings=findings,
                entity_id=entity_id,
            )
        except TypeError:
            return self.adjudicator.adjudicate(
                text=text,
                current_classification=current_classification,
            )


def _resolve_adjudicator(provider_arg: str) -> TeacherAdjudicator:
    """Build the teacher adjudicator. `--provider mock` is for tests; anything else
    is forwarded to the runtime settings loader so the same env-var / config-file
    plumbing applies as at server runtime."""
    if provider_arg == "mock":
        class _Mock:
            def adjudicate(self, *, text, current_classification, **_):
                return {
                    "status": "adjudicated",
                    "provider": "mock",
                    "model": "mock-teacher",
                    "risk_label": current_classification,
                    "public_status": "ambiguous",
                    "confidence": 0.5,
                    "materiality_reason": "mock teacher placeholder",
                    "matched_public_sources": [],
                    "unverified_claims": [],
                    "review_recommendation": "no escalation (mock)",
                }
        return TeacherAdjudicator(_Mock())

    from kaypoh.advisory.llm_adjudicator.inference import LocalLLMAdjudicator
    from kaypoh.configs.runtime import get_runtime_settings

    settings = get_runtime_settings()
    return TeacherAdjudicator(LocalLLMAdjudicator(settings.llm))


def _build_user_content_for_row(*, input_mode: str, text: str, classification: str,
                                  findings: list, entity_id: str | None) -> str:
    """Build the JSON string the LLM saw on the user turn — store it in the row so
    distill_train.py doesn't have to re-derive it from text. Lazy import keeps the
    runtime-only imports off the test path when provider=mock."""
    from training.distillation.prompts import (
        build_user_content_raw_text,
        build_user_content_structured_tokens,
    )

    if input_mode == "raw_text":
        return build_user_content_raw_text(text=text, current_classification=classification)
    if input_mode == "structured_tokens":
        from kaypoh.advisory.llm_adjudicator.structured_query import (
            build_structured_query,
        )
        query = build_structured_query(
            text=text,
            findings=findings,
            entity_id=entity_id,
            current_classification=classification,
            public_evidence=None,
        )
        return build_user_content_structured_tokens(query)
    raise ValueError(f"unknown input_mode: {input_mode!r}")


def collect(
    *,
    docs: list[CorpusDoc],
    output: Path,
    adjudicator: TeacherAdjudicator,
    input_mode: str,
    force: bool,
    entity_id: str | None = None,
) -> tuple[int, int]:
    """Returns (rows_written, errors). Resumable: skips docs whose text_hash is
    already present in `output` unless `--force` is set."""
    output.parent.mkdir(parents=True, exist_ok=True)
    existing = set() if force else _load_existing_hashes(output)

    engine = PreSendReviewEngine()
    rows_written = 0
    errors = 0
    with output.open("a", encoding="utf-8") as fh:
        for doc in docs:
            text_hash = _text_hash(doc.text)
            if text_hash in existing:
                _record_ledger(
                    doc_id=doc.doc_id, text_hash=text_hash,
                    status="skipped", detail="already collected",
                )
                continue

            try:
                review = engine.review(
                    text=doc.text,
                    source_jurisdiction=doc.source_jurisdiction,
                    destination_jurisdiction=doc.destination_jurisdiction,
                    entity_id=entity_id,
                    include_suggestions=False,
                    document_type=doc.document_type,
                    review_profile="strict",  # deterministic only on this side; teacher fires separately
                )
                verdict = adjudicator.adjudicate(
                    text=doc.text,
                    current_classification=review.overall_risk.value,
                    findings=review.findings,
                    entity_id=entity_id,
                )
                if str(verdict.get("status", "")) == "error":
                    _record_ledger(
                        doc_id=doc.doc_id, text_hash=text_hash,
                        status="teacher_error", detail=str(verdict.get("review_recommendation", "")),
                    )
                    errors += 1
                    continue

                user_content = _build_user_content_for_row(
                    input_mode=input_mode,
                    text=doc.text,
                    classification=review.overall_risk.value,
                    findings=review.findings,
                    entity_id=entity_id,
                )

                row = {
                    "doc_id": doc.doc_id,
                    "text_hash": text_hash,
                    "document_type": doc.document_type,
                    "source_jurisdiction": doc.source_jurisdiction,
                    "destination_jurisdiction": doc.destination_jurisdiction,
                    "corpus_dir": doc.corpus_dir,
                    "input_mode": input_mode,
                    "user_content": user_content,
                    "deterministic_findings": _build_findings_payload(review.findings),
                    "deterministic_classification": review.overall_risk.value,
                    "teacher_verdict": verdict,
                }
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                fh.flush()
                rows_written += 1
                existing.add(text_hash)
                _record_ledger(
                    doc_id=doc.doc_id, text_hash=text_hash,
                    status="collected", detail=verdict.get("provider", ""),
                )
            except Exception as exc:
                _record_ledger(
                    doc_id=doc.doc_id, text_hash=text_hash,
                    status="exception", detail=str(exc)[:200],
                )
                errors += 1
    return rows_written, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect teacher verdicts for distillation")
    parser.add_argument(
        "--corpus", type=Path, action="append", required=True,
        help="corpus dir to walk. repeat for multiple corpora.",
    )
    parser.add_argument(
        "--output", type=Path, required=True,
        help="JSONL output path; appended-to so re-runs are idempotent by text_hash.",
    )
    parser.add_argument(
        "--input-mode", default="raw_text",
        choices=["raw_text", "structured_tokens"],
        help="must match the LLM input mode used at serve time so the student sees the same shape.",
    )
    parser.add_argument(
        "--provider", default="runtime",
        help="`runtime` (default) reads kaypoh.configs.runtime for the adjudicator; "
        "`mock` returns canned verdicts (tests).",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="re-emit rows for every doc, even those already in --output by text_hash.",
    )
    parser.add_argument("--entity-id", default=None, help="optional entity_id passed to the teacher.")
    args = parser.parse_args(argv)

    corpora: list[Path] = []
    for corpus in args.corpus:
        path = corpus if corpus.is_absolute() else (REPO_ROOT / corpus).resolve()
        if not path.exists():
            print(f"corpus missing: {path}", file=sys.stderr)
            return 2
        corpora.append(path)

    docs = _enumerate_fixtures(corpora)
    if not docs:
        print(f"no fixtures found in {[str(c) for c in corpora]}", file=sys.stderr)
        return 2

    output = args.output if args.output.is_absolute() else (REPO_ROOT / args.output).resolve()

    adjudicator = _resolve_adjudicator(args.provider)
    rows, errors = collect(
        docs=docs,
        output=output,
        adjudicator=adjudicator,
        input_mode=args.input_mode,
        force=args.force,
        entity_id=args.entity_id,
    )
    print(json.dumps({
        "rows_written": rows,
        "errors": errors,
        "output": str(output),
        "ledger": str(_ledger_path()),
        "input_mode": args.input_mode,
    }, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
