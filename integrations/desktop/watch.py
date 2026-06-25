from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

DEFAULT_BASE_URL = "http://127.0.0.1:8765"
DEFAULT_SUFFIXES = (".txt", ".md", ".csv", ".json", ".eml")


@dataclass(frozen=True)
class WatchConfig:
    base_url: str = DEFAULT_BASE_URL
    source_jurisdiction: str = "SG"
    destination_jurisdiction: str = "SG"
    document_type: str = "generic"
    review_profile: str = "strict"
    timeout_seconds: float = 10.0
    anonymize_output_dir: Path | None = None
    local_token: str = ""
    notify: bool = False


@dataclass(frozen=True)
class ReviewSummary:
    source: str
    overall_risk: str
    finding_count: int
    document_score: float
    anonymized_path: str | None = None


def _post_json(base_url: str, path: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    return _post_json_with_headers(base_url, path, payload, timeout_seconds, {})


def _post_json_with_headers(
    base_url: str,
    path: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    headers: dict[str, str],
) -> dict[str, Any]:
    request_headers = {"content-type": "application/json", **headers}
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{path} failed with HTTP {exc.code}: {detail}") from exc


def _payload(text: str, config: WatchConfig) -> dict[str, Any]:
    return {
        "text": text,
        "source_jurisdiction": config.source_jurisdiction,
        "destination_jurisdiction": config.destination_jurisdiction,
        "document_type": config.document_type,
        "review_profile": config.review_profile,
        "include_suggestions": True,
    }


def review_text(text: str, *, source: str, config: WatchConfig) -> ReviewSummary:
    response = _post_json_with_headers(
        config.base_url,
        "/review",
        _payload(text, config),
        config.timeout_seconds,
        _local_headers(config),
    )
    return ReviewSummary(
        source=source,
        overall_risk=str(response.get("overall_risk") or "UNKNOWN"),
        finding_count=len(response.get("findings") or []),
        document_score=float(response.get("document_score") or 0.0),
    )


def anonymize_text(text: str, *, source: str, config: WatchConfig) -> str | None:
    if config.anonymize_output_dir is None:
        return None
    response = _post_json_with_headers(
        config.base_url,
        "/anonymize",
        _payload(text, config),
        config.timeout_seconds,
        _local_headers(config),
    )
    anonymized = str(response.get("anonymized_text") or "")
    config.anonymize_output_dir.mkdir(parents=True, exist_ok=True)
    target = config.anonymize_output_dir / f"{Path(source).name}.anonymized.txt"
    target.write_text(anonymized, encoding="utf-8")
    return str(target)


def review_file(path: Path, config: WatchConfig) -> ReviewSummary:
    text = path.read_text(encoding="utf-8")
    summary = review_text(text, source=str(path), config=config)
    anonymized_path = anonymize_text(text, source=str(path), config=config) if summary.finding_count else None
    return ReviewSummary(
        source=summary.source,
        overall_risk=summary.overall_risk,
        finding_count=summary.finding_count,
        document_score=summary.document_score,
        anonymized_path=anonymized_path,
    )


def scan_paths(paths: Iterable[Path], config: WatchConfig) -> list[ReviewSummary]:
    summaries: list[ReviewSummary] = []
    for path in paths:
        if path.is_file():
            summary = review_file(path, config)
            summaries.append(summary)
            _emit_summary(summary, config)
    return summaries


def _tracked_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)


def changed_files(root: Path, seen: dict[Path, float], suffixes: tuple[str, ...] = DEFAULT_SUFFIXES) -> list[Path]:
    changed: list[Path] = []
    for path in _tracked_files(root, suffixes):
        mtime = path.stat().st_mtime
        if seen.get(path) == mtime:
            continue
        seen[path] = mtime
        changed.append(path)
    return changed


def _clipboard_text() -> str:
    if platform.system() != "Darwin":
        return ""
    result = subprocess.run(["pbpaste"], capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else ""


def _read_token_file(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return path.expanduser().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _local_headers(config: WatchConfig) -> dict[str, str]:
    return {"X-Junas-Local-Token": config.local_token} if config.local_token else {}


def poll_clipboard_once(config: WatchConfig, *, previous: str = "") -> tuple[str, ReviewSummary | None]:
    text = _clipboard_text()
    if not text or text == previous:
        return text, None
    summary = review_text(text, source="clipboard", config=config)
    _emit_summary(summary, config)
    return text, summary


def _notify(summary: ReviewSummary) -> None:
    title = "Junas review findings"
    message = f"{summary.finding_count} findings in {summary.source}"
    if platform.system() == "Darwin":
        subprocess.run(
            ["osascript", "-e", f'display notification "{message}" with title "{title}"'],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _emit_summary(summary: ReviewSummary, config: WatchConfig) -> None:
    print(json.dumps(summary.__dict__, sort_keys=True), flush=True)
    if config.notify and summary.finding_count:
        _notify(summary)


def _config_from_args(args: argparse.Namespace) -> WatchConfig:
    local_token = (
        args.local_token
        or os.environ.get("JUNAS_LOCAL_DAEMON_TOKEN", "")
        or _read_token_file(args.local_token_file)
    )
    return WatchConfig(
        base_url=args.base_url,
        source_jurisdiction=args.source_jurisdiction,
        destination_jurisdiction=args.destination_jurisdiction,
        document_type=args.document_type,
        review_profile=args.review_profile,
        timeout_seconds=args.timeout_seconds,
        anonymize_output_dir=args.anonymize_output_dir,
        local_token=local_token,
        notify=args.notify,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Opt-in junas-local clipboard / watched-folder fallback")
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--base-url", default=os.environ.get("JUNAS_LOCAL_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--source-jurisdiction", default="SG")
    parser.add_argument("--destination-jurisdiction", default="SG")
    parser.add_argument("--document-type", default="generic")
    parser.add_argument("--review-profile", choices=("strict", "audit_grade"), default="strict")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--watch-folder", type=Path)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--clipboard", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("--anonymize-output-dir", type=Path)
    parser.add_argument("--local-token", default="")
    parser.add_argument("--local-token-file", type=Path)
    args = parser.parse_args(argv)
    config = _config_from_args(args)
    if args.paths:
        scan_paths(args.paths, config)
    if args.watch_folder:
        seen: dict[Path, float] = {}
        scan_paths(changed_files(args.watch_folder, seen), config)
        if args.once:
            return 0
        while True:
            time.sleep(max(0.25, args.poll_seconds))
            scan_paths(changed_files(args.watch_folder, seen), config)
    if args.clipboard:
        previous, _ = poll_clipboard_once(config)
        if args.once:
            return 0
        while True:
            time.sleep(max(0.25, args.poll_seconds))
            previous, _ = poll_clipboard_once(config, previous=previous)
    if not args.paths and not args.watch_folder and not args.clipboard:
        parser.error("provide file paths, --watch-folder, or --clipboard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
