"""Build static baseline leaderboard artefacts from JSON receipts."""
from __future__ import annotations

import argparse
import json
import random
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNS_ROOT = REPO_ROOT / "runs" / "baselines"
DOCS_LEADERBOARD = REPO_ROOT / "docs" / "leaderboard.md"
LEADERBOARD_JSON = RUNS_ROOT / "leaderboard.json"
BOOTSTRAP_N = 1000
REQUIRED_PROVIDERS = ("azure", "anthropic", "gemini", "ollama")
PROVIDER_LABELS = {
    "azure": "OpenAI (Azure gpt-5)",
    "anthropic": "Anthropic (claude-sonnet-4.6)",
    "gemini": "Gemini 2.0",
}
DATASET_VERSION_BY_NAME = {
    "sglb_01_pdpa.yaml": "sglb-01-v0.1",
    "sglb_02_statute_qa.yaml": "sglb-02-v0.1",
    "sglb_04_citation_verify.yaml": "sglb-04-v0.1",
}


@dataclass(frozen=True)
class MetricRow:
    task: str
    metric: str
    evaluator: str
    detail_key: str | None = None
    lower_is_better: bool = False


ROWS = (
    MetricRow("SGLB-01", "obligation F1", "sglb_01_obligations_f1"),
    MetricRow("SGLB-01", "penalty MAE", "penalty_band_mae", detail_key="mae", lower_is_better=True),
    MetricRow("SGLB-02", "citation match", "sglb_02_citation_match"),
    MetricRow("SGLB-02", "ROUGE-L", "rouge_l_answer"),
    MetricRow("SGLB-04", "label F1", "multi_label_f1"),
)


def _task_from_payload(payload: dict[str, Any]) -> str:
    haystack = " ".join(
        str(payload.get(key, ""))
        for key in ("workflow", "dataset")
    ).lower()
    for suffix in ("01", "02", "04", "08"):
        if f"sglb_{suffix}" in haystack or f"sglb-{suffix}" in haystack:
            return f"SGLB-{suffix}"
    return ""


def _timestamp(payload: dict[str, Any], path: Path) -> str:
    value = str(payload.get("finished_at") or payload.get("started_at") or "")
    if value:
        return value
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def _load_receipts(root: Path) -> dict[tuple[str, str], tuple[Path, dict[str, Any]]]:
    latest: dict[tuple[str, str], tuple[Path, dict[str, Any]]] = {}
    for path in sorted(root.rglob("*.json")):
        if path.name == "leaderboard.json":
            continue
        relative = path.relative_to(root)
        if not relative.parts:
            continue
        provider = relative.parts[0]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        task = _task_from_payload(payload)
        if not task:
            continue
        key = (provider, task)
        current = latest.get(key)
        if current is None or _timestamp(payload, path) > _timestamp(current[1], current[0]):
            latest[key] = (path, payload)
    return latest


def _provider_display(provider: str, payloads: list[dict[str, Any]]) -> str:
    if provider != "ollama":
        return PROVIDER_LABELS.get(provider, provider)
    for payload in payloads:
        provenance = payload.get("provenance") or {}
        display = provenance.get("model_display_name")
        if display:
            return str(display)
        label = str(provenance.get("provider_label") or "")
        if label.startswith("ollama:"):
            return label.split(":", 1)[1]
    return "Open-weight"


def _metric_values(payload: dict[str, Any], row: MetricRow) -> list[float]:
    values: list[float] = []
    for result in payload.get("results") or []:
        if result.get("evaluator") != row.evaluator:
            continue
        if result.get("error"):
            values.append(3.0 if row.lower_is_better else 0.0)
            continue
        if row.detail_key:
            metadata = result.get("metadata") or {}
            if row.detail_key in metadata:
                values.append(float(metadata[row.detail_key]))
            else:
                values.append(3.0)
        else:
            values.append(float(result.get("score") or 0.0))
    return values


def _bootstrap(values: list[float], *, seed: int, n: int = BOOTSTRAP_N) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "ci_low": 0.0, "ci_high": 0.0, "n": 0.0}
    rng = random.Random(seed)
    means: list[float] = []
    count = len(values)
    for _ in range(n):
        sample = [values[rng.randrange(count)] for _ in range(count)]
        means.append(statistics.fmean(sample))
    means.sort()
    low_idx = int(0.025 * (n - 1))
    high_idx = int(0.975 * (n - 1))
    return {
        "mean": statistics.fmean(values),
        "ci_low": means[low_idx],
        "ci_high": means[high_idx],
        "n": float(count),
    }


def _normalised_task_score(payload: dict[str, Any], task: str) -> float | None:
    scores: list[float] = []
    for row in ROWS:
        if row.task != task:
            continue
        for result in payload.get("results") or []:
            if result.get("evaluator") == row.evaluator and not result.get("error"):
                scores.append(float(result.get("score") or 0.0))
    if not scores:
        return None
    return statistics.fmean(scores)


def _dataset_version(payload: dict[str, Any]) -> str:
    provenance = payload.get("provenance") or {}
    if provenance.get("dataset_version"):
        return str(provenance["dataset_version"])
    dataset_path = payload.get("dataset")
    if not dataset_path:
        return ""
    path = Path(str(dataset_path))
    if not path.is_absolute():
        path = REPO_ROOT / path
    fallback = DATASET_VERSION_BY_NAME.get(path.name, "")
    if not path.exists():
        return fallback
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    versions = {
        str(case.get("metadata", {}).get("dataset_version"))
        for case in data.get("cases", [])
        if case.get("metadata", {}).get("dataset_version")
    }
    if len(versions) == 1:
        return next(iter(versions))
    if versions:
        return "mixed"
    return fallback


def _format_cell(stats: dict[str, float]) -> str:
    return f"{stats['mean']:.2f} [{stats['ci_low']:.2f}, {stats['ci_high']:.2f}]"


def build_leaderboard(
    *,
    root: Path,
    required_providers: tuple[str, ...],
    allow_missing: bool,
) -> dict[str, Any]:
    receipts = _load_receipts(root)
    present = {provider for provider, _task in receipts}
    missing_providers = [provider for provider in required_providers if provider not in present]
    if missing_providers and not allow_missing:
        raise SystemExit(f"missing provider receipts: {', '.join(missing_providers)}")
    providers = [provider for provider in required_providers if provider in present]
    missing_cells: list[str] = []
    provider_payloads = {
        provider: [payload for (p, _task), (_path, payload) in receipts.items() if p == provider]
        for provider in providers
    }
    columns = [{"key": provider, "label": _provider_display(provider, provider_payloads[provider])} for provider in providers]
    rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(ROWS):
        cells: dict[str, Any] = {}
        for provider in providers:
            item = receipts.get((provider, row.task))
            if item is None:
                missing_cells.append(f"{provider}/{row.task}/{row.metric}")
                continue
            path, payload = item
            values = _metric_values(payload, row)
            if not values:
                missing_cells.append(f"{provider}/{row.task}/{row.metric}")
                continue
            stats = _bootstrap(values, seed=1009 + row_index)
            cells[provider] = {
                **stats,
                "receipt": str(path.relative_to(REPO_ROOT)),
                "dataset_version": _dataset_version(payload),
                "run_date": payload.get("finished_at") or payload.get("started_at") or "",
                "model": (payload.get("provenance") or {}).get("provider_label", ""),
                "lower_is_better": row.lower_is_better,
            }
        rows.append({"task": row.task, "metric": row.metric, "evaluator": row.evaluator, "cells": cells})
    if missing_cells and not allow_missing:
        raise SystemExit("missing leaderboard cells: " + ", ".join(missing_cells))
    review_flags = _review_flags(receipts, providers)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bootstrap_n": BOOTSTRAP_N,
        "providers": columns,
        "rows": rows,
        "review_flags": review_flags,
    }


def _review_flags(
    receipts: dict[tuple[str, str], tuple[Path, dict[str, Any]]],
    providers: list[str],
) -> dict[str, list[str]]:
    too_easy: list[str] = []
    too_low: list[str] = []
    for task in sorted({row.task for row in ROWS}):
        scores: list[float] = []
        for provider in providers:
            item = receipts.get((provider, task))
            if item is None:
                continue
            score = _normalised_task_score(item[1], task)
            if score is not None:
                scores.append(score)
        if len(scores) != len(providers) or not scores:
            continue
        if all(score >= 0.98 for score in scores):
            too_easy.append(task)
        if all(score <= 0.30 for score in scores):
            too_low.append(task)
    return {"too_easy": too_easy, "too_low": too_low}


def write_outputs(payload: dict[str, Any], *, json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    provider_labels = [provider["label"] for provider in payload["providers"]]
    provider_keys = [provider["key"] for provider in payload["providers"]]
    header = "| Task | Metric | " + " | ".join(provider_labels) + " |"
    divider = "|---|---|" + "|".join("---" for _ in provider_labels) + "|"
    lines = [
        "# SG-LegalBench v0.1 Baseline Leaderboard",
        "",
        f"Generated: {payload['generated_at']}",
        f"95% confidence intervals use bootstrap n={payload['bootstrap_n']} over case-level scores.",
        "Penalty MAE is lower-is-better; all other metrics are higher-is-better.",
        "",
        header,
        divider,
    ]
    for row in payload["rows"]:
        cells = []
        for provider in provider_keys:
            cell = row["cells"].get(provider)
            cells.append(_format_cell(cell) if cell else "TBD")
        lines.append(f"| {row['task']} | {row['metric']} | " + " | ".join(cells) + " |")
    flags = payload["review_flags"]
    lines.extend(["", "## Review Flags", ""])
    if flags["too_easy"]:
        lines.append("Tasks where every model scored >=98%: " + ", ".join(flags["too_easy"]))
    else:
        lines.append("Tasks where every model scored >=98%: none")
    if flags["too_low"]:
        lines.append("Tasks where every model scored <=30%: " + ", ".join(flags["too_low"]))
    else:
        lines.append("Tasks where every model scored <=30%: none")
    lines.extend(["", "## Receipts", ""])
    for row in payload["rows"]:
        for provider in provider_keys:
            cell = row["cells"].get(provider)
            if not cell:
                continue
            lines.append(
                f"- {row['task']} {row['metric']} / {provider}: "
                f"{cell['receipt']} ({cell['dataset_version']})"
            )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build SG-LegalBench baseline leaderboard")
    parser.add_argument("--runs-root", type=Path, default=RUNS_ROOT)
    parser.add_argument("--json-output", type=Path, default=LEADERBOARD_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DOCS_LEADERBOARD)
    parser.add_argument("--allow-missing", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_leaderboard(
        root=args.runs_root,
        required_providers=REQUIRED_PROVIDERS,
        allow_missing=args.allow_missing,
    )
    write_outputs(payload, json_path=args.json_output, md_path=args.markdown_output)
    print(f"wrote {args.json_output}")
    print(f"wrote {args.markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
