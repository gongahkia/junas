#!/usr/bin/env python3
"""Generate quarantine candidate fixtures across jurisdictions and statutory concepts."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.fixture_taxonomy import CONCEPTS, DOC_TYPES, JURISDICTIONS  # noqa: E402
from scripts.generate_legal_fixture import main as generate_one  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "test" / "fixtures" / "legal-corpus-candidates"
DEFAULT_DOC_TYPES = ("memo", "term_sheet", "privacy_notice", "incident_report")
DEFAULT_VARIANTS = ("default", "adversarial", "negative")
SATURATION_PROFILE = "saturation-4284"
PROFILE_CHOICES = ("custom", SATURATION_PROFILE)


@dataclass(frozen=True)
class CandidatePlanItem:
    jurisdiction: str
    concept: str
    doc_type: str
    variant: str
    slug: str
    txt_path: str
    labels_path: str


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


def _prefix(jurisdiction: str, concept: str, doc_type: str, variant: str) -> str:
    return f"{jurisdiction.lower()}_{concept}_{doc_type}_{variant}"


def _cell_dir(out_dir: Path, jurisdiction: str, concept: str) -> Path:
    return out_dir / jurisdiction.lower() / concept


def _existing_indices(out_dir: Path, jurisdiction: str, concept: str, doc_type: str, variant: str) -> set[int]:
    cell_dir = _cell_dir(out_dir, jurisdiction, concept)
    prefix = _prefix(jurisdiction, concept, doc_type, variant)
    indices: set[int] = set()
    for path in cell_dir.glob(f"{prefix}_*.txt"):
        suffix = path.stem.removeprefix(f"{prefix}_")
        if suffix.isdigit():
            indices.add(int(suffix))
    return indices


def _slug_for(jurisdiction: str, concept: str, doc_type: str, variant: str, index: int) -> str:
    return f"{_prefix(jurisdiction, concept, doc_type, variant)}_{index:03d}"


def _next_slug(out_dir: Path, jurisdiction: str, concept: str, doc_type: str, variant: str) -> str:
    prefix = f"{jurisdiction.lower()}_{concept}_{doc_type}_{variant}"
    idx = 1
    while (out_dir / jurisdiction.lower() / concept / f"{prefix}_{idx:03d}.txt").exists():
        idx += 1
    return f"{prefix}_{idx:03d}"


def _plan_cell(
    *,
    out_dir: Path,
    jurisdiction: str,
    concept: str,
    doc_type: str,
    variant: str,
    target_count: int,
) -> list[CandidatePlanItem]:
    existing = _existing_indices(out_dir, jurisdiction, concept, doc_type, variant)
    planned: list[CandidatePlanItem] = []
    for idx in range(1, target_count + 1):
        if idx in existing:
            continue
        slug = _slug_for(jurisdiction, concept, doc_type, variant, idx)
        cell_dir = _cell_dir(out_dir, jurisdiction, concept)
        planned.append(
            CandidatePlanItem(
                jurisdiction=jurisdiction,
                concept=concept,
                doc_type=doc_type,
                variant=variant,
                slug=slug,
                txt_path=str(cell_dir / f"{slug}.txt"),
                labels_path=str(cell_dir / f"{slug}.labels.json"),
            )
        )
    return planned


def plan_candidate_matrix(
    *,
    out_dir: Path,
    jurisdictions: tuple[str, ...],
    concepts: tuple[str, ...],
    doc_types: tuple[str, ...],
    variants: tuple[str, ...],
    target_count: int,
) -> list[CandidatePlanItem]:
    plan: list[CandidatePlanItem] = []
    for jurisdiction in jurisdictions:
        for concept in concepts:
            for doc_type in doc_types:
                for variant in variants:
                    plan.extend(
                        _plan_cell(
                            out_dir=out_dir,
                            jurisdiction=jurisdiction,
                            concept=concept,
                            doc_type=doc_type,
                            variant=variant,
                            target_count=target_count,
                        )
                    )
    return plan


def expected_matrix_size(
    *,
    jurisdictions: tuple[str, ...],
    concepts: tuple[str, ...],
    doc_types: tuple[str, ...],
    variants: tuple[str, ...],
    target_count: int,
) -> int:
    return len(jurisdictions) * len(concepts) * len(doc_types) * len(variants) * target_count


def _manifest_dir(raw: Path | None) -> Path:
    if raw:
        return raw if raw.is_absolute() else REPO_ROOT / raw
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    return Path(f"/tmp/kaypoh-candidate-run-{stamp}")


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def _run_one(
    *,
    item: CandidatePlanItem,
    model: str,
    dry_run: bool,
) -> int:
    argv = [
        item.doc_type,
        "--slug",
        item.slug,
        "--jurisdiction",
        item.jurisdiction,
        "--concept",
        item.concept,
        "--variant",
        item.variant,
        "--candidate",
        "--out-dir",
        str(Path(item.txt_path).parent),
        "--model",
        model,
    ]
    if dry_run:
        print(" ".join(["generate_legal_fixture.py", *argv, "--dry-run"]))
        return 0
    return generate_one(argv)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate jurisdiction-wide candidate fixture corpus")
    parser.add_argument(
        "--profile",
        choices=PROFILE_CHOICES,
        default="custom",
        help="named matrix preset; saturation-4284 = 17 jurisdictions x 7 concepts x 4 docs x 3 variants x 3",
    )
    parser.add_argument("--jurisdictions", default="all", help="comma list or all")
    parser.add_argument("--concepts", default="all", help="comma list or all")
    parser.add_argument("--doc-types", default=",".join(DEFAULT_DOC_TYPES), help="comma list or all")
    parser.add_argument("--variants", default=",".join(DEFAULT_VARIANTS), help="comma list")
    parser.add_argument("--count", type=int, default=1, help="target fixtures per matrix cell")
    parser.add_argument("--model", default=os.environ.get("KAYPOH_FIXTURE_MODEL", "gpt-4o"))
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        help="write generation JSONL manifests here (default for real runs: /tmp/kaypoh-candidate-run-*)",
    )
    parser.add_argument("--dry-run", action="store_true", help="print planned generation calls only")
    args = parser.parse_args(argv)

    if args.profile == SATURATION_PROFILE:
        args.jurisdictions = "all"
        args.concepts = "all"
        args.doc_types = ",".join(DEFAULT_DOC_TYPES)
        args.variants = ",".join(DEFAULT_VARIANTS)
        args.count = 3

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
    plan = plan_candidate_matrix(
        out_dir=out_dir,
        jurisdictions=jurisdictions,
        concepts=concepts,
        doc_types=doc_types,
        variants=variants,
        target_count=args.count,
    )
    expected = expected_matrix_size(
        jurisdictions=jurisdictions,
        concepts=concepts,
        doc_types=doc_types,
        variants=variants,
        target_count=args.count,
    )
    print(
        "candidate generation plan: "
        f"profile={args.profile} expected={expected} existing_or_complete={expected - len(plan)} "
        f"planned={len(plan)}",
        flush=True,
    )

    manifest_dir = _manifest_dir(args.manifest_dir) if args.manifest_dir or not args.dry_run else None
    if manifest_dir:
        manifest_name = "generation_plan.jsonl" if args.dry_run else "generation_manifest.jsonl"
        manifest_path = manifest_dir / manifest_name
        for item in plan:
            _append_jsonl(manifest_path, {"event": "planned", **asdict(item)})
        print(f"wrote generation plan manifest: {manifest_path}", flush=True)

    ok = failed = 0
    t0 = time.monotonic()
    for item in plan:
        rc = _run_one(
            item=item,
            model=args.model,
            dry_run=args.dry_run,
        )
        if rc == 0:
            ok += 1
            if manifest_dir and not args.dry_run:
                _append_jsonl(manifest_dir / "generation_manifest.jsonl", {"event": "generated", **asdict(item)})
        else:
            failed += 1
            if manifest_dir and not args.dry_run:
                _append_jsonl(
                    manifest_dir / "generation_manifest.jsonl",
                    {"event": "failed", "returncode": rc, **asdict(item)},
                )
    elapsed = int(time.monotonic() - t0)
    print(f"candidate generation summary: ok={ok} failed={failed} skipped={expected - len(plan)} elapsed={elapsed}s")
    if not args.dry_run:
        print("candidate fixtures are quarantine-only; human review is required before lock promotion.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
