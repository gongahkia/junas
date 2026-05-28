#!/usr/bin/env python3
"""Opt-in p95 latency SLO gate for /review and /anonymize.

This intentionally uses FastAPI's in-process TestClient rather than an external uvicorn
process so CI can run the gate without port management noise. The benchmark still exercises
request validation, routing, endpoint code, and response serialization.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BUDGET_FILE = ROOT / "test" / "benchmarks" / "latency_slo_budgets.json"
DEFAULT_REPORT_DIR = ROOT / "reports"
VALID_SURFACES = ("review", "anonymize")
VALID_PROFILES = ("strict", "audit_grade")


@dataclass(frozen=True)
class LatencyCase:
    surface: str
    profile: str
    budget_ms: float
    fixture_path: Path

    @property
    def key(self) -> str:
        return f"{self.surface}.{self.profile}"


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return round(values[0], 3)
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round((ordered[lower] * (1 - weight)) + (ordered[upper] * weight), 3)


def load_budget_config(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    budgets = raw.get("budgets_ms")
    if not isinstance(budgets, dict) or not budgets:
        raise ValueError(f"{path} must define non-empty budgets_ms")
    return raw


def resolve_fixture(config: dict[str, Any], override: str | None) -> Path:
    raw = override or str(config.get("default_fixture") or "")
    if not raw:
        raise ValueError("latency SLO config is missing default_fixture")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        raise FileNotFoundError(f"latency fixture not found: {path}")
    return path.resolve()


def build_cases(
    *,
    config: dict[str, Any],
    fixture_path: Path,
    surfaces: list[str],
    profiles: list[str],
) -> list[LatencyCase]:
    budgets: dict[str, Any] = dict(config["budgets_ms"])
    out: list[LatencyCase] = []
    for surface in surfaces:
        if surface not in VALID_SURFACES:
            raise ValueError(f"unsupported surface {surface!r}; expected one of {VALID_SURFACES}")
        for profile in profiles:
            if profile not in VALID_PROFILES:
                raise ValueError(f"unsupported profile {profile!r}; expected one of {VALID_PROFILES}")
            key = f"{surface}.{profile}"
            if key not in budgets:
                raise ValueError(f"missing p95 budget for {key}")
            out.append(
                LatencyCase(
                    surface=surface,
                    profile=profile,
                    budget_ms=float(budgets[key]),
                    fixture_path=fixture_path,
                )
            )
    return out


def _payload_for_case(case: LatencyCase, text: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "text": text,
        "source_jurisdiction": "SG",
        "destination_jurisdiction": "SG",
        "document_type": "generic",
        "review_profile": case.profile,
        "include_suggestions": False,
    }
    if case.surface == "anonymize":
        payload["include_mnpi_scalars"] = True
    return payload


@contextmanager
def quiet_latency_logs(enabled: bool):
    if not enabled:
        yield
        return
    names = ("kaypoh.backend", "kaypoh.siem", "httpx")
    previous = []
    for name in names:
        logger = logging.getLogger(name)
        previous.append((logger, logger.level))
        logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        for logger, level in previous:
            logger.setLevel(level)


def _case_result(
    *,
    case: LatencyCase,
    mode: str,
    warmups: int,
    repetitions: int,
    latencies_ms: list[float],
    server_totals_ms: list[float],
    base_url: str = "",
) -> dict[str, Any]:
    p95_ms = percentile(latencies_ms, 0.95)
    passed = p95_ms <= case.budget_ms
    result = {
        "case": case.key,
        "mode": mode,
        "surface": case.surface,
        "profile": case.profile,
        "fixture": str(case.fixture_path),
        "fixture_bytes": case.fixture_path.stat().st_size,
        "warmups": warmups,
        "repetitions": repetitions,
        "budget_ms": case.budget_ms,
        "min_ms": round(min(latencies_ms), 3),
        "mean_ms": round(mean(latencies_ms), 3),
        "p50_ms": percentile(latencies_ms, 0.50),
        "p95_ms": p95_ms,
        "max_ms": round(max(latencies_ms), 3),
        "mean_server_total_ms": round(mean(server_totals_ms), 3) if server_totals_ms else None,
        "passed": passed,
        "latencies_ms": latencies_ms,
    }
    if base_url:
        result["base_url"] = base_url
    return result


def run_case(client: Any, case: LatencyCase, *, warmups: int, repetitions: int) -> dict[str, Any]:
    endpoint = f"/{case.surface}"
    text = case.fixture_path.read_text(encoding="utf-8")
    payload = _payload_for_case(case, text)

    for _ in range(warmups):
        response = client.post(endpoint, json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"{case.key} warmup failed with HTTP {response.status_code}: {response.text}")

    latencies_ms: list[float] = []
    server_totals_ms: list[float] = []
    for _ in range(repetitions):
        started = time.perf_counter()
        response = client.post(endpoint, json=payload)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if response.status_code != 200:
            raise RuntimeError(f"{case.key} run failed with HTTP {response.status_code}: {response.text}")
        body = response.json()
        latencies_ms.append(round(elapsed_ms, 3))
        total = (body.get("timings_ms") or {}).get("total")
        if total is not None:
            server_totals_ms.append(float(total))

    return _case_result(
        case=case,
        mode="in_process",
        warmups=warmups,
        repetitions=repetitions,
        latencies_ms=latencies_ms,
        server_totals_ms=server_totals_ms,
    )


def run_gate(
    *,
    cases: list[LatencyCase],
    warmups: int,
    repetitions: int,
    quiet_logs: bool = True,
) -> list[dict[str, Any]]:
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from fastapi.testclient import TestClient

    from kaypoh.backend import main as backend_main

    backend_main._state.clear()
    with quiet_latency_logs(quiet_logs):
        with TestClient(backend_main.app) as client:
            return [run_case(client, case, warmups=warmups, repetitions=repetitions) for case in cases]


def _post_live_json(
    *,
    base_url: str,
    endpoint: str,
    payload: dict[str, Any],
    api_key: str,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    if not isinstance(body, dict):
        raise RuntimeError(f"unexpected non-object response from {endpoint}: {body!r}")
    return body


def run_live_http_case(
    *,
    base_url: str,
    api_key: str,
    case: LatencyCase,
    warmups: int,
    repetitions: int,
) -> dict[str, Any]:
    endpoint = f"/{case.surface}"
    text = case.fixture_path.read_text(encoding="utf-8")
    payload = _payload_for_case(case, text)

    for _ in range(warmups):
        try:
            _post_live_json(base_url=base_url, endpoint=endpoint, payload=payload, api_key=api_key)
        except RuntimeError as exc:
            raise RuntimeError(f"{case.key} live warmup failed: {exc}") from exc

    latencies_ms: list[float] = []
    server_totals_ms: list[float] = []
    for _ in range(repetitions):
        started = time.perf_counter()
        try:
            body = _post_live_json(base_url=base_url, endpoint=endpoint, payload=payload, api_key=api_key)
        except RuntimeError as exc:
            raise RuntimeError(f"{case.key} live run failed: {exc}") from exc
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        latencies_ms.append(round(elapsed_ms, 3))
        total = (body.get("timings_ms") or {}).get("total")
        if total is not None:
            server_totals_ms.append(float(total))

    return _case_result(
        case=case,
        mode="live_http",
        warmups=warmups,
        repetitions=repetitions,
        latencies_ms=latencies_ms,
        server_totals_ms=server_totals_ms,
        base_url=base_url.rstrip("/"),
    )


def run_live_http_gate(
    *,
    cases: list[LatencyCase],
    warmups: int,
    repetitions: int,
    base_url: str,
    api_key: str = "",
) -> list[dict[str, Any]]:
    return [
        run_live_http_case(
            base_url=base_url,
            api_key=api_key,
            case=case,
            warmups=warmups,
            repetitions=repetitions,
        )
        for case in cases
    ]


def render_summary(results: list[dict[str, Any]]) -> str:
    lines = [
        f"{'case':<24} {'fixture_kb':>10} {'p50':>10} {'p95':>10} {'budget':>10} {'status':>8}",
        "-" * 78,
    ]
    for item in results:
        status = "PASS" if item["passed"] else "FAIL"
        lines.append(
            f"{item['case']:<24} "
            f"{item['fixture_bytes'] / 1024:>10.1f} "
            f"{item['p50_ms']:>10.3f} "
            f"{item['p95_ms']:>10.3f} "
            f"{item['budget_ms']:>10.3f} "
            f"{status:>8}"
        )
    return "\n".join(lines)


def write_report(results: list[dict[str, Any]], report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = report_dir / f"latency_slo_{timestamp}.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "kaypoh.latency_slo.v1",
                "generated_at": timestamp,
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the opt-in Kaypoh p95 latency SLO gate")
    parser.add_argument("--budget-file", type=Path, default=DEFAULT_BUDGET_FILE)
    parser.add_argument("--fixture", help="override fixture path; default comes from budget file")
    parser.add_argument("--surface", choices=VALID_SURFACES, action="append", dest="surfaces")
    parser.add_argument("--profile", choices=VALID_PROFILES, action="append", dest="profiles")
    parser.add_argument("--warmups", type=int, help="warmup runs per case")
    parser.add_argument("--repetitions", type=int, help="measured runs per case")
    parser.add_argument("--no-fail", action="store_true", help="always exit 0 after reporting")
    parser.add_argument("--write-report", action="store_true", help="write reports/latency_slo_*.json")
    parser.add_argument("--base-url", help="run against a live HTTP server instead of in-process TestClient")
    parser.add_argument(
        "--api-key",
        default=None,
        help="X-API-Key for live HTTP mode; falls back to KAYPOH_LATENCY_SLO_API_KEY or KAYPOH_API_KEY",
    )
    parser.add_argument("--verbose-logs", action="store_true", help="show backend request logs during the run")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_budget_config(args.budget_file)
    fixture = resolve_fixture(config, args.fixture)
    warmups = int(args.warmups if args.warmups is not None else config.get("default_warmups", 1))
    repetitions = int(args.repetitions if args.repetitions is not None else config.get("default_repetitions", 5))
    if warmups < 0:
        raise SystemExit("--warmups must be >= 0")
    if repetitions <= 0:
        raise SystemExit("--repetitions must be > 0")

    cases = build_cases(
        config=config,
        fixture_path=fixture,
        surfaces=list(args.surfaces or VALID_SURFACES),
        profiles=list(args.profiles or VALID_PROFILES),
    )
    if args.base_url:
        api_key = (
            args.api_key
            if args.api_key is not None
            else os.environ.get("KAYPOH_LATENCY_SLO_API_KEY", os.environ.get("KAYPOH_API_KEY", ""))
        )
        results = run_live_http_gate(
            cases=cases,
            warmups=warmups,
            repetitions=repetitions,
            base_url=args.base_url,
            api_key=api_key,
        )
    else:
        results = run_gate(
            cases=cases,
            warmups=warmups,
            repetitions=repetitions,
            quiet_logs=not args.verbose_logs,
        )
    print(render_summary(results))
    if args.write_report:
        print(f"\nJSON report: {write_report(results, DEFAULT_REPORT_DIR)}")

    failed = [item for item in results if not item["passed"]]
    if failed and not args.no_fail:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
