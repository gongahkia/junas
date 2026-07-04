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
FOREGROUND_PROFILE_CHOICES = ("auto", "off", "terminal", "chat", "editor", "browser", "broad")


@dataclass(frozen=True)
class WatchConfig:
    base_url: str = DEFAULT_BASE_URL
    source_jurisdiction: str = "SG"
    destination_jurisdiction: str = "SG"
    document_type: str = "generic"
    review_profile: str = "strict"
    surface: str = "desktop"
    workflow: str = "desktop_watch"
    detector_profile: str = ""
    foreground_app: str = ""
    timeout_seconds: float = 10.0
    anonymize_output_dir: Path | None = None
    local_token: str = ""
    notify: bool = False


@dataclass(frozen=True)
class ForegroundApp:
    name: str
    bundle_id: str = ""


@dataclass(frozen=True)
class ForegroundProfile:
    name: str
    document_type: str
    review_profile: str
    surface: str
    workflow: str
    description: str


@dataclass(frozen=True)
class ReviewSummary:
    source: str
    overall_risk: str
    finding_count: int
    document_score: float
    anonymized_path: str | None = None
    detector_profile: str = ""
    foreground_app: str = ""


FOREGROUND_PROFILES: dict[str, ForegroundProfile] = {
    "terminal": ForegroundProfile(
        name="terminal",
        document_type="terminal_buffer",
        review_profile="strict",
        surface="desktop",
        workflow="desktop_watch",
        description="secrets-heavy terminal text",
    ),
    "chat": ForegroundProfile(
        name="chat",
        document_type="chat_message",
        review_profile="strict",
        surface="other",
        workflow="collaboration_message",
        description="email and PII-heavy chat text",
    ),
    "editor": ForegroundProfile(
        name="editor",
        document_type="source_buffer",
        review_profile="audit_grade",
        surface="desktop",
        workflow="desktop_watch",
        description="broad source/editor text",
    ),
    "browser": ForegroundProfile(
        name="browser",
        document_type="genai_prompt",
        review_profile="strict",
        surface="browser_genai",
        workflow="prompt_submit",
        description="browser GenAI prompt text",
    ),
    "broad": ForegroundProfile(
        name="broad",
        document_type="generic",
        review_profile="audit_grade",
        surface="desktop",
        workflow="desktop_watch",
        description="broad local fallback review",
    ),
}

_FOREGROUND_RULES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "terminal",
        (
            "com.apple.Terminal",
            "com.googlecode.iterm2",
            "dev.warp.Warp-Stable",
            "com.github.wez.wezterm",
            "net.kovidgoyal.kitty",
            "org.alacritty",
            "com.mitchellh.ghostty",
        ),
        ("terminal", "iterm", "warp", "wezterm", "kitty", "alacritty", "ghostty", "hyper"),
    ),
    (
        "chat",
        ("com.tinyspeck.slackmacgap", "com.hnc.Discord", "com.microsoft.teams"),
        ("slack", "discord", "microsoft teams"),
    ),
    (
        "editor",
        ("com.microsoft.VSCode", "com.todesktop.230313mzl4w4u92", "com.vscodium"),
        ("visual studio code", "vscode", "cursor", "vscodium"),
    ),
    (
        "browser",
        (
            "com.apple.Safari",
            "com.google.Chrome",
            "com.microsoft.edgemac",
            "org.mozilla.firefox",
            "com.brave.Browser",
            "company.thebrowser.Browser",
        ),
        ("safari", "google chrome", "microsoft edge", "firefox", "brave browser", "arc"),
    ),
)


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
        raise RuntimeError(f"{path} failed with HTTP {exc.code}") from exc


def _payload(text: str, config: WatchConfig) -> dict[str, Any]:
    return {
        "text": text,
        "source_jurisdiction": config.source_jurisdiction,
        "destination_jurisdiction": config.destination_jurisdiction,
        "document_type": config.document_type,
        "review_profile": config.review_profile,
        "surface": config.surface,
        "workflow": config.workflow,
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
        detector_profile=config.detector_profile,
        foreground_app=config.foreground_app,
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
        detector_profile=summary.detector_profile,
        foreground_app=summary.foreground_app,
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


def _detect_foreground_app() -> ForegroundApp | None:
    if platform.system() != "Darwin":
        return None
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                "set frontApp to path to frontmost application as text",
                "-e",
                "set appName to name of application frontApp",
                "-e",
                "set bundleId to id of application frontApp",
                "-e",
                'return appName & "\t" & bundleId',
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    parts = result.stdout.strip().split("\t", 1)
    if not parts or not parts[0]:
        return None
    return ForegroundApp(name=parts[0], bundle_id=parts[1] if len(parts) > 1 else "")


def _profile_name_for_app(app: ForegroundApp) -> str:
    name = app.name.casefold()
    bundle_id = app.bundle_id
    for profile_name, bundle_ids, name_tokens in _FOREGROUND_RULES:
        if bundle_id in bundle_ids:
            return profile_name
        if any(token in name for token in name_tokens):
            return profile_name
    return ""


def _apply_foreground_profile(
    config: WatchConfig, profile: ForegroundProfile, app: ForegroundApp | None
) -> WatchConfig:
    return WatchConfig(
        base_url=config.base_url,
        source_jurisdiction=config.source_jurisdiction,
        destination_jurisdiction=config.destination_jurisdiction,
        document_type=profile.document_type,
        review_profile=profile.review_profile,
        surface=profile.surface,
        workflow=profile.workflow,
        detector_profile=profile.name,
        foreground_app=app.name if app else "",
        timeout_seconds=config.timeout_seconds,
        anonymize_output_dir=config.anonymize_output_dir,
        local_token=config.local_token,
        notify=config.notify,
    )


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
        args.local_token or os.environ.get("JUNAS_LOCAL_DAEMON_TOKEN", "") or _read_token_file(args.local_token_file)
    )
    config = WatchConfig(
        base_url=args.base_url,
        source_jurisdiction=args.source_jurisdiction,
        destination_jurisdiction=args.destination_jurisdiction,
        document_type=args.document_type,
        review_profile=args.review_profile,
        surface="desktop",
        workflow="desktop_watch",
        timeout_seconds=args.timeout_seconds,
        anonymize_output_dir=args.anonymize_output_dir,
        local_token=local_token,
        notify=args.notify,
    )
    mode = args.foreground_profile
    if mode == "off":
        return config
    if mode != "auto":
        return _apply_foreground_profile(config, FOREGROUND_PROFILES[mode], None)
    app = _detect_foreground_app()
    if app is None:
        return config
    profile_name = _profile_name_for_app(app)
    if not profile_name:
        return config
    return _apply_foreground_profile(config, FOREGROUND_PROFILES[profile_name], app)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Opt-in junas-local clipboard / watched-folder fallback")
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--base-url", default=os.environ.get("JUNAS_LOCAL_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--source-jurisdiction", default="SG")
    parser.add_argument("--destination-jurisdiction", default="SG")
    parser.add_argument("--document-type", default="generic")
    parser.add_argument("--review-profile", choices=("strict", "audit_grade"), default="strict")
    parser.add_argument(
        "--foreground-profile",
        choices=FOREGROUND_PROFILE_CHOICES,
        default=os.environ.get("JUNAS_WATCH_FOREGROUND_PROFILE", "auto"),
        help="auto-select a review profile from the macOS foreground app, force one, or use off",
    )
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
