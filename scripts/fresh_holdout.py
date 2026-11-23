#!/usr/bin/env python3
"""Prepare a private frozen holdout bundle offline; paid execution needs separate authorization."""

from __future__ import annotations

import argparse
import ast
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts import model_corpus as corpus  # noqa: E402
from scripts.corpus_partitions import (  # noqa: E402
    FRESH_HOLDOUT_GROUPS,
    exclusion_registry,
    validate_exclusion_registry,
)
from scripts.corpus_report import read_records, release_holdout  # noqa: E402
from scripts.evaluate_sensitivity import check_targets  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files(root: Path) -> list[Path]:
    files = [
        p
        for directory in ("src/junas", "scripts", "config")
        for p in (root / directory).rglob("*")
        if p.is_file() and p.suffix in {".py", ".csv", ".toml", ".json"}
    ]
    files.extend(root / name for name in ("pyproject.toml", "uv.lock") if (root / name).is_file())
    corpus.require(files and not any(p.is_symlink() for p in files), "regular frozen source files required")
    return sorted(files)


def snapshot(root: Path, destination: Path) -> None:
    corpus.require((root / "src/junas/review/sensitivity.py").is_file(), "baseline source snapshot missing")
    for source in source_files(root):
        target = destination / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def runtime_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in source_files(root):
        if p.is_relative_to(root / "src/junas") and p.suffix in {".py", ".csv", ".toml"}:
            h.update(str(p.relative_to(root)).encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def execution_environment() -> dict:
    snapshot = corpus.reproducibility(Path(__file__))
    return {
        key: snapshot[key]
        for key in ("python", "package_versions", "dependency_lock_sha256", "detector_environment_value_sha256")
    }


def constant_text(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = constant_text(node.left), constant_text(node.right)
        if a is not None and b is not None and len(a) + len(b) <= 20_000:
            return a + b
    return None


def build_exclusions(inherited: dict, runs: list[Path], groups: list[dict] | None = None) -> tuple[dict, dict]:
    """Fingerprint old holdout sources without exposing their text or labels to evaluation."""
    validate_exclusion_registry(inherited)
    records = [
        {"text": p.read_text(), "template_group": "existing-fixture"} for p in (ROOT / "test/fixtures").rglob("*.txt")
    ]
    from scripts.check_reliability import cases

    records.extend({"text": r["text"], "template_group": "authored-regression"} for r in cases())
    for name in ("test_sensitivity.py", "test_contextual_identity_scopes.py", "test_contextual_mnpi_scopes.py"):
        for node in ast.walk(ast.parse((ROOT / "test" / name).read_text())):
            value = constant_text(node)
            if value is not None and len(value.strip()) >= 20:
                records.append({"text": value, "template_group": "authored-context-regression"})
    generated, candidates = 0, 0
    for run in runs:
        corpus.require(run.is_dir() and not run.is_relative_to(ROOT), "private prior run directory required")
        before = len(records)
        for path in sorted(run.rglob("candidate-*.json")):
            record = json.loads(path.read_text())
            if isinstance(record.get("text"), str) and record["text"].strip():
                records.append(
                    {"text": record["text"], "template_group": record.get("template_group", "legacy-source")}
                )
                candidates += 1
        for path in sorted(run.rglob("response-*.json")):
            raw = json.loads(path.read_text())
            if raw.get("request", {}).get("text", {}).get("format", {}).get("name") != "generator":
                continue
            try:
                payload = corpus.response_payload(raw["response"])
            except (ValueError, KeyError, TypeError):
                continue
            if isinstance(payload.get("text"), str) and payload["text"].strip():
                records.append({"text": payload["text"], "template_group": "previous-generated-source"})
                generated += 1
        corpus.require(len(records) > before, "prior run contains no recognized synthetic source artifacts")
    added = exclusion_registry(records)["entries"]
    unique = {corpus.identity(entry): entry for entry in inherited["entries"] + added}
    registry = {"schema_version": inherited["schema_version"], "entries": [unique[k] for k in sorted(unique)]}
    validate_exclusion_registry(registry)
    used_groups = {entry["template_group"] for entry in registry["entries"]}
    groups = FRESH_HOLDOUT_GROUPS if groups is None else groups
    corpus.require(not used_groups & {g["id"] for g in groups}, "fresh scenario families already used")
    return registry, {
        "inherited_entries": len(inherited["entries"]),
        "total_entries": len(unique),
        "prior_candidate_sources_fingerprinted": candidates,
        "prior_generator_responses_fingerprinted": generated,
        "prior_run_directories": [str(p) for p in runs],
        "old_holdout_use": "fingerprinting for exclusion only; no labels inspected or classifier evaluation",
        "limits": (
            "exact, normalized, numeric/email skeleton and shingle checks are contamination heuristics; "
            "semantic novelty is unverified"
        ),
    }


def prepare(output: Path, baseline: Path, inherited: Path, runs: list[Path], config_path: Path | None = None) -> dict:
    corpus.require(not output.resolve().is_relative_to(ROOT), "bundle must be outside repository")
    corpus.require(not output.exists(), "bundle already exists")
    config = json.loads((config_path or ROOT / "config/model_corpus.holdout-v2.json").read_text())
    corpus.validate_config(config)
    corpus.require(config.get("sampling", {}).get("split") == "holdout", "reserved holdout configuration required")
    registry, audit = build_exclusions(json.loads(inherited.read_text()), runs, config["sampling"]["groups"])
    config["exclusion_registry_sha256"] = corpus.identity(registry)
    corpus.validate_config(config)
    baseline_hash, improved_hash = runtime_hash(baseline), runtime_hash(ROOT)
    corpus.require(baseline_hash != improved_hash, "paired evaluation requires different classifier versions")
    output.mkdir(mode=0o700)
    snapshot(ROOT, output / "source")
    snapshot(baseline, output / "baseline")
    corpus.write_new(output / "config.json", config)
    corpus.write_new(output / "exclusions.json", registry)
    corpus.write_new(
        output / "targets.json", json.loads((ROOT / "config/sensitivity-development-gates.json").read_text())
    )
    corpus.write_new(output / "exclusion-audit.json", audit)
    limit = corpus.validate_spending_limit(config["spending_limit"])
    proposal = {
        "schema_version": "junas.fresh_holdout_proposal.v1",
        "status": "prepared_not_generated",
        "paid_calls_made": 0,
        "live_calls_authorized": False,
        "plan": corpus.plan(config),
        "empirical_estimate_usd": "2.73792225",
        "empirical_basis": (
            "completed prior 40-document stage including rejection and retries; "
            "conservative accounted cost, not invoice"
        ),
        "proposed_cap_usd": limit["provider_cap_usd"],
        "additional_sgd_scenario": str(Decimal(limit["provider_cap_usd"]) * Decimal("1.5") * Decimal("1.2")),
        "aggregate_sgd_scenario": limit["sgd_scenario_ceiling"],
        "fx_and_fees": "planning assumptions: SGD1.50/USD and 20% contingency; not a current exchange-rate quote",
        "pricing_checked_on": config["pricing_checked_on"],
        "published_standard_rates_per_million": {
            "gpt-6.2-sol": {"input": "2", "output": "10", "cache_write_30m": "2.5"},
            "gpt-6.1-terra": {"input": "1", "output": "5", "cache_write_30m": "1.25"},
        },
        "pricing_sources": [
            "https://developers.openai.com/api/docs/models/gpt-6.2-sol",
            "https://developers.openai.com/api/docs/models/gpt-6.1-terra",
        ],
        "budget_accounting": (
            "conservative input ceilings of 4.5/2.25 cover standard input plus 30-minute cache writes; "
            "full output reservation before each request; no cache savings assumed"
        ),
        "classifiers": {"baseline_sha256": baseline_hash, "improved_sha256": improved_hash},
        "selection": "judge-only quadrant and subtype coverage; classifier predictions never select documents",
        "release": (
            "one-shot paired evaluation after complete quadrant/entity coverage; "
            "consume before metrics; no tuning or retrying the evaluation"
        ),
        "limits": [
            "40 documents is a small synthetic check, not independent legal ground truth.",
            "Three passes of the same judge model have correlated errors.",
            "Budget or candidate limits may prevent coverage; report incomplete runs without forced labels.",
            "Unknown request charges retain their reserve and are not automatically retried.",
            "No authorization file or paid calls are created by preparation.",
        ],
        "exclusions": audit,
    }
    corpus.write_new(output / "proposal.json", proposal)
    files = {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}
    corpus.write_new(
        output / "frozen.json",
        {
            "files": files,
            "config_sha256": corpus.identity(config),
            "classifiers": proposal["classifiers"],
            "execution_environment": execution_environment(),
        },
    )
    return proposal


def verify_bundle(bundle: Path) -> dict:
    frozen = json.loads((bundle / "frozen.json").read_text())
    corpus.require(frozen["execution_environment"] == execution_environment(), "frozen execution environment drift")
    for name, expected in frozen["files"].items():
        path = (bundle / name).resolve()
        corpus.require(
            path.is_relative_to(bundle) and path.is_file() and digest(path) == expected, "frozen bundle drift"
        )
    corpus.require(
        runtime_hash(bundle / "source") == frozen["classifiers"]["improved_sha256"], "improved classifier drift"
    )
    corpus.require(
        runtime_hash(bundle / "baseline") == frozen["classifiers"]["baseline_sha256"], "baseline classifier drift"
    )
    return frozen


BASELINE_WORKER = """
import json,socket,sys
from pathlib import Path
root,records,output=map(Path,sys.argv[1:])
sys.path[:0]=[str(root),str(root/'src')]
from scripts.model_corpus import evaluate_records
def denied(*a,**k): raise RuntimeError('network forbidden during classifier evaluation')
socket.socket.connect=denied
data=[json.loads(line) for line in records.read_text().splitlines() if line.strip()]
result=evaluate_records([{**r,'split':'released_holdout'} for r in data])
with output.open('x') as f:json.dump(result,f,sort_keys=True);f.write('\\n')
"""


def evaluate(bundle: Path, run_dir: Path | None = None) -> dict:
    frozen = verify_bundle(bundle)
    run_dir = bundle / "run" if run_dir is None else run_dir.resolve()
    corpus.require(run_dir.is_relative_to(bundle), "holdout segment must remain in the frozen bundle")
    manifest = json.loads((run_dir / "manifest.json").read_text())
    corpus.require(manifest["config_sha256"] == frozen["config_sha256"], "run configuration drift")
    corpus.require(
        manifest["reproducibility"]["classifier_sha256"] == frozen["classifiers"]["improved_sha256"],
        "run classifier drift",
    )
    records = read_records(run_dir / "combined-records.jsonl")
    ids = [r["document_id"] for r in records]
    corpus.require(len(ids) == len(set(ids)), "duplicate holdout document identity")
    allowed = {g["id"] for g in json.loads((bundle / "config.json").read_text())["sampling"]["groups"]}
    corpus.require(all(r.get("template_group") in allowed for r in records), "unreserved holdout scenario family")
    exclusions = json.loads((bundle / "exclusions.json").read_text())
    current = release_holdout(run_dir, [], bundle / "improved-evaluation.json", exclusions=exclusions)
    subprocess.run(
        [
            sys.executable,
            "-c",
            BASELINE_WORKER,
            str(bundle / "baseline"),
            str(run_dir / "combined-records.jsonl"),
            str(bundle / "baseline-evaluation.json"),
        ],
        check=True,
        cwd=bundle,
    )
    baseline = json.loads((bundle / "baseline-evaluation.json").read_text())
    targets = json.loads((bundle / "targets.json").read_text())
    before, _ = check_targets(baseline, targets)
    after, checks = check_targets(current["evaluation"], targets)
    result = {
        "schema_version": "junas.paired_holdout.v1",
        "status": "consumed",
        "documents": current["documents"],
        "classifiers": frozen["classifiers"],
        "records_sha256": corpus.identity(records),
        "reference": "same fresh synthetic model-consensus holdout for both frozen versions; not independent accuracy",
        "before": before,
        "after": after,
        "delta": {k: after[k] - before[k] for k in before},
        "targets": checks,
        "passed": all(c["passed"] for c in checks.values()),
    }
    corpus.write_new(bundle / "paired-evaluation.json", result)
    return result


def execute(bundle: Path, authorization: Path, env_file: Path) -> dict:
    verify_bundle(bundle)
    config = json.loads((bundle / "config.json").read_text())
    auth = json.loads(authorization.read_text())
    corpus.validate_authorization(auth, config)
    corpus.load_api_key(env_file)
    exclusions = json.loads((bundle / "exclusions.json").read_text())
    source = None
    attempted, failures, ordinal = 0, 0, 1
    controller_stop = None
    with (bundle / "paid-execution.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            verify_bundle(bundle)
            output = bundle / ("run" if ordinal == 1 else f"run-{ordinal:03d}")
            result = corpus.run(config, auth, output, exclusions=exclusions, resume_from=source)
            if result["stop_reason"] != "UncertainRequest":
                break
            # recovery retains every reserve and skips the entire uncertain candidate.
            failures = failures + 1 if result["attempted_candidates"] <= attempted + 1 else 1
            if failures >= 3:
                controller_stop = "three_consecutive_uncertain_candidates"
                break
            source, attempted, ordinal = output, result["attempted_candidates"], ordinal + 1
        validation = evaluate(bundle, output) if result["status"] == "completed" else None
    return {
        **{k: result[k] for k in ("status", "stop_reason", "accepted_documents", "charged_or_reserved_ceiling_usd")},
        "validation_passed": validation["passed"] if validation else None,
        "controller_stop_reason": controller_stop,
        "final_segment": output.name,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "evaluate"))
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--baseline-source", type=Path)
    parser.add_argument("--config", type=Path, help="Reserved holdout config; default preserves the v2 proposal")
    parser.add_argument("--inherited-exclusions", type=Path)
    parser.add_argument("--prior-run", type=Path, action="append", default=[])
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    bundle = args.bundle.resolve()
    if args.command == "prepare":
        corpus.require(
            args.baseline_source is not None and args.inherited_exclusions is not None and args.prior_run,
            "baseline, inherited exclusions and prior runs required",
        )
        result = prepare(
            bundle,
            args.baseline_source.resolve(),
            args.inherited_exclusions,
            [p.resolve() for p in args.prior_run],
            args.config,
        )
        print(
            json.dumps(
                {k: result[k] for k in ("status", "paid_calls_made", "proposed_cap_usd", "empirical_estimate_usd")}
            )
        )
        return 0
    verify_bundle(bundle)
    frozen_script = bundle / "source/scripts/fresh_holdout.py"
    if Path(__file__).resolve() != frozen_script:
        command = [sys.executable, str(frozen_script), args.command, "--bundle", str(bundle)]
        for option, value in (("--authorization", args.authorization), ("--env-file", args.env_file)):
            if value is not None:
                command.extend((option, str(value.resolve())))
        return subprocess.run(command, cwd=bundle, check=False).returncode
    if args.command == "run":
        corpus.require(
            args.authorization is not None and args.env_file is not None,
            "separate paid authorization and explicit local key file required",
        )
        result = execute(bundle, args.authorization, args.env_file)
        print(json.dumps(result))
        return 0 if result["status"] == "completed" and result["validation_passed"] else 1
    result = evaluate(bundle)
    print(json.dumps({k: result[k] for k in ("status", "documents", "passed")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
