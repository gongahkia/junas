#!/usr/bin/env python3
"""Benchmark classify latency for plain-text inputs."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
TIMING_KEY_ORDER = ["review", "extract", "anonymize", "cache_hit", "total"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark /classify latency for text files")
    parser.add_argument("inputs", nargs="*", help="text files or directories containing .txt files")
    parser.add_argument("--glob", dest="glob_pattern", help="optional glob relative to repo root")
    parser.add_argument("--repetitions", type=int, default=5, help="measured runs per file")
    parser.add_argument("--warmups", type=int, default=1, help="warmup runs per file before measurement")
    parser.add_argument("--port", type=int, default=8130, help="backend port when spawning locally")
    parser.add_argument("--timeout", type=int, default=180, help="seconds to wait for backend readiness")
    parser.add_argument("--config", type=Path, help="optional config file to use when spawning the backend")
    parser.add_argument("--no-server", action="store_true", help="use an already-running backend")
    parser.add_argument("--url", help="base URL for an already-running backend")
    return parser.parse_args()


def resolve_inputs(args: argparse.Namespace) -> list[Path]:
    paths: list[Path] = []

    for raw in args.inputs:
        path = Path(raw).expanduser()
        if path.is_dir():
            paths.extend(sorted(path.glob("*.txt")))
        elif path.is_file():
            paths.append(path)

    if args.glob_pattern:
        paths.extend(sorted(ROOT.glob(args.glob_pattern)))

    seen: set[Path] = set()
    unique_paths: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved.suffix.lower() != ".txt":
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(resolved)

    if not unique_paths:
        raise SystemExit("no .txt inputs found")

    return unique_paths


def wait_for_ready(base_url: str, timeout: int) -> dict:
    deadline = time.time() + timeout
    ready_url = f"{base_url}/ready"

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(ready_url, timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            time.sleep(1)
            continue

        if payload.get("ready") is True:
            return payload

        time.sleep(1)

    raise TimeoutError(f"timed out waiting for backend readiness at {ready_url}")


def start_backend(args: argparse.Namespace) -> subprocess.Popen:
    env = {**os.environ}
    env.setdefault("UV_PROJECT_ENVIRONMENT", str(ROOT / ".venv-uv"))
    env.setdefault("UV_PYTHON", "3.12")
    if args.config:
        env["JUNAS_CONFIG"] = str(args.config.resolve())

    if shutil.which("uv"):
        cmd = ["uv", "run", "uvicorn", "junas.backend.main:app", "--host", "127.0.0.1", "--port", str(args.port)]
    else:
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "junas.backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
        ]
    return subprocess.Popen(cmd, cwd=str(ROOT), env=env)


def request_classification(base_url: str, text: str) -> tuple[float, dict]:
    body = json.dumps({"text": text}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/classify",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=300) as response:
        payload = json.loads(response.read().decode("utf-8"))
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
    return elapsed_ms, payload


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]

    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round((ordered[lower] * (1 - weight)) + (ordered[upper] * weight), 3)


def summarize_runs(runs: list[dict]) -> dict:
    latencies = [float(run["client_latency_ms"]) for run in runs]
    server_latencies = [float(run["server_total_ms"]) for run in runs if run["server_total_ms"] is not None]
    base = runs[0]
    return {
        "file_name": base["file_name"],
        "file_path": base["file_path"],
        "word_count": base["word_count"],
        "char_count": base["char_count"],
        "runs": len(runs),
        "min_ms": round(min(latencies), 3),
        "mean_ms": round(mean(latencies), 3),
        "p50_ms": percentile(latencies, 0.50),
        "p95_ms": percentile(latencies, 0.95),
        "max_ms": round(max(latencies), 3),
        "mean_server_ms": round(mean(server_latencies), 3) if server_latencies else None,
    }


def ordered_timing_keys(runs: list[dict]) -> list[str]:
    seen = {
        key
        for run in runs
        for key in (run.get("timings_ms") or {})
    }
    ordered = [key for key in TIMING_KEY_ORDER if key in seen]
    extras = sorted(seen - set(ordered))
    return ordered + extras


def render_file_detail_block(summary: dict, runs: list[dict]) -> str:
    lines = [
        f"File: {summary['file_name']}",
        f"Path: {summary['file_path']}",
        f"Words: {summary['word_count']}",
        f"Chars: {summary['char_count']}",
        f"Measured runs: {summary['runs']}",
        (
            "Summary: "
            f"min={summary['min_ms']:.3f} ms, "
            f"mean={summary['mean_ms']:.3f} ms, "
            f"p50={summary['p50_ms']:.3f} ms, "
            f"p95={summary['p95_ms']:.3f} ms, "
            f"max={summary['max_ms']:.3f} ms"
        ),
    ]

    if summary["mean_server_ms"] is not None:
        lines.append(f"Mean backend total: {summary['mean_server_ms']:.3f} ms")

    timing_keys = ordered_timing_keys(runs)
    if timing_keys:
        lines.append("Average backend timings per step (ms):")
        for key in timing_keys:
            values = [
                float(run["timings_ms"][key])
                for run in runs
                if key in (run.get("timings_ms") or {})
            ]
            if not values:
                continue
            lines.append(
                f"- {key}: mean={mean(values):.3f} min={min(values):.3f} max={max(values):.3f}"
            )

    lines.append("Per-run details:")
    for run in runs:
        lines.append(
            f"- Run {run['run_index']}: "
            f"classification={run.get('classification')} "
            f"cache_status={run.get('cache_status')} "
            f"degraded={run.get('degraded')}"
        )
        lines.append(f"  client_latency_ms={float(run['client_latency_ms']):.3f}")
        server_total = run.get("server_total_ms")
        lines.append(
            "  server_total_ms="
            + ("null" if server_total is None else f"{float(server_total):.3f}")
        )
        timings = run.get("timings_ms") or {}
        if timings:
            lines.append("  timings_ms:")
            for key in timing_keys:
                if key not in timings:
                    continue
                lines.append(f"    {key}: {float(timings[key]):.3f}")

    return "\n".join(lines)


def render_summary_table(summaries: list[dict]) -> str:
    lines = []
    lines.append(
        f"{'file':<28} {'words':>8} {'chars':>8} {'min':>10} {'mean':>10} {'p50':>10} {'p95':>10} {'max':>10}"
    )
    lines.append("-" * 100)
    for item in summaries:
        lines.append(
            f"{item['file_name']:<28} "
            f"{item['word_count']:>8} "
            f"{item['char_count']:>8} "
            f"{item['min_ms']:>10.3f} "
            f"{item['mean_ms']:>10.3f} "
            f"{item['p50_ms']:>10.3f} "
            f"{item['p95_ms']:>10.3f} "
            f"{item['max_ms']:>10.3f}"
        )
    return "\n".join(lines)


def write_reports(
    summaries: list[dict],
    raw_runs: list[dict],
    *,
    base_url: str,
    input_paths: list[Path],
    repetitions: int,
    warmups: int,
) -> tuple[Path, Path, Path]:
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    json_path = reports_dir / f"latency_{timestamp}.json"
    csv_path = reports_dir / f"latency_{timestamp}.csv"
    txt_path = reports_dir / f"latency_{timestamp}.txt"

    json_path.write_text(
        json.dumps({"summaries": summaries, "runs": raw_runs}, indent=2),
        encoding="utf-8",
    )

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "file_name",
                "file_path",
                "word_count",
                "char_count",
                "runs",
                "min_ms",
                "mean_ms",
                "p50_ms",
                "p95_ms",
                "max_ms",
                "mean_server_ms",
            ],
        )
        writer.writeheader()
        writer.writerows(summaries)

    lines = [
        "Junas Latency Benchmark Report",
        "",
        f"Generated: {timestamp}",
        f"Target URL: {base_url}",
        f"Warmups per file: {warmups}",
        f"Measured repetitions per file: {repetitions}",
        "",
        "Inputs:",
    ]
    for path in input_paths:
        lines.append(f"- {path}")
    lines.extend(
        [
            "",
            render_summary_table(summaries),
            "",
            "Detailed results:",
            "",
        ]
    )
    runs_by_path = {summary["file_path"]: [] for summary in summaries}
    for run in raw_runs:
        runs_by_path.setdefault(run["file_path"], []).append(run)
    for summary in summaries:
        file_runs = runs_by_path.get(summary["file_path"], [])
        lines.append(render_file_detail_block(summary, file_runs))
        lines.append("")
    lines.extend(
        [
            f"JSON report: {json_path}",
            f"CSV report : {csv_path}",
        ]
    )
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return json_path, csv_path, txt_path


def print_summary_table(summaries: list[dict]) -> None:
    print()
    print(render_summary_table(summaries))


def main() -> int:
    args = parse_args()
    input_paths = resolve_inputs(args)
    base_url = args.url or f"http://127.0.0.1:{args.port}"

    backend_proc: subprocess.Popen | None = None
    if not args.no_server:
        backend_proc = start_backend(args)

    try:
        wait_for_ready(base_url, args.timeout)

        raw_runs: list[dict] = []
        summaries: list[dict] = []

        for path in input_paths:
            text = path.read_text(encoding="utf-8")
            word_count = len(text.split())
            char_count = len(text)

            for _ in range(args.warmups):
                request_classification(base_url, text)

            file_runs: list[dict] = []
            for run_index in range(1, args.repetitions + 1):
                client_latency_ms, payload = request_classification(base_url, text)
                timings = payload.get("timings_ms") or {}
                observability = payload.get("observability") or {}
                run_payload = {
                    "file_name": path.name,
                    "file_path": str(path),
                    "word_count": word_count,
                    "char_count": char_count,
                    "run_index": run_index,
                    "classification": payload.get("classification"),
                    "cache_status": observability.get("cache_status"),
                    "degraded": observability.get("degraded"),
                    "client_latency_ms": client_latency_ms,
                    "server_total_ms": timings.get("total"),
                    "timings_ms": timings,
                }
                raw_runs.append(run_payload)
                file_runs.append(run_payload)

            summaries.append(summarize_runs(file_runs))

        print_summary_table(summaries)
        json_path, csv_path, txt_path = write_reports(
            summaries,
            raw_runs,
            base_url=base_url,
            input_paths=input_paths,
            repetitions=args.repetitions,
            warmups=args.warmups,
        )
        print()
        print(f"JSON report: {json_path}")
        print(f"CSV report : {csv_path}")
        print(f"TXT report : {txt_path}")
        return 0
    except urllib.error.HTTPError as exc:
        sys.stderr.write(f"request failed with HTTP {exc.code}: {exc.reason}\n")
        return 1
    finally:
        if backend_proc is not None:
            backend_proc.send_signal(signal.SIGTERM)
            try:
                backend_proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                backend_proc.kill()
                backend_proc.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
