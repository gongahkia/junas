"""Command-line entrypoint for classifier experiments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from junas.configs.runtime import get_runtime_settings
from junas.pipeline import ReviewPipeline


def _dict_finding(**kwargs: object) -> dict[str, object]:
    return kwargs


def run_rules_test(args: argparse.Namespace, *, stdout: TextIO | None = None) -> int:
    if stdout is None:
        stdout = sys.stdout
    try:
        from junas.review.secret_rulepacks import (
            SecretRulePackError,
            detect_secret_findings,
            load_gitleaks_rule_pack,
        )

        pack_path = Path(args.gitleaks).expanduser()
        text = args.text if args.text_file is None else Path(args.text_file).expanduser().read_text(encoding="utf-8")
        pack = load_gitleaks_rule_pack(pack_path)
        findings = detect_secret_findings(
            text=text,
            rule_packs=(pack,),
            jurisdiction=args.jurisdiction,
            idx_start=0,
            new_finding=_dict_finding,
            max_matches=args.max_matches,
        )
    except (OSError, SecretRulePackError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        payload = {"pack": str(pack_path), "findings": findings}
        stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return 0
    lines = [
        "Junas rules test",
        f"pack: {pack_path}",
        f"findings: {len(findings)}",
    ]
    for finding in findings:
        lines.append(
            f"- {finding['rule']} {finding['severity']} {finding['matched_text']} ({finding['start']}:{finding['end']})"
        )
    stdout.write("\n".join(lines) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Junas PII/MNPI classifier research tools")
    commands = parser.add_subparsers(dest="command", required=True)
    classify = commands.add_parser("classify", help="Analyze local text or a document and emit JSON")
    inputs = classify.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--text", help="Inline text; use --file - to read standard input")
    inputs.add_argument("--file", help="Document path, or - for text on standard input")
    classify.add_argument("--source-jurisdiction", default="SG")
    classify.add_argument("--destination-jurisdiction")
    classify.add_argument("--document-type", default="generic")
    classify.add_argument("--entity-id")
    classify.add_argument("--profile", choices=("strict", "audit_grade"), default="strict")
    classify.add_argument("--config", type=Path)
    rules = commands.add_parser("rules", help="Evaluate a local secret rule pack")
    rule_commands = rules.add_subparsers(dest="rules_command", required=True)
    rules_test = rule_commands.add_parser("test", help="Run a Gitleaks TOML pack against a text fixture")
    rules_test.add_argument("--gitleaks", required=True)
    rule_inputs = rules_test.add_mutually_exclusive_group(required=True)
    rule_inputs.add_argument("--text")
    rule_inputs.add_argument("--text-file")
    rules_test.add_argument("--jurisdiction", default="US")
    rules_test.add_argument("--max-matches", type=int, default=64)
    rules_test.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "rules":
        return run_rules_test(args)
    try:
        settings = get_runtime_settings({"config_path": args.config} if args.config else None)
        pipeline = ReviewPipeline(settings)
        options = {
            "source_jurisdiction": args.source_jurisdiction,
            "destination_jurisdiction": args.destination_jurisdiction,
            "document_type": args.document_type,
            "entity_id": args.entity_id,
            "review_profile": args.profile,
        }
        if args.file == "-":
            result = pipeline.review_text(sys.stdin.read(), **options)
        elif args.file:
            result = pipeline.review_file(args.file, **options)
        else:
            result = pipeline.review_text(args.text, **options)
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 1 if result.review.degraded_modes else 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"classification failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
