#!/usr/bin/env python3
"""Synthetic legal-contract fixture generator. Build-time only — never touches customer data.

Wraps the OpenAI chat-completions API to draft a short legal-style fixture for the kaypoh
recall-gate corpus. Prints the draft text + a labels.json stub to stdout, or writes both to
`test/fixtures/legal-corpus/` (default) or `test/fixtures/legal-corpus-adversarial/` (when
`--adversarial` is set). Hand-review is mandatory before the labels.json is committed.

Usage:
    OPENAI_API_KEY=... python3 scripts/generate_legal_fixture.py spa --slug spa_02
    OPENAI_API_KEY=... python3 scripts/generate_legal_fixture.py memo --adversarial --slug memo_obfuscated_01

Document types: spa, nda, sha, term_sheet, memo, employment_letter, research_note

The `--multilingual` flag asks the model to include SG-realistic Mandarin, Bahasa Melayu, and
Tamil names alongside English text. The `--adversarial` flag asks for obfuscated PII (NRIC in
URLs, ZWJ chars, broken DOCX-style runs, OCR ligature artefacts) plus negative prose so the
precision gate has signal.

No network call is made when --dry-run is set; the prompt is printed instead.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.fixture_taxonomy import (  # noqa: E402
    CONCEPTS,
    DOC_TYPE_TO_FIELD,
    DOC_TYPES,
    JURISDICTIONS,
    concept_prompt,
    jurisdiction_prompt,
)

CORPUS_DIR = REPO_ROOT / "test" / "fixtures" / "legal-corpus"
ADVERSARIAL_DIR = REPO_ROOT / "test" / "fixtures" / "legal-corpus-adversarial"
CANDIDATE_DIR = REPO_ROOT / "test" / "fixtures" / "legal-corpus-candidates"


def _variant_notes(*, adversarial: bool, multilingual: bool, variant: str) -> list[str]:
    notes: list[str] = []
    if variant == "negative":
        notes.append("Bias the document toward false-positive bait and benign uses of risky vocabulary.")
    elif variant == "multilingual":
        multilingual = True
    elif variant == "adversarial":
        adversarial = True
    if multilingual:
        notes.append(
            "Include local realistic names and at least one non-English or mixed-script surface where natural."
        )
    if adversarial:
        notes.append(
            "Include obfuscated identifiers, broken line runs, OCR-like spacing, or URL-embedded values."
        )
        notes.append(
            "Include negative bait that should not be detected, such as negated MAC language, public-source "
            "references, lowercase project-management prose, product names, or generic policy text."
        )
    return notes


def _concept_generation_notes(concept: str) -> list[str]:
    if concept == "direct_identifiers":
        return [
            "Include at least two direct identifiers: one jurisdiction-local ID/company/tax identifier and one "
            "universal contact/account identifier.",
            "Include one invalid, public, or generic identifier-shaped bait item that should test precision.",
        ]
    if concept == "special_category":
        return [
            "Anchor sensitive data to a fictional person and include at least two categories such as health, "
            "biometric, genetic, religious, union, political, sexual-orientation, or minor data.",
            "Include one benign phrase that reuses sensitive vocabulary without describing a person's sensitive data.",
        ]
    if concept == "privacy_events":
        return [
            "Include at least two privacy workflow events such as cross-border transfer, consent withdrawal, DSAR, "
            "erasure, retention, or minimisation.",
            "Include one completed, negated, or policy-only control statement that should test precision.",
        ]
    if concept == "universal_mnpi":
        return [
            "Include at least two universal market-sensitive signals such as a deal codename, non-public marker, "
            "definitive agreement, embargo date, financial amount, percentage, or MAC/MAE clause.",
            "Include one public-source, stale, lowercase project-management, or negated MAC sentence.",
        ]
    if concept == "jurisdictional_mnpi":
        return [
            "Use the local exchange/regulator vocabulary for non-public/public-status or disclosure timing.",
            "Include one local public-filing or already-announced reference that should test public-status precision.",
        ]
    if concept == "sector_mnpi":
        return [
            "Include at least two sector-sensitive signals from cyber, crypto/DPT, ESG/climate, insider lists, "
            "information barriers, commercial terms, blackout windows, tipping, or selective disclosure.",
            "Include one educational, marketing, or operations-only sentence that reuses sector vocabulary benignly.",
        ]
    if concept == "quasi_identifiers":
        return [
            "Create a linkable cluster of weak identifiers around one fictional person, such as DOB/age, role, "
            "employer, device, location, account, or session reference.",
            "Include similar weak identifiers separated from any person so the corpus tests over-detection.",
        ]
    return []


def _build_prompt(
    doc_type: str,
    *,
    adversarial: bool,
    multilingual: bool,
    jurisdiction: str = "SG",
    concept: str = "universal_mnpi",
    variant: str = "default",
) -> tuple[str, str]:
    base_kind = DOC_TYPES[doc_type]
    system = (
        "You are a legal/finance fixture generator for evaluating PII and MNPI coverage. "
        "Generate useful synthetic test documents, not documents designed to placate an existing detector. "
        "Every person, organisation, identifier, address, account, and transaction must be fictional. "
        "Do not use real companies, real people, real securities identifiers, or real government IDs. "
        "Output only the fixture body: no preamble, no commentary, no markdown fences."
    )
    constraints = [
        f"Jurisdiction context:\n{jurisdiction_prompt(jurisdiction)}",
        f"Coverage concept:\n{concept_prompt(concept)}",
        f"Draft {base_kind}.",
        "Length: 10–18 lines of plain text.",
        "Make the fixture realistic enough to evaluate legal/compliance coverage.",
        "Include at least one fictional named person with an honorific.",
        "Include at least one fictional organisation and one fictional email/contact channel.",
        "Use jurisdiction-local terminology, regulator/exchange context, and document conventions where relevant.",
        "Include both straightforward signals and at least one subtle contextual signal.",
        "Include at least one benign or negative sentence that should help evaluate precision.",
        "Do not mention Kaypoh, tests, labels, detector rules, or expected outputs.",
    ]
    constraints.extend(_concept_generation_notes(concept))
    constraints.extend(_variant_notes(adversarial=adversarial, multilingual=multilingual, variant=variant))
    user = (
        "Generate a synthetic legal fixture.\n\n"
        + "\n".join(f"- {c}" for c in constraints)
        + "\n\nReturn only the document body."
    )
    return system, user


class FixtureGenerationError(RuntimeError):
    """Raised when the OpenAI call fails or returns an unexpected payload shape."""


def _call_openai(system: str, user: str, *, model: str, api_key: str) -> str:
    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.7,
            },
            timeout=60.0,
        )
    except httpx.HTTPError as exc:
        raise FixtureGenerationError(f"network error calling OpenAI: {exc}") from exc
    if response.status_code >= 400:
        # surface the API's own error body — usually the actionable thing (model misnamed,
        # rate-limited, key revoked).
        raise FixtureGenerationError(
            f"OpenAI returned {response.status_code}: {response.text[:500]}"
        )
    try:
        payload = response.json()
        return payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as exc:
        raise FixtureGenerationError(
            f"unexpected OpenAI response shape: {response.text[:500]!r}"
        ) from exc


def _labels_stub(
    slug: str,
    doc_type: str,
    *,
    jurisdiction: str,
    concept: str,
    prompt_version: str,
    human_review_status: str,
) -> dict:
    return {
        "doc_id": slug,
        "document_type": DOC_TYPE_TO_FIELD[doc_type],
        "source_jurisdiction": jurisdiction,
        "destination_jurisdiction": jurisdiction,
        "must_detect": [],
        "must_not_detect": [],
        "uncertain": [],
        "_taxonomy_concept": concept,
        "_taxonomy_version": "architecture-pivot-2026-05-26",
        "_prompt_version": prompt_version,
        "_human_review_status": human_review_status,
        "_generation_note": (
            "AUTO-GENERATED STUB. A reviewer must hand-fill must_detect / must_not_detect "
            "by inspecting the fixture text before this file is committed and before the "
            "recall.lock baseline is refreshed."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthetic legal-fixture generator")
    parser.add_argument("doc_type", choices=sorted(DOC_TYPES), help="Document type to generate")
    parser.add_argument("--slug", required=False, help="Output slug (e.g., spa_02). Required unless --dry-run.")
    parser.add_argument("--jurisdiction", choices=sorted(JURISDICTIONS), default="SG")
    parser.add_argument("--concept", choices=sorted(CONCEPTS), default="universal_mnpi")
    parser.add_argument(
        "--variant",
        choices=("default", "adversarial", "multilingual", "negative"),
        default="default",
        help="Prompt variant. Legacy --adversarial/--multilingual are still accepted.",
    )
    parser.add_argument("--adversarial", action="store_true", help="Generate adversarial / obfuscated variant")
    parser.add_argument("--multilingual", action="store_true", help="Include multilingual SG names")
    parser.add_argument("--model", default=os.environ.get("KAYPOH_FIXTURE_MODEL", "gpt-4o-mini"))
    parser.add_argument("--candidate", action="store_true", help="Write to candidate quarantine corpus")
    parser.add_argument("--out-dir", type=Path, help="Override output directory")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt only; no network call")
    parser.add_argument("--stdout", action="store_true", help="Print fixture to stdout rather than writing files")
    args = parser.parse_args(argv)

    prompt_version = "jurisdiction-taxonomy-v1"
    system, user = _build_prompt(
        args.doc_type,
        adversarial=args.adversarial,
        multilingual=args.multilingual,
        jurisdiction=args.jurisdiction,
        concept=args.concept,
        variant=args.variant,
    )
    if args.dry_run:
        print("=== system ===")
        print(system)
        print("\n=== user ===")
        print(user)
        return 0

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("OPENAI_API_KEY is not set", file=sys.stderr)
        return 2

    try:
        body = _call_openai(system, user, model=args.model, api_key=api_key)
    except FixtureGenerationError as exc:
        print(f"fixture generation failed: {exc}", file=sys.stderr)
        return 1

    if args.stdout or not args.slug:
        print(body)
        return 0

    if args.out_dir:
        target_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    elif args.candidate:
        target_dir = CANDIDATE_DIR / args.jurisdiction.lower() / args.concept
    else:
        target_dir = ADVERSARIAL_DIR if args.adversarial or args.variant == "adversarial" else CORPUS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    txt_path = target_dir / f"{args.slug}.txt"
    labels_path = target_dir / f"{args.slug}.labels.json"
    if txt_path.exists() or labels_path.exists():
        print(f"refusing to overwrite existing fixture: {txt_path}", file=sys.stderr)
        return 1
    txt_path.write_text(body + ("\n" if not body.endswith("\n") else ""), encoding="utf-8")
    labels_path.write_text(
        json.dumps(
            _labels_stub(
                args.slug,
                args.doc_type,
                jurisdiction=args.jurisdiction,
                concept=args.concept,
                prompt_version=prompt_version,
                human_review_status="pending" if args.candidate else "unreviewed",
            ),
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {txt_path.relative_to(REPO_ROOT)}")
    print(f"wrote {labels_path.relative_to(REPO_ROOT)}")
    print("HAND-REVIEW the labels stub before refreshing recall.lock.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
