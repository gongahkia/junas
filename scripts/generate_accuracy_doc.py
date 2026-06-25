#!/usr/bin/env python3
"""Generate docs/accuracy.md from committed recall/precision lock files."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "docs" / "accuracy.md"


@dataclass(frozen=True)
class CorpusSpec:
    name: str
    path: Path
    lock_name: str
    description: str
    optional: bool = False


CORPORA = (
    CorpusSpec(
        name="default legal corpus",
        path=ROOT / "test" / "fixtures" / "legal-corpus",
        lock_name="recall.lock.json",
        description="Hand-labelled SG/legal-contract seed corpus.",
    ),
    CorpusSpec(
        name="adversarial corpus",
        path=ROOT / "test" / "fixtures" / "legal-corpus-adversarial",
        lock_name="recall_adversarial.lock.json",
        description="Negative, obfuscated, and multilingual probes.",
    ),
    CorpusSpec(
        name="SEA jurisdiction corpus",
        path=ROOT / "test" / "fixtures" / "legal-corpus-sea",
        lock_name="legal-corpus-sea.lock.json",
        description="Seed local-ID fixtures for MY, ID, TH, PH, and VN.",
    ),
    CorpusSpec(
        name="HK/AU/JP/KR jurisdiction corpus",
        path=ROOT / "test" / "fixtures" / "legal-corpus-hk-au-jp-kr",
        lock_name="legal-corpus-hk-au-jp-kr.lock.json",
        description="Seed local-ID fixtures for HK, AU, JP, and KR.",
    ),
    CorpusSpec(
        name="reviewed candidate corpus",
        path=ROOT / "test" / "fixtures" / "legal-corpus-reviewed-candidates",
        lock_name="legal-corpus-reviewed-candidates.lock.json",
        description="Human-approved candidate fixtures promoted into recall-lock form.",
        optional=True,
    ),
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture_count(corpus_dir: Path) -> int:
    return len(sorted(corpus_dir.glob("*.txt")))


def _fmt_score(value: float | None) -> str:
    if value is None:
        return "not locked"
    return f"{value:.4f}"


def render_accuracy_doc() -> str:
    lines: list[str] = [
        "# Junas Detector Accuracy",
        "",
        "This file is generated from committed recall and precision locks. Do not edit it by hand.",
        "",
        "## Endpoint Data States",
        "",
        "| Endpoint | Data state | Mapping retained | Accuracy caveat |",
        "|---|---|---|---|",
        "| `/pseudonymize` | Pseudonymised personal data | Yes | "
        "Detector baselines describe span detection before reversible replacement; "
        "output remains re-identifiable where the controller holds the mapping. |",
        "| `/anonymize` | Placeholder-only anonymised text | No | "
        "Detector baselines do not prove statistical anonymisation; residual "
        "singling-out/linkability/inference risk remains document-context dependent. |",
        "| `/redact` | Opaque redacted text | No | "
        "Detector baselines describe what was found for redaction; residual risk "
        "depends on unredacted context and container metadata handling. |",
        "",
        "## Corpus Locks",
        "",
        "| Corpus | Fixtures | Lock file | Description |",
        "|---|---:|---|---|",
    ]

    corpus_payloads: list[tuple[CorpusSpec, dict[str, Any], int]] = []
    for spec in CORPORA:
        lock_path = spec.path / spec.lock_name
        if spec.optional and (not spec.path.is_dir() or not lock_path.is_file()):
            continue
        payload = _load_json(lock_path)
        count = _fixture_count(spec.path)
        corpus_payloads.append((spec, payload, count))
        rel_lock = lock_path.relative_to(ROOT)
        lines.append(f"| {spec.name} | {count} | `{rel_lock}` | {spec.description} |")

    lines.extend(
        [
            "",
            "## Per-Detector Baselines",
            "",
            "| Corpus | Fixtures | Detector | Recall | Precision |",
            "|---|---:|---|---:|---:|",
        ]
    )
    for spec, payload, count in corpus_payloads:
        recall = dict(payload.get("baseline_recall", {}))
        precision = dict(payload.get("baseline_precision", {}))
        for rule in sorted(set(recall) | set(precision)):
            lines.append(
                f"| {spec.name} | {count} | `{rule}` | "
                f"{_fmt_score(recall.get(rule))} | {_fmt_score(precision.get(rule))} |"
            )

    lines.extend(
        [
            "",
            "## Known Limitations",
            "",
            "- These are locked regression baselines over small, hand-labelled fixture corpora; "
            "they are not population-level accuracy claims.",
            "- `not locked` means that corpus currently gates recall only for that detector.",
            "- Public-evidence matching and LLM adjudication accuracy are not included in these "
            "deterministic detector locks.",
            "- New detectors should not be represented as available until matching recall and "
            "precision locks are committed.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate docs/accuracy.md from lock files")
    parser.add_argument("--check", action="store_true", help="fail if output differs from docs/accuracy.md")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="destination markdown file")
    args = parser.parse_args(argv)

    rendered = render_accuracy_doc()
    output = args.output
    if args.check:
        current = output.read_text(encoding="utf-8") if output.exists() else ""
        if current != rendered:
            print(f"{output} is stale; run scripts/generate_accuracy_doc.py", file=sys.stderr)
            return 1
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
