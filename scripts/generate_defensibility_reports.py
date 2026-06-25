#!/usr/bin/env python3
"""Generate per-jurisdiction defensibility reports from runtime rule packs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from junas.review import jurisdictions  # noqa: E402

DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "defensibility"
GENERATED_ON = "2026-06-06"


def _format_list(values: list[str] | tuple[str, ...], *, empty: str) -> str:
    if not values:
        return f"- {empty}\n"
    return "".join(f"- {value}\n" for value in values)


def _recognizer_rows(pack: jurisdictions.JurisdictionRulePack) -> str:
    if not pack.recognizers:
        return (
            "| Rule | Severity | Defensible basis |\n"
            "| --- | --- | --- |\n"
            "| None | n/a | Baseline pack relies on universal detectors. |\n"
        )
    rows = ["| Rule | Severity | Defensible basis |", "| --- | --- | --- |"]
    for recognizer in pack.recognizers:
        rows.append(f"| `{recognizer.rule_name}` | {recognizer.severity} | {recognizer.reason} |")
    return "\n".join(rows) + "\n"


def render_report(pack: jurisdictions.JurisdictionRulePack) -> str:
    baseline_note = (
        "\nSEA is the regional baseline pack: it gives Southeast Asia routing a statutory baseline "
        "when a more specific local pack is not selected.\n"
        if pack.code == "SEA"
        else ""
    )
    return (
        f"# {pack.label} ({pack.code}) Defensibility Report\n\n"
        f"> Generated {GENERATED_ON} from `src/junas/review/jurisdictions_data/{pack.code}.toml`. "
        "Internal benchmarking and procurement-support artifact only; not legal advice.\n"
        f"{baseline_note}\n"
        "## Statutory Coverage\n\n"
        "Companion coverage source: `docs/statutory-coverage.md`. Runtime statutory references:\n\n"
        f"{_format_list(pack.references, empty='No pack-specific references; customer baseline only.')}\n"
        "Runtime PII rule families:\n\n"
        f"{_format_list(pack.pii_rules, empty='Universal PII detectors only.')}\n"
        "Runtime MNPI rule families:\n\n"
        f"{_format_list(pack.mnpi_rules, empty='Universal MNPI detectors only.')}\n"
        "Jurisdiction-local recognizers:\n\n"
        f"{_recognizer_rows(pack)}\n"
        "## Known Gaps\n\n"
        "- Deterministic strict-mode reports are detector evidence, not a legal conclusion.\n"
        "- `audit_grade` public-source retrieval and LLM adjudication may be required for public-status, "
        "materiality, safe-harbour, and domain-inference questions.\n"
        "- Candidate `.bucket.json` sidecars are internal benchmarking review artifacts, not procurement-grade "
        "legal truth.\n"
        "- Customer citation overrides can change the cited internal policy without changing detector recall.\n\n"
        "## Operational Controls\n\n"
        "- Review responses expose per-finding `source_verification` and detector `metadata` where applicable.\n"
        "- HMAC journal and audit-pack export provide tamper-evident reviewer decisions and pack manifests.\n"
        "- `/pseudonymize` is reversible and may persist mappings when explicitly enabled; `/anonymize` is "
        "irreversible placeholder-only; `/redact` emits opaque markers without reidentification material.\n"
        "- Sanitized reviewer action rates are aggregated by rule in audit packs; raw reviewer rationale and "
        "raw document text are not added to defensibility manifests.\n\n"
        "## Pack Manifest\n\n"
        f"- Jurisdiction code: `{pack.code}`\n"
        f"- Label: {pack.label}\n"
        f"- Recognizer count: {len(pack.recognizers)}\n"
        f"- PII family count: {len(pack.pii_rules)}\n"
        f"- MNPI family count: {len(pack.mnpi_rules)}\n"
    )


def generate(output_dir: Path) -> list[Path]:
    jurisdictions.reload_registry()
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for code, pack in sorted(jurisdictions.RULE_PACKS.items()):
        path = output_dir / f"{code}.md"
        path.write_text(render_report(pack), encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate jurisdiction defensibility reports")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    written = generate(args.output_dir if args.output_dir.is_absolute() else REPO_ROOT / args.output_dir)
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
