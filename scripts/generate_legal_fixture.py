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
CORPUS_DIR = REPO_ROOT / "test" / "fixtures" / "legal-corpus"
ADVERSARIAL_DIR = REPO_ROOT / "test" / "fixtures" / "legal-corpus-adversarial"

DOC_TYPES = {
    "spa": "a Singapore-style Share Purchase Agreement (face page only, ~10 lines)",
    "nda": "a Singapore-style Non-Disclosure Agreement (preamble + 2 clauses)",
    "sha": "a Singapore-style Shareholders Agreement face page with 2–3 shareholder lines",
    "term_sheet": "a Series B funding term sheet (10–12 lines, no boilerplate)",
    "memo": "a short internal deal memo using a Project codename for an unannounced acquisition",
    "research_note": "a short equity-research analyst note referencing forthcoming earnings",
    "employment_letter": "a Singapore-style employment offer letter, signatory block + salary line",
}

# document types map to the schema of must_detect labels — the recall gate expects these rule names.
DOC_TYPE_TO_DOC_TYPE_FIELD = {
    "spa": "SPA",
    "nda": "NDA",
    "sha": "SHA",
    "term_sheet": "term_sheet",
    "memo": "memo",
    "research_note": "research_note",
    "employment_letter": "generic",
}


def _build_prompt(doc_type: str, *, adversarial: bool, multilingual: bool) -> tuple[str, str]:
    base_kind = DOC_TYPES[doc_type]
    system = (
        "You are a legal-text fixture generator for a regulated-PII / MNPI detection test "
        "harness. Your outputs are SYNTHETIC: every entity, number, identifier, and address you "
        "produce is fictional, and the document must be obviously a test fixture. Do not use "
        "any real person, real company, real NRIC/FIN, or real UEN. Never produce content that "
        "could be confused with a real legal document. Output only the text of the fixture — no "
        "preamble, no commentary, no markdown fences."
    )
    constraints = [
        f"Draft {base_kind}.",
        "Length: 8–14 lines of plain text.",
        "Include at least one fictional Singapore NRIC of the form S1234567A through S9999999Z.",
        "Include at least one fictional UEN (legacy 9-char or T-format).",
        "Include at least one fictional Singapore phone number (+65 ...).",
        "Include at least one fictional email address ending in .sg.",
        "Include at least one named person with an honorific (Dr / Mr / Ms / Mrs).",
        "If the document type is SPA/SHA/term_sheet/memo, include a fictional financial amount.",
    ]
    if multilingual:
        constraints.append(
            "Mix at least two named persons: one English/Chinese name (e.g. Tan Wei Ming), "
            "one Malay name (e.g. Siti Aishah binti Abdullah), and optionally one Tamil name "
            "(e.g. Ramasamy Muthu). The rest of the body remains English."
        )
    if adversarial:
        constraints.append(
            "Insert at least one obfuscated identifier (e.g. NRIC embedded inside a URL such as "
            "https://example.sg/user/S1234567D, or with non-breaking spaces between digits)."
        )
        constraints.append(
            "Include at least one negative-prose sentence that uses words like 'project plan' or "
            "'project status' in lowercase so that the transaction_codename detector should NOT fire."
        )
        constraints.append(
            "Include at least one defined term abbreviation like (the \"SPA\") immediately "
            "followed later by standalone references to that defined term."
        )
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


def _labels_stub(slug: str, doc_type: str) -> dict:
    return {
        "doc_id": slug,
        "document_type": DOC_TYPE_TO_DOC_TYPE_FIELD[doc_type],
        "source_jurisdiction": "SG",
        "destination_jurisdiction": "SG",
        "must_detect": [],
        "must_not_detect": [],
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
    parser.add_argument("--adversarial", action="store_true", help="Generate adversarial / obfuscated variant")
    parser.add_argument("--multilingual", action="store_true", help="Include multilingual SG names")
    parser.add_argument("--model", default=os.environ.get("KAYPOH_FIXTURE_MODEL", "gpt-4o-mini"))
    parser.add_argument("--dry-run", action="store_true", help="Print prompt only; no network call")
    parser.add_argument("--stdout", action="store_true", help="Print fixture to stdout rather than writing files")
    args = parser.parse_args(argv)

    system, user = _build_prompt(args.doc_type, adversarial=args.adversarial, multilingual=args.multilingual)
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

    target_dir = ADVERSARIAL_DIR if args.adversarial else CORPUS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    txt_path = target_dir / f"{args.slug}.txt"
    labels_path = target_dir / f"{args.slug}.labels.json"
    if txt_path.exists() or labels_path.exists():
        print(f"refusing to overwrite existing fixture: {txt_path}", file=sys.stderr)
        return 1
    txt_path.write_text(body + ("\n" if not body.endswith("\n") else ""), encoding="utf-8")
    labels_path.write_text(
        json.dumps(_labels_stub(args.slug, args.doc_type), indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {txt_path.relative_to(REPO_ROOT)}")
    print(f"wrote {labels_path.relative_to(REPO_ROOT)}")
    print("HAND-REVIEW the labels stub before refreshing recall.lock.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
