#!/usr/bin/env python3
"""Run local accuracy measurements and unchanged regression locks; never relabel or update locks."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.check_precision_risk import DEFAULT_CORPORA, _lock_path_for  # noqa: E402
from scripts.evaluate_candidate_corpus import _evaluate_one, _summary  # noqa: E402


def fingerprint(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def evaluate_corpus(corpus: Path) -> dict[str, Any]:
    documents = sorted(corpus.glob("*.txt"))
    if not documents:
        raise ValueError(f"no labelled documents in {corpus}")
    labels = [path.with_suffix(".labels.json") for path in documents]
    missing = [str(path) for path in labels if not path.is_file()]
    if missing:
        raise ValueError(f"missing labels: {', '.join(missing[:5])}")
    reports = [_evaluate_one(path, review_profile="strict") for path in documents]
    gate = subprocess.run(
        [sys.executable, str(ROOT / "scripts/recall_gate.py"), "--corpus", str(corpus)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "corpus": str(corpus.relative_to(ROOT) if corpus.is_relative_to(ROOT) else corpus),
        "corpus_sha256": fingerprint(documents + labels),
        "lock_sha256": fingerprint([_lock_path_for(corpus)]) if _lock_path_for(corpus).is_file() else None,
        "summary": _summary(reports),
        "regression_gate": {
            "passed": gate.returncode == 0,
            "returncode": gate.returncode,
            "diagnostics": (gate.stderr or gate.stdout)[-12000:] if gate.returncode else "",
        },
        "misses": [
            {"document": report.doc_id, "rules": sorted({item["rule"] for item in report.missed})}
            for report in reports
            if report.missed
        ],
        "interpretation": (
            "Exact rule/text expectation matching on internal fixtures. Unexpected findings may reflect incomplete "
            "labels; candidate_precision is a label-agreement measure, not independently verified precision. "
            "Use external held-out evaluation for generalization claims."
        ),
    }


def external_status() -> dict[str, dict[str, Any]]:
    return {
        "tab": {
            "available": all(
                (ROOT / "test/fixtures/external/text-anonymization-benchmark" / filename).is_file()
                for filename in ("echr_train.json", "echr_dev.json", "echr_test.json")
            ),
            "runner": "scripts/run_tab_eval.py",
            "output": "reports/current/core_tab_eval.json",
        },
        "ai4privacy": {
            "available": (ROOT / "test/fixtures/external/ai4privacy-pii-masking-200k/english_pii_43k.jsonl").is_file(),
            "runner": "scripts/run_ai4privacy_eval.py",
            "output": "reports/current/core_ai4privacy_eval.json",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus", action="append", type=Path, help="Repeat to select corpora; defaults to all locked corpora"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "reports/current/core_accuracy.json")
    parser.add_argument("--external", choices=("available", "require", "skip"), default="available")
    args = parser.parse_args(argv)
    corpora = [(path if path.is_absolute() else ROOT / path).resolve() for path in (args.corpus or DEFAULT_CORPORA)]
    versions = {}
    for package in ("junas", "numpy", "spacy", "pypdf", "Pillow"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    report: dict[str, Any] = {
        "schema_version": "junas.core_accuracy.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": "strict",
        "external_mode": args.external,
        "python": sys.version.split()[0],
        "package_versions": versions,
        "source_sha256": fingerprint(
            list((ROOT / "src/junas").rglob("*.py"))
            + list((ROOT / "src/junas").rglob("*.toml"))
            + list((ROOT / "src/junas").rglob("*.csv"))
        ),
        "evaluator_sha256": fingerprint(list((ROOT / "scripts").glob("*.py"))),
        "detector_environment_overrides": {
            name: os.environ[name]
            for name in (
                "JUNAS_SEMANTIC_PII_FALLBACK",
                "JUNAS_LOCAL_NER_FALLBACK",
                "JUNAS_LOCAL_NER_MODEL",
                "JUNAS_SPECIAL_CATEGORY_DISABLE",
                "JUNAS_JURISDICTION_PACKS_DIR",
                "JUNAS_FREQUENCY_DATA_DIR",
                "JUNAS_ENTITY_SIZE_CSV",
                "JUNAS_ENTITY_SIZE_JSON",
                "JUNAS_EARNINGS_CALENDAR_CSV",
                "JUNAS_GITLEAKS_RULE_PACKS",
                "JUNAS_GITLEAKS_MAX_RULES",
                "JUNAS_GITLEAKS_MAX_MATCHES",
                "JUNAS_GITLEAKS_RULE_PACK_MAX_BYTES",
            )
            if name in os.environ
        },
        "local_ner_enabled": os.environ.get("JUNAS_LOCAL_NER_FALLBACK", "0"),
        "local_ner_model": os.environ.get("JUNAS_LOCAL_NER_MODEL", "en_core_web_sm"),
        "corpora": [],
        "external": external_status(),
        "limitations": [
            "Regression locks measure retained behavior, not sufficient accuracy.",
            "Internal candidate labels are not independent public MNPI ground truth.",
            "This text-corpus run does not measure file extraction or OCR accuracy.",
            "External datasets are never downloaded automatically or treated as passing when absent.",
        ],
    }
    failed = False
    try:
        for corpus in corpora:
            print(f"Evaluating {corpus.name} ...", flush=True)
            result = evaluate_corpus(corpus)
            report["corpora"].append(result)
            summary = result["summary"]
            failed |= not result["regression_gate"]["passed"]
            print(
                f"  {summary['doc_count']} documents; recall={summary['candidate_recall']:.4f}; "
                f"label precision={summary['candidate_precision']:.4f}; F2={summary['candidate_f2']:.4f}; "
                f"gate={'FAIL' if not result['regression_gate']['passed'] else 'PASS'}",
                flush=True,
            )
        for name, external in report["external"].items():
            if args.external == "skip":
                external["status"] = "skipped_by_request"
            elif not external["available"]:
                external["status"] = "missing_fixture"
                failed |= args.external == "require"
            else:
                print(f"Evaluating external {name} ...", flush=True)
                result = subprocess.run(
                    [sys.executable, str(ROOT / external["runner"]), "--output", str(ROOT / external["output"])],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                external["status"] = "measured" if result.returncode == 0 else "failed"
                external["returncode"] = result.returncode
                external["diagnostics"] = (result.stderr or result.stdout)[-4000:] if result.returncode else ""
                failed |= result.returncode != 0
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        report["error"] = str(exc)
        failed = True
    report["regression_gates_passed"] = len(report["corpora"]) == len(corpora) and all(
        result["regression_gate"]["passed"] for result in report["corpora"]
    )
    report["run_passed"] = not failed
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Report: {args.output}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
