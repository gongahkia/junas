#!/usr/bin/env python3
"""Watch backend status by polling health, readiness, diagnostics, and metrics."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


METRIC_LINE_RE = re.compile(
    r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>[^}]*)\})?\s+(?P<value>[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)$"
)


@dataclass
class MetricSample:
    name: str
    labels: dict[str, str]
    value: float


def fetch_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
        if isinstance(payload, dict):
            return payload
    return {}


def fetch_text(url: str, timeout_seconds: float) -> str:
    with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8")


def parse_labels(raw: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    if not raw:
        return labels
    for item in raw.split(","):
        part = item.strip()
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        labels[key.strip()] = value.strip().strip('"')
    return labels


def parse_metrics(text: str) -> list[MetricSample]:
    samples: list[MetricSample] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = METRIC_LINE_RE.match(stripped)
        if not match:
            continue
        try:
            value = float(match.group("value"))
        except ValueError:
            continue
        samples.append(
            MetricSample(
                name=match.group("name"),
                labels=parse_labels(match.group("labels") or ""),
                value=value,
            )
        )
    return samples


def summarize_metrics(samples: list[MetricSample]) -> dict[str, Any]:
    http_total = 0.0
    classify_total = 0.0
    classify_by_label: dict[str, float] = {}
    cache_hits = 0.0
    cache_misses = 0.0

    for sample in samples:
        if sample.name == "kaypoh_http_requests_total":
            http_total += sample.value
        elif sample.name == "kaypoh_classification_results_total":
            classify_total += sample.value
            classification = sample.labels.get("classification", "unknown")
            classify_by_label[classification] = classify_by_label.get(classification, 0.0) + sample.value
            cache_status = sample.labels.get("cache_status")
            if cache_status == "hit":
                cache_hits += sample.value
            elif cache_status == "miss":
                cache_misses += sample.value

    return {
        "http_total": int(http_total),
        "classify_total": int(classify_total),
        "classify_by_label": {k: int(v) for k, v in sorted(classify_by_label.items())},
        "cache_hits": int(cache_hits),
        "cache_misses": int(cache_misses),
    }


def bool_icon(value: Any) -> str:
    return "yes" if bool(value) else "no"


def format_status_block(
    *,
    base_url: str,
    health: dict[str, Any] | None,
    ready: dict[str, Any] | None,
    diagnostics: dict[str, Any] | None,
    metrics_summary: dict[str, Any] | None,
    errors: list[str],
) -> str:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"Kaypoh Backend Status Watch  {now}", f"Base URL: {base_url}", ""]

    if ready is not None:
        missing = ",".join(ready.get("missing_required_layers", []) or []) or "-"
        warming = ",".join(ready.get("warming_required_layers", []) or []) or "-"
        lines.append(
            "Ready: "
            f"status={ready.get('status', 'unknown')} "
            f"ready={bool_icon(ready.get('ready'))} "
            f"missing={missing} warming={warming}"
        )
    else:
        lines.append("Ready: unavailable")

    if health is not None:
        loaded_bits = [
            f"lexicon={bool_icon(health.get('lexicon_loaded'))}",
            f"embedding={bool_icon(health.get('embedding_loaded'))}",
            f"clustering={bool_icon(health.get('clustering_loaded'))}",
            f"model1={bool_icon(health.get('model1_loaded'))}",
            f"model2={bool_icon(health.get('model2_loaded'))}",
            f"mosaic={bool_icon(health.get('mosaic_loaded'))}",
            f"regression={bool_icon(health.get('regression_loaded'))}",
        ]
        lines.append(f"Health: {' '.join(loaded_bits)}")
    else:
        lines.append("Health: unavailable")

    if diagnostics is not None:
        loaded_layers = ",".join(diagnostics.get("loaded_layers", []) or []) or "-"
        lazy_layers = ",".join(diagnostics.get("lazy_layers", []) or []) or "-"
        startup_total = (diagnostics.get("startup_timings_ms") or {}).get("total")
        dep_redis = (diagnostics.get("dependency_status") or {}).get("redis", {})
        dep_summary = dep_redis.get("status", "n/a")
        lines.append(
            "Diagnostics: "
            f"loaded={loaded_layers} lazy={lazy_layers} "
            f"startup_total_ms={startup_total if startup_total is not None else 'n/a'} "
            f"redis={dep_summary}"
        )
    else:
        lines.append("Diagnostics: unavailable")

    if metrics_summary is not None:
        label_summary = ", ".join(
            [f"{key}={value}" for key, value in metrics_summary.get("classify_by_label", {}).items()]
        ) or "-"
        lines.append(
            "Metrics: "
            f"http_requests_total={metrics_summary.get('http_total', 0)} "
            f"classifications_total={metrics_summary.get('classify_total', 0)} "
            f"cache_hits={metrics_summary.get('cache_hits', 0)} "
            f"cache_misses={metrics_summary.get('cache_misses', 0)} "
            f"by_class=[{label_summary}]"
        )
    else:
        lines.append("Metrics: unavailable")

    if errors:
        lines.append("")
        lines.append("Errors:")
        for error in errors:
            lines.append(f"- {error}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Watch backend status by polling /health, /ready, /diagnostics, and /metrics."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--interval-seconds", type=float, default=2.0, help="Polling interval in seconds")
    parser.add_argument("--timeout-seconds", type=float, default=3.0, help="Per-request timeout in seconds")
    parser.add_argument("--once", action="store_true", help="Print one snapshot and exit")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    interval_seconds = max(0.25, args.interval_seconds)
    timeout_seconds = max(0.5, args.timeout_seconds)
    use_clear = not args.once

    while True:
        errors: list[str] = []
        health: dict[str, Any] | None = None
        ready: dict[str, Any] | None = None
        diagnostics: dict[str, Any] | None = None
        metrics_summary: dict[str, Any] | None = None

        try:
            health = fetch_json(f"{base_url}/health", timeout_seconds)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"/health: {exc}")

        try:
            ready = fetch_json(f"{base_url}/ready", timeout_seconds)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"/ready: {exc}")

        try:
            diagnostics = fetch_json(f"{base_url}/diagnostics", timeout_seconds)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"/diagnostics: {exc}")

        try:
            metrics_text = fetch_text(f"{base_url}/metrics", timeout_seconds)
            metrics_summary = summarize_metrics(parse_metrics(metrics_text))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"/metrics: {exc}")

        block = format_status_block(
            base_url=base_url,
            health=health,
            ready=ready,
            diagnostics=diagnostics,
            metrics_summary=metrics_summary,
            errors=errors,
        )

        if use_clear:
            print("\033[2J\033[H", end="")
        print(block, flush=True)

        if args.once:
            return 0
        time.sleep(interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
