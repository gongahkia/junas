from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO
from urllib.parse import urlparse


@dataclass(frozen=True)
class DemoFrame:
    key: str
    surface: str
    fake_secret: str
    sample_text: str
    expected_signal: str


@dataclass(frozen=True)
class DoctorResult:
    status: str
    name: str
    detail: str
    remediation: str


DEMO_FRAMES: tuple[DemoFrame, ...] = (
    DemoFrame(
        key="browser-prompt",
        surface="browser GenAI prompt",
        fake_secret="AWS_ACCESS_KEY_ID=AKIA-FAKE-DEMO-0000",
        sample_text=("Before pasting to GenAI, remove FAKE-SG-NRIC-S1234567D for Jane Demo <jane.demo@example.test>."),
        expected_signal="fake secret + PII-shaped text",
    ),
    DemoFrame(
        key="outlook-send",
        surface="Outlook pre-send",
        fake_secret="GITHUB_TOKEN=ghp_FAKE_DEMO_TOKEN_0000",
        sample_text=("Send the Project Raven FAKE-MNPI draft to Alex Example at +1-555-0100 after approval."),
        expected_signal="fake token + MNPI-shaped text",
    ),
    DemoFrame(
        key="dms-upload",
        surface="DMS upload",
        fake_secret="OPENAI_API_KEY=sk-fake-demo",
        sample_text=("Upload fake passport FAKE-P0000000 and demo account DEMO-0000-0000 for Taylor Example."),
        expected_signal="fake API key + identifier-shaped text",
    ),
    DemoFrame(
        key="slack-like",
        surface="internal chat",
        fake_secret="SLACK_BOT_TOKEN=xoxb-fake-demo",
        sample_text=("Post only the redacted demo note; DOB 1900-01-01 and employee id DEMO-EMP-0001 are synthetic."),
        expected_signal="fake bot token + special-category-shaped text",
    ),
)

DAL_PATHS = (
    Path("/Library/CoreMediaIO/Plug-Ins/DAL"),
    Path.home() / "Library/CoreMediaIO/Plug-Ins/DAL",
)


def selected_demo_frames(case: str, frame_count: int) -> tuple[DemoFrame, ...]:
    if frame_count < 1:
        raise ValueError("--frames must be >= 1")
    frames = DEMO_FRAMES
    if case != "all":
        frames = tuple(frame for frame in DEMO_FRAMES if frame.key == case)
        if not frames:
            valid = ", ".join(frame.key for frame in DEMO_FRAMES)
            raise ValueError(f"unknown demo case {case!r}; expected one of: {valid}")
    return tuple(frames[index % len(frames)] for index in range(frame_count))


def render_demo(*, case: str = "all", frames: int | None = None) -> str:
    frame_count = frames if frames is not None else len(DEMO_FRAMES)
    selected = selected_demo_frames(case, frame_count)
    lines = [
        "Aki fake-secret demo",
        "All values below are synthetic FAKE/DEMO fixtures for screenshots and bug reports.",
        "",
    ]
    for index, frame in enumerate(selected, start=1):
        lines.extend(
            [
                f"frame {index:02d}/{len(selected):02d} | {frame.key} | {frame.surface}",
                f"  fake_secret: {frame.fake_secret}",
                f"  sample_text: {frame.sample_text}",
                f"  expected_signal: {frame.expected_signal}",
                f"  repro: aki demo --case {frame.key} --frames 1",
                "",
            ]
        )
    lines.append("demo_completed: true")
    return "\n".join(lines) + "\n"


def run_demo(args: argparse.Namespace, *, stdout: TextIO | None = None) -> int:
    if stdout is None:
        stdout = sys.stdout
    try:
        output = render_demo(case=args.case, frames=args.frames)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.delay <= 0:
        stdout.write(output)
        return 0
    lines = output.splitlines(keepends=True)
    for line in lines:
        stdout.write(line)
        stdout.flush()
        if line.startswith("frame "):
            time.sleep(args.delay)
    return 0


def _plugin_paths() -> tuple[Path, ...]:
    plugins: list[Path] = []
    for path in DAL_PATHS:
        if path.is_dir():
            plugins.extend(sorted(path.glob("*.plugin")))
    return tuple(plugins)


def _check_screen_capture() -> DoctorResult:
    if platform.system() != "Darwin":
        return DoctorResult(
            status="warn",
            name="ScreenCaptureKit permission",
            detail="macOS ScreenCaptureKit is not available on this platform.",
            remediation="Run this command on the Mac that will perform capture.",
        )
    if not shutil.which("screencapture"):
        return DoctorResult(
            status="fail",
            name="ScreenCaptureKit permission",
            detail="macOS screencapture helper was not found.",
            remediation=(
                "Check the macOS install; ScreenCaptureKit diagnostics require the standard screencapture tool."
            ),
        )
    return DoctorResult(
        status="warn",
        name="ScreenCaptureKit permission",
        detail="Permission cannot be verified without a capture attempt or macOS TCC prompt.",
        remediation=(
            "Open System Settings > Privacy & Security > Screen & System Audio Recording, "
            "enable the terminal/app that runs Aki, then rerun this command."
        ),
    )


def _check_coremediaio() -> DoctorResult:
    existing = [path for path in DAL_PATHS if path.is_dir()]
    if existing:
        paths = ", ".join(str(path) for path in existing)
        return DoctorResult(
            status="pass",
            name="CoreMediaIO DAL state",
            detail=f"DAL plugin directory exists: {paths}.",
            remediation="No action needed unless the virtual camera check below is warn/fail.",
        )
    return DoctorResult(
        status="warn",
        name="CoreMediaIO DAL state",
        detail="No CoreMediaIO DAL plugin directory was found.",
        remediation="Install OBS virtual camera or another DAL plugin if video capture/output is required.",
    )


def _check_virtual_camera() -> DoctorResult:
    plugins = _plugin_paths()
    if plugins:
        names = ", ".join(plugin.name for plugin in plugins)
        return DoctorResult(
            status="pass",
            name="Virtual-camera installation",
            detail=f"Found DAL plugin(s): {names}.",
            remediation="No action needed.",
        )
    return DoctorResult(
        status="warn",
        name="Virtual-camera installation",
        detail="No DAL virtual-camera plugin was found.",
        remediation=(
            "Install OBS and enable its virtual camera if `aki redact` or capture workflows need camera output."
        ),
    )


def _parse_obs_target(obs_url: str) -> tuple[str, int]:
    parsed = urlparse(obs_url)
    if not parsed.scheme:
        parsed = urlparse(f"ws://{obs_url}")
    host = parsed.hostname or "127.0.0.1"
    if parsed.port:
        return host, parsed.port
    if parsed.scheme == "wss":
        return host, 443
    return host, 4455


def _check_obs(obs_url: str) -> DoctorResult:
    if not obs_url:
        return DoctorResult(
            status="warn",
            name="OBS reachability",
            detail="OBS websocket URL is not configured; reachability check skipped.",
            remediation="Set AKI_OBS_WEBSOCKET_URL=ws://127.0.0.1:4455 when OBS integration is relevant.",
        )
    try:
        host, port = _parse_obs_target(obs_url)
        with socket.create_connection((host, port), timeout=1.5):
            pass
    except OSError as exc:
        return DoctorResult(
            status="fail",
            name="OBS reachability",
            detail=f"Could not connect to {obs_url}: {exc}.",
            remediation="Start OBS, enable websocket server, confirm host/port, then rerun `aki doctor`.",
        )
    return DoctorResult(
        status="pass",
        name="OBS reachability",
        detail=f"TCP connection to {obs_url} succeeded.",
        remediation="No action needed.",
    )


def _check_tesseract(env: dict[str, str]) -> DoctorResult:
    prefix = env.get("TESSDATA_PREFIX", "").strip()
    if prefix and not Path(prefix).expanduser().exists():
        return DoctorResult(
            status="fail",
            name="Tesseract data path",
            detail=f"TESSDATA_PREFIX does not exist: {prefix}.",
            remediation="Set TESSDATA_PREFIX to the tessdata directory or unset it to use the system default.",
        )
    binary = shutil.which("tesseract")
    if not binary:
        return DoctorResult(
            status="warn",
            name="Tesseract data path",
            detail="tesseract binary was not found; OCR paths will be unavailable.",
            remediation="Install Tesseract, for example `brew install tesseract`, when OCR is needed.",
        )
    try:
        result = subprocess.run(
            [binary, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return DoctorResult(
            status="fail",
            name="Tesseract data path",
            detail=f"Could not list Tesseract languages: {exc}.",
            remediation="Reinstall Tesseract or fix TESSDATA_PREFIX.",
        )
    if result.returncode != 0:
        return DoctorResult(
            status="fail",
            name="Tesseract data path",
            detail=(result.stderr or result.stdout or "tesseract --list-langs failed").strip(),
            remediation="Reinstall language data or set TESSDATA_PREFIX to a valid tessdata directory.",
        )
    languages = [line.strip() for line in result.stdout.splitlines() if line.strip() and "List of" not in line]
    if not languages:
        return DoctorResult(
            status="fail",
            name="Tesseract data path",
            detail="Tesseract returned no installed languages.",
            remediation="Install tessdata language files, including eng for default OCR smoke tests.",
        )
    return DoctorResult(
        status="pass",
        name="Tesseract data path",
        detail=f"tesseract is installed with languages: {', '.join(languages[:8])}.",
        remediation="No action needed.",
    )


def run_doctor_checks(*, obs_url: str = "", env: dict[str, str] | None = None) -> tuple[DoctorResult, ...]:
    resolved_env = dict(os.environ if env is None else env)
    resolved_obs_url = (
        obs_url or resolved_env.get("AKI_OBS_WEBSOCKET_URL", "") or resolved_env.get("OBS_WEBSOCKET_URL", "")
    )
    return (
        _check_screen_capture(),
        _check_coremediaio(),
        _check_virtual_camera(),
        _check_obs(resolved_obs_url),
        _check_tesseract(resolved_env),
    )


def render_doctor(results: tuple[DoctorResult, ...]) -> str:
    lines = [
        "Aki doctor",
        "telemetry: disabled; diagnostics stay local and are not transmitted",
        "",
    ]
    counts = {"pass": 0, "warn": 0, "fail": 0}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
        lines.extend(
            [
                f"{result.status}: {result.name}",
                f"  detail: {result.detail}",
                f"  fix: {result.remediation}",
                "",
            ]
        )
    lines.append(f"summary: pass={counts.get('pass', 0)} warn={counts.get('warn', 0)} fail={counts.get('fail', 0)}")
    return "\n".join(lines) + "\n"


def run_doctor(args: argparse.Namespace, *, stdout: TextIO | None = None) -> int:
    if stdout is None:
        stdout = sys.stdout
    results = run_doctor_checks(obs_url=args.obs_url)
    if args.json:
        payload = {
            "telemetry": "disabled",
            "results": [result.__dict__ for result in results],
        }
        stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        stdout.write(render_doctor(results))
    return 1 if any(result.status == "fail" for result in results) else 0


def _dict_finding(**kwargs):
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
        "Aki rules test",
        f"pack: {pack_path}",
        f"findings: {len(findings)}",
    ]
    for finding in findings:
        lines.append(
            f"- {finding['rule']} {finding['severity']} {finding['matched_text']} ({finding['start']}:{finding['end']})"
        )
    stdout.write("\n".join(lines) + "\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aki", description="Junas local helper CLI.")
    subparsers = parser.add_subparsers(dest="command")
    demo = subparsers.add_parser(
        "demo",
        help="render deterministic fake-secret and PII-shaped examples",
        description="Render deterministic fake-secret and PII-shaped examples for screenshots and bug reports.",
    )
    demo.add_argument("--case", choices=("all", *(frame.key for frame in DEMO_FRAMES)), default="all")
    demo.add_argument("--frames", type=int, default=len(DEMO_FRAMES))
    demo.add_argument("--delay", type=float, default=0.0, help="sleep seconds between rendered frames")
    demo.set_defaults(func=run_demo)
    doctor = subparsers.add_parser(
        "doctor",
        help="run local diagnostics without telemetry",
        description="Run local diagnostics for capture, virtual camera, OBS, and OCR setup without telemetry.",
    )
    doctor.add_argument("--obs-url", default="", help="OBS websocket URL, e.g. ws://127.0.0.1:4455")
    doctor.add_argument("--json", action="store_true", help="emit machine-readable local diagnostics")
    doctor.set_defaults(func=run_doctor)
    rules = subparsers.add_parser(
        "rules",
        help="test local secret rule packs",
        description="Test local community secret rule packs before opting them into Junas review.",
    )
    rules_subparsers = rules.add_subparsers(dest="rules_command")
    rules_test = rules_subparsers.add_parser(
        "test",
        help="run a local Gitleaks TOML rule pack against text",
        description="Run a local Gitleaks TOML rule pack through the same bounded importer used by Junas review.",
    )
    rules_test.add_argument("--gitleaks", required=True, help="path to a local Gitleaks TOML rule pack")
    input_group = rules_test.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--text", help="text to scan")
    input_group.add_argument("--text-file", help="UTF-8 text fixture to scan")
    rules_test.add_argument("--jurisdiction", default="US", help="jurisdiction label for emitted findings")
    rules_test.add_argument("--max-matches", type=int, default=64, help="maximum findings to emit")
    rules_test.add_argument("--json", action="store_true", help="emit machine-readable findings")
    rules_test.set_defaults(func=run_rules_test)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
