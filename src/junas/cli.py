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


def run_tui(args: argparse.Namespace, *, stdout: TextIO | None = None) -> int:
    if stdout is None:
        stdout = sys.stdout
    stdout.write(
        "\n".join(
            [
                "Aki TUI",
                "power_user_surface: terminal",
                "menu_bar_entrypoint: Open TUI",
                "commands:",
                "- aki sidecar stdio",
                "- aki redact <video.mov> --output <redacted.mp4>",
                "- junas-watch --clipboard --once",
            ]
        )
        + "\n"
    )
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


def run_ocr_classify_region(args: argparse.Namespace, *, stdout: TextIO | None = None) -> int:
    if stdout is None:
        stdout = sys.stdout
    from junas.advisory.local_ocr_llm import (
        LocalOcrLLMSettings,
        LocalOcrRegionClassifier,
        settings_from_env,
    )

    env_settings = settings_from_env()
    settings = LocalOcrLLMSettings(
        enabled=bool(args.enable_local_llm or env_settings.enabled),
        provider=args.provider or env_settings.provider,
        base_url=args.base_url or env_settings.base_url,
        model=args.model or env_settings.model,
        timeout_seconds=args.timeout_seconds or env_settings.timeout_seconds,
        confidence_threshold=args.confidence_threshold or env_settings.confidence_threshold,
        max_chars=args.max_chars or env_settings.max_chars,
    )
    result = LocalOcrRegionClassifier(settings).classify_text(args.text, confidence=args.confidence)
    payload = result.__dict__
    if args.json:
        stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        stdout.write(
            "\n".join(
                [
                    "Aki OCR local-LLM classifier",
                    f"status: {result.status}",
                    f"label: {result.label}",
                    f"confidence: {result.confidence:.3f}",
                    f"reason: {result.reason}",
                    f"text_sha256: {result.text_sha256}",
                ]
            )
            + "\n"
        )
    return 2 if result.status == "error" else 0


def run_displays_list(args: argparse.Namespace, *, stdout: TextIO | None = None) -> int:
    if stdout is None:
        stdout = sys.stdout
    from junas.desktop import displays as display_tools

    sources = display_tools.list_displays()
    if args.json:
        stdout.write(json.dumps({"displays": [source.__dict__ for source in sources]}, indent=2, sort_keys=True) + "\n")
        return 0
    stdout.write("Aki displays\n")
    for source in sources:
        pixels = "unknown"
        if source.pixels:
            pixels = f"{source.pixels[0]}x{source.pixels[1]}"
        main = " main" if source.is_main else ""
        online = " online" if source.is_online else " offline"
        stdout.write(f"- {source.capture_index}: {source.name} {pixels}{main}{online}\n")
    if not sources:
        stdout.write("no displays detected\n")
    return 0


def run_displays_capture(args: argparse.Namespace, *, stdout: TextIO | None = None) -> int:
    if stdout is None:
        stdout = sys.stdout
    from junas.desktop import displays as display_tools

    try:
        plan = display_tools.build_capture_plan(
            display_tools.list_displays(),
            selected_indexes=args.display or (),
            output_dir=args.output_dir,
            video_seconds=args.video_seconds,
            ignore_missing=args.ignore_missing,
            timestamp=args.timestamp,
        )
    except display_tools.DisplaySelectionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        payload = {
            "commands": [
                {
                    "display": command.display.__dict__,
                    "output_path": str(command.output_path),
                    "argv": list(command.argv),
                }
                for command in plan
            ],
            "dry_run": args.dry_run,
        }
        stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        stdout.write("Aki display capture plan\n")
        for command in plan:
            stdout.write(f"- display {command.display.capture_index}: {' '.join(command.argv)}\n")
    if args.dry_run:
        return 0
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for command in plan:
        completed = subprocess.run(command.argv, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


def run_redact_video(args: argparse.Namespace, *, stdout: TextIO | None = None) -> int:
    if stdout is None:
        stdout = sys.stdout
    from junas.desktop import offline_video, time_buffer

    try:
        plan = offline_video.build_offline_video_redaction_plan(
            input_path=args.input_video,
            output_path=args.output,
            fps=args.fps,
            redaction_box=time_buffer.parse_redaction_box(args.box),
            detections_json=args.detections_json,
            gitleaks_path=args.gitleaks,
            overwrite=args.overwrite,
            create_parent=args.create_parent,
            ffmpeg_path=args.ffmpeg,
            require_ffmpeg=not args.dry_run,
        )
        payload = offline_video.plan_to_payload(plan, dry_run=args.dry_run)
        if not args.dry_run:
            payload = offline_video.redact_video(plan)
    except (offline_video.OfflineVideoRedactionError, time_buffer.TimeBufferError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return 0
    stdout.write(
        "\n".join(
            [
                "Aki offline video redaction",
                f"input_path: {payload['input_path']}",
                f"output_path: {payload['output_path']}",
                f"detection_mode: {payload['detection_mode']}",
                f"transform: {payload['transform']}",
                f"audio_preserved: {payload['audio_preserved']}",
            ]
        )
        + "\n"
    )
    return 0


def run_sidecar_stdio(args: argparse.Namespace, *, stdout: TextIO | None = None, stdin: TextIO | None = None) -> int:
    if stdout is None:
        stdout = sys.stdout
    if stdin is None:
        stdin = sys.stdin
    from junas.desktop import sidecar_protocol

    session = sidecar_protocol.SidecarSession()
    for line in stdin:
        if not line.strip():
            continue
        stdout.write(sidecar_protocol.encode_messages(session.handle(line)))
        stdout.flush()
        if session.should_exit:
            break
    return 0


def run_mp4_from_redacted_frames(args: argparse.Namespace, *, stdout: TextIO | None = None) -> int:
    if stdout is None:
        stdout = sys.stdout
    from junas.desktop import mp4_sink

    try:
        plan = mp4_sink.build_mp4_sink_plan(
            frames_dir=args.frames_dir,
            output_path=args.output,
            frame_pattern=args.pattern,
            fps=args.fps,
            overwrite=args.overwrite,
            create_parent=args.create_parent,
            ffmpeg_path=args.ffmpeg,
            require_ffmpeg=not args.dry_run,
        )
    except mp4_sink.Mp4SinkError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    payload = {
        "frames_dir": str(plan.frames_dir),
        "frame_pattern": plan.frame_pattern,
        "frame_count": len(plan.frames),
        "fps": plan.fps,
        "duration_seconds": plan.duration_seconds,
        "output_path": str(plan.output_path),
        "overwrite": plan.overwrite,
        "create_parent": plan.create_parent,
        "ffmpeg_path": plan.ffmpeg_path,
        "argv": list(plan.argv_template),
        "dry_run": args.dry_run,
    }
    if args.json and args.dry_run:
        stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    elif not args.json:
        stdout.write(
            "\n".join(
                [
                    "Aki MP4 sink",
                    f"frames: {len(plan.frames)}",
                    f"fps: {plan.fps}",
                    f"duration_seconds: {plan.duration_seconds}",
                    f"output_path: {plan.output_path}",
                    f"command: {' '.join(plan.argv_template)}",
                ]
            )
            + "\n"
        )
    if args.dry_run:
        return 0
    try:
        mp4_sink.encode_mp4(plan)
    except mp4_sink.Mp4SinkError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        payload["status"] = "written"
        stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        stdout.write(f"wrote: {plan.output_path}\n")
    return 0


def run_buffer_prototype(args: argparse.Namespace, *, stdout: TextIO | None = None) -> int:
    if stdout is None:
        stdout = sys.stdout
    from junas.desktop import time_buffer

    try:
        plan = time_buffer.build_time_buffer_plan(
            frames_dir=args.frames_dir,
            output_dir=args.output_dir,
            frame_pattern=args.pattern,
            fps=args.fps,
            seconds=args.seconds,
            redact_last_seconds=args.redact_last_seconds,
            redaction_box=time_buffer.parse_redaction_box(args.box),
            overwrite=args.overwrite,
            create_parent=args.create_parent,
            write_buffer_copy=args.write_buffer_copy,
        )
        payload = time_buffer.plan_to_payload(plan, dry_run=args.dry_run)
        if not args.dry_run:
            payload = time_buffer.write_time_buffer_output(plan)
    except time_buffer.TimeBufferError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return 0
    stdout.write(
        "\n".join(
            [
                "Aki time-buffer prototype",
                f"retained_frames: {payload['retained_frame_count']}",
                f"evicted_frames: {payload['evicted_frame_count']}",
                f"memory_bytes_estimate: {payload['memory_bytes_estimate']}",
                f"disk_bytes_estimate: {payload['disk_bytes_estimate']}",
                f"final_frames_dir: {payload['final_frames_dir']}",
                f"live_stream_undo_supported: {payload['live_stream_undo_supported']}",
            ]
        )
        + "\n"
    )
    return 0


def run_obs_prototype_source(args: argparse.Namespace, *, stdout: TextIO | None = None) -> int:
    if stdout is None:
        stdout = sys.stdout
    from junas.desktop.time_buffer import parse_redaction_box
    from junas.integrations import obs_source

    try:
        plan = obs_source.build_obs_source_prototype_plan(
            frames_dir=args.frames_dir,
            output_dir=args.output_dir,
            frame_pattern=args.pattern,
            redaction_box=parse_redaction_box(args.box),
            overwrite=args.overwrite,
            create_parent=args.create_parent,
        )
        payload = obs_source.plan_to_payload(plan, dry_run=args.dry_run)
        if not args.dry_run:
            payload = obs_source.run_obs_source_prototype(plan)
    except (obs_source.ObsSourcePrototypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return 0
    stdout.write(
        "\n".join(
            [
                "Aki OBS source prototype",
                f"frames: {payload['frame_count']}",
                f"transform: {payload['transform']}",
                f"processed_frames_dir: {payload['processed_frames_dir']}",
                f"native_plugin_shipped: {payload['native_plugin_shipped']}",
                f"virtual_camera_unchanged: {payload['virtual_camera_unchanged']}",
            ]
        )
        + "\n"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aki", description="Junas local helper CLI.")
    parser.add_argument("--tui", action="store_true", help="show the power-user terminal UI entrypoint")
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
    ocr = subparsers.add_parser(
        "ocr",
        help="run opt-in OCR helper prototypes",
        description="Run opt-in OCR helper prototypes that are disabled by default.",
    )
    ocr_subparsers = ocr.add_subparsers(dest="ocr_command")
    classify_region = ocr_subparsers.add_parser(
        "classify-region",
        help="classify one low-confidence OCR fragment with a local model",
        description="Classify one low-confidence OCR fragment with an opt-in local Ollama model.",
    )
    classify_region.add_argument("--text", required=True, help="OCR fragment text to classify")
    classify_region.add_argument("--confidence", type=float, required=True, help="OCR confidence from 0.0 to 1.0")
    classify_region.add_argument("--enable-local-llm", action="store_true", help="explicitly enable local model call")
    classify_region.add_argument("--provider", choices=("ollama",), help="local model provider")
    classify_region.add_argument("--base-url", help="loopback Ollama base URL")
    classify_region.add_argument("--model", help="local Ollama model name")
    classify_region.add_argument("--timeout-seconds", type=float, help="local model timeout")
    classify_region.add_argument("--confidence-threshold", type=float, help="maximum OCR confidence to classify")
    classify_region.add_argument("--max-chars", type=int, help="maximum OCR fragment chars sent to local model")
    classify_region.add_argument("--json", action="store_true", help="emit machine-readable classification")
    classify_region.set_defaults(func=run_ocr_classify_region)
    displays = subparsers.add_parser(
        "displays",
        help="list and select local displays for capture",
        description="List and select macOS displays for explicit local capture workflows.",
    )
    displays_subparsers = displays.add_subparsers(dest="displays_command")
    displays_list = displays_subparsers.add_parser("list", help="list currently connected displays")
    displays_list.add_argument("--json", action="store_true", help="emit machine-readable display inventory")
    displays_list.set_defaults(func=run_displays_list)
    displays_capture = displays_subparsers.add_parser(
        "capture",
        help="build or run a screencapture command for selected displays",
        description="Build or run screencapture commands for one or more selected display indexes.",
    )
    displays_capture.add_argument("--display", action="append", type=int, help="display index to capture")
    displays_capture.add_argument("--output-dir", type=Path, required=True, help="directory for capture files")
    displays_capture.add_argument("--video-seconds", type=int, help="record video for this many seconds")
    displays_capture.add_argument("--timestamp", default="", help="stable suffix for output filenames")
    displays_capture.add_argument("--ignore-missing", action="store_true", help="skip displays no longer connected")
    displays_capture.add_argument("--dry-run", action="store_true", help="print commands without capture")
    displays_capture.add_argument("--json", action="store_true", help="emit machine-readable capture plan")
    displays_capture.set_defaults(func=run_displays_capture)
    redact = subparsers.add_parser(
        "redact",
        help="redact an existing local video file",
        description="Extract frames from an existing local video, apply the local redaction transform, and write MP4.",
    )
    redact.add_argument("input_video", type=Path, help="input .mov, .mp4, or .m4v file")
    redact.add_argument("--output", type=Path, required=True, help="explicit .mp4 output path")
    redact.add_argument("--box", default="0,0,120,80", help="manual redaction box as left,top,right,bottom")
    redact.add_argument("--detections-json", type=Path, help="frame text/box detection manifest")
    redact.add_argument("--gitleaks", type=Path, help="local Gitleaks TOML pack for detections manifest text")
    redact.add_argument("--fps", type=int, default=30, help="output frame rate from 1 to 240")
    redact.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg executable path")
    redact.add_argument("--overwrite", action="store_true", help="replace an existing output file")
    redact.add_argument("--create-parent", action="store_true", help="create the output parent directory")
    redact.add_argument("--dry-run", action="store_true", help="validate paths and print plan without writing MP4")
    redact.add_argument("--json", action="store_true", help="emit machine-readable redaction output")
    redact.set_defaults(func=run_redact_video)
    sidecar = subparsers.add_parser(
        "sidecar",
        help="run menu-bar sidecar protocol helpers",
        description="Run JSON-RPC helpers used by the future macOS menu-bar shell.",
    )
    sidecar_subparsers = sidecar.add_subparsers(dest="sidecar_command")
    sidecar_stdio = sidecar_subparsers.add_parser(
        "stdio",
        help="serve the v1 sidecar JSON-RPC protocol over newline-delimited stdio",
        description="Read JSON-RPC requests from stdin and write JSON-RPC responses plus stats notifications.",
    )
    sidecar_stdio.set_defaults(func=run_sidecar_stdio)
    mp4 = subparsers.add_parser(
        "mp4",
        help="write redacted frame sequences to local MP4 files",
        description="Write already-redacted frame PNGs to an explicit local MP4 file.",
    )
    mp4_subparsers = mp4.add_subparsers(dest="mp4_command")
    mp4_from_frames = mp4_subparsers.add_parser(
        "from-redacted-frames",
        help="encode a directory of redacted PNG frames to MP4",
        description="Encode already-redacted PNG frames to MP4 with ffmpeg; this does not capture the screen.",
    )
    mp4_from_frames.add_argument("--frames-dir", type=Path, required=True, help="directory of redacted frame PNGs")
    mp4_from_frames.add_argument("--output", type=Path, required=True, help="explicit .mp4 output path")
    mp4_from_frames.add_argument("--pattern", default="*.png", help="frame filename glob inside --frames-dir")
    mp4_from_frames.add_argument("--fps", type=int, default=30, help="output frame rate from 1 to 240")
    mp4_from_frames.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg executable path")
    mp4_from_frames.add_argument("--overwrite", action="store_true", help="replace an existing output file")
    mp4_from_frames.add_argument("--create-parent", action="store_true", help="create the output parent directory")
    mp4_from_frames.add_argument("--dry-run", action="store_true", help="print encoder plan without writing MP4")
    mp4_from_frames.add_argument("--json", action="store_true", help="emit machine-readable encoder plan")
    mp4_from_frames.set_defaults(func=run_mp4_from_redacted_frames)
    buffer = subparsers.add_parser(
        "buffer",
        help="prototype local recording frame buffers",
        description="Prototype a recording-only frame ring buffer for retroactive redaction.",
    )
    buffer_subparsers = buffer.add_subparsers(dest="buffer_command")
    buffer_prototype = buffer_subparsers.add_parser(
        "prototype",
        help="retain recent frames and apply a retroactive box redaction",
        description="Retain a local recording frame window and apply a retroactive transform before final output.",
    )
    buffer_prototype.add_argument("--frames-dir", type=Path, required=True, help="directory of captured frame PNGs")
    buffer_prototype.add_argument("--output-dir", type=Path, required=True, help="directory for prototype output")
    buffer_prototype.add_argument("--pattern", default="*.png", help="frame filename glob inside --frames-dir")
    buffer_prototype.add_argument("--fps", type=int, default=30, help="recording frame rate from 1 to 240")
    buffer_prototype.add_argument("--seconds", type=float, default=30.0, help="ring-buffer retention window")
    buffer_prototype.add_argument(
        "--redact-last-seconds",
        type=float,
        default=5.0,
        help="trailing retained seconds to transform before finalizing",
    )
    buffer_prototype.add_argument("--box", default="0,0,120,80", help="redaction box as left,top,right,bottom")
    buffer_prototype.add_argument(
        "--write-buffer-copy",
        action="store_true",
        help="also persist the raw retained buffer",
    )
    buffer_prototype.add_argument("--overwrite", action="store_true", help="replace prior managed prototype output")
    buffer_prototype.add_argument("--create-parent", action="store_true", help="create the output parent directory")
    buffer_prototype.add_argument("--dry-run", action="store_true", help="measure and plan without writing output")
    buffer_prototype.add_argument("--json", action="store_true", help="emit machine-readable prototype metrics")
    buffer_prototype.set_defaults(func=run_buffer_prototype)
    obs = subparsers.add_parser(
        "obs",
        help="prototype OBS integration boundaries",
        description="Prototype OBS source-plugin frame handoff boundaries without shipping a native plugin.",
    )
    obs_subparsers = obs.add_subparsers(dest="obs_command")
    obs_source_prototype = obs_subparsers.add_parser(
        "prototype-source",
        help="apply an existing transform to frames as an OBS source stand-in",
        description="Process frame PNGs with the same transform a future OBS source plugin would call.",
    )
    obs_source_prototype.add_argument("--frames-dir", type=Path, required=True, help="directory of source frame PNGs")
    obs_source_prototype.add_argument("--output-dir", type=Path, required=True, help="directory for processed frames")
    obs_source_prototype.add_argument("--pattern", default="*.png", help="frame filename glob inside --frames-dir")
    obs_source_prototype.add_argument("--box", default="0,0,120,80", help="redaction box as left,top,right,bottom")
    obs_source_prototype.add_argument("--overwrite", action="store_true", help="replace prior managed prototype output")
    obs_source_prototype.add_argument("--create-parent", action="store_true", help="create the output parent directory")
    obs_source_prototype.add_argument("--dry-run", action="store_true", help="plan without writing processed frames")
    obs_source_prototype.add_argument("--json", action="store_true", help="emit machine-readable prototype output")
    obs_source_prototype.set_defaults(func=run_obs_prototype_source)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.tui:
        return run_tui(args)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
