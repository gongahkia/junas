#!/usr/bin/env python3
"""Generate quarantine candidate fixtures across jurisdictions and statutory concepts."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.fixture_taxonomy import CONCEPTS, DOC_TYPES, JURISDICTIONS  # noqa: E402
from scripts.generate_legal_fixture import main as generate_one  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "test" / "fixtures" / "legal-corpus-candidates"
DEFAULT_DOC_TYPES = ("memo", "term_sheet", "privacy_notice", "incident_report")
DEFAULT_VARIANTS = ("default", "adversarial", "negative")


def _expand(raw: str, choices: dict | tuple[str, ...], *, default: tuple[str, ...]) -> tuple[str, ...]:
    value = raw.strip()
    if not value:
        return default
    if value == "all":
        return tuple(choices)
    allowed = set(choices)
    out = tuple(part.strip() for part in value.split(",") if part.strip())
    invalid = sorted(set(out) - allowed)
    if invalid:
        raise ValueError(f"invalid values: {', '.join(invalid)}")
    return out


def _next_slug(out_dir: Path, jurisdiction: str, concept: str, doc_type: str, variant: str) -> str:
    prefix = f"{jurisdiction.lower()}_{concept}_{doc_type}_{variant}"
    idx = 1
    while (out_dir / jurisdiction.lower() / concept / f"{prefix}_{idx:03d}.txt").exists():
        idx += 1
    return f"{prefix}_{idx:03d}"


def _run_one(
    *,
    jurisdiction: str,
    concept: str,
    doc_type: str,
    variant: str,
    out_dir: Path,
    model: str,
    dry_run: bool,
) -> int:
    slug = _next_slug(out_dir, jurisdiction, concept, doc_type, variant)
    argv = [
        doc_type,
        "--slug",
        slug,
        "--jurisdiction",
        jurisdiction,
        "--concept",
        concept,
        "--variant",
        variant,
        "--candidate",
        "--out-dir",
        str(out_dir / jurisdiction.lower() / concept),
        "--model",
        model,
    ]
    if dry_run:
        print(" ".join(["generate_legal_fixture.py", *argv, "--dry-run"]))
        return 0
    return generate_one(argv)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate jurisdiction-wide candidate fixture corpus")
    parser.add_argument("--jurisdictions", default="all", help="comma list or all")
    parser.add_argument("--concepts", default="all", help="comma list or all")
    parser.add_argument("--doc-types", default=",".join(DEFAULT_DOC_TYPES), help="comma list or all")
    parser.add_argument("--variants", default=",".join(DEFAULT_VARIANTS), help="comma list")
    parser.add_argument("--count", type=int, default=1, help="fixtures per matrix cell")
    parser.add_argument("--model", default=os.environ.get("KAYPOH_FIXTURE_MODEL", "gpt-4o"))
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true", help="print planned generation calls only")
    args = parser.parse_args(argv)

    try:
        jurisdictions = _expand(args.jurisdictions, JURISDICTIONS, default=tuple(JURISDICTIONS))
        concepts = _expand(args.concepts, CONCEPTS, default=tuple(CONCEPTS))
        doc_types = _expand(args.doc_types, DOC_TYPES, default=DEFAULT_DOC_TYPES)
        variants = _expand(
            args.variants,
            ("default", "adversarial", "multilingual", "negative"),
            default=DEFAULT_VARIANTS,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.count < 1:
        print("--count must be >= 1", file=sys.stderr)
        return 2
    if not args.dry_run and not os.environ.get("OPENAI_API_KEY", "").strip():
        print("OPENAI_API_KEY is not set", file=sys.stderr)
        return 2

    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    ok = failed = 0
    t0 = time.monotonic()
    for jurisdiction in jurisdictions:
        for concept in concepts:
            for doc_type in doc_types:
                for variant in variants:
                    for _ in range(args.count):
                        rc = _run_one(
                            jurisdiction=jurisdiction,
                            concept=concept,
                            doc_type=doc_type,
                            variant=variant,
                            out_dir=out_dir,
                            model=args.model,
                            dry_run=args.dry_run,
                        )
                        if rc == 0:
                            ok += 1
                        else:
                            failed += 1
    elapsed = int(time.monotonic() - t0)
    print(f"candidate generation summary: ok={ok} failed={failed} elapsed={elapsed}s")
    if not args.dry_run:
        print("candidate fixtures are quarantine-only; human review is required before lock promotion.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
