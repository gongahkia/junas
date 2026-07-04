from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from junas.desktop.mp4_sink import (
    Mp4SinkError,
    build_mp4_sink_plan,
    discover_frame_paths,
    encode_mp4,
    resolve_ffmpeg_binary,
    validate_output_path,
)
from junas.desktop.time_buffer import RedactionBox, apply_redaction_box
from junas.review.secret_rulepacks import SecretRulePackError, detect_secret_findings, load_gitleaks_rule_pack


class OfflineVideoRedactionError(ValueError):
    pass


@dataclass(frozen=True)
class ManifestDetections:
    boxes_by_frame: dict[int, tuple[RedactionBox, ...]]
    detected_rules: tuple[str, ...]


@dataclass(frozen=True)
class OfflineVideoRedactionPlan:
    input_path: Path
    output_path: Path
    fps: int
    redaction_box: RedactionBox
    detections_json: Path | None
    gitleaks_path: Path | None
    overwrite: bool
    create_parent: bool
    ffmpeg_path: str
    detection_mode: str
    transform: str = "time_buffer.redaction_box"
    audio_preserved: bool = False


def build_offline_video_redaction_plan(
    *,
    input_path: Path,
    output_path: Path,
    fps: int = 30,
    redaction_box: RedactionBox,
    detections_json: Path | None = None,
    gitleaks_path: Path | None = None,
    overwrite: bool = False,
    create_parent: bool = False,
    ffmpeg_path: str = "ffmpeg",
    require_ffmpeg: bool = False,
) -> OfflineVideoRedactionPlan:
    resolved_input = _validate_input_path(input_path)
    try:
        resolved_output = validate_output_path(output_path, overwrite=overwrite, create_parent=create_parent)
        ffmpeg = resolve_ffmpeg_binary(ffmpeg_path, require=require_ffmpeg)
    except Mp4SinkError as exc:
        raise OfflineVideoRedactionError(str(exc)) from exc
    if resolved_input == resolved_output:
        raise OfflineVideoRedactionError("output path must not overwrite the input video")
    resolved_fps = _validate_fps(fps)
    resolved_manifest = _validate_optional_file(detections_json, "detections JSON") if detections_json else None
    resolved_gitleaks = _validate_optional_file(gitleaks_path, "Gitleaks rule pack") if gitleaks_path else None
    if resolved_manifest and not resolved_gitleaks:
        raise OfflineVideoRedactionError("--gitleaks is required with --detections-json")
    if resolved_gitleaks and not resolved_manifest:
        raise OfflineVideoRedactionError("--detections-json is required with --gitleaks")
    return OfflineVideoRedactionPlan(
        input_path=resolved_input,
        output_path=resolved_output,
        fps=resolved_fps,
        redaction_box=redaction_box,
        detections_json=resolved_manifest,
        gitleaks_path=resolved_gitleaks,
        overwrite=overwrite,
        create_parent=create_parent,
        ffmpeg_path=ffmpeg,
        detection_mode="manifest_secret_rules" if resolved_manifest else "manual_box_all_frames",
    )


def redact_video(plan: OfflineVideoRedactionPlan) -> dict[str, Any]:
    detections = _load_manifest_detections(plan)
    with tempfile.TemporaryDirectory(prefix="junas-offline-video-") as tmp:
        root = Path(tmp)
        extracted_dir = root / "extracted"
        redacted_dir = root / "redacted"
        extracted_dir.mkdir()
        redacted_dir.mkdir()
        _extract_video_frames(plan, extracted_dir)
        try:
            extracted_frames = discover_frame_paths(extracted_dir)
            redacted_frame_count = _write_redacted_frames(
                extracted_frames,
                redacted_dir,
                redaction_box=plan.redaction_box,
                detections=detections,
                manual_all_frames=plan.detections_json is None,
            )
            sink_plan = build_mp4_sink_plan(
                frames_dir=redacted_dir,
                output_path=plan.output_path,
                fps=plan.fps,
                overwrite=plan.overwrite,
                create_parent=plan.create_parent,
                ffmpeg_path=plan.ffmpeg_path,
                require_ffmpeg=True,
            )
            encode_mp4(sink_plan)
        except Mp4SinkError as exc:
            raise OfflineVideoRedactionError(str(exc)) from exc
    payload = plan_to_payload(plan, dry_run=False)
    payload.update(
        {
            "frame_count": len(extracted_frames),
            "redacted_frame_count": redacted_frame_count,
            "detected_frame_count": len(detections.boxes_by_frame),
            "detected_rules": list(detections.detected_rules),
            "status": "written",
        }
    )
    return payload


def plan_to_payload(plan: OfflineVideoRedactionPlan, *, dry_run: bool) -> dict[str, Any]:
    return {
        "input_path": str(plan.input_path),
        "output_path": str(plan.output_path),
        "fps": plan.fps,
        "detection_mode": plan.detection_mode,
        "detections_json": str(plan.detections_json) if plan.detections_json else "",
        "gitleaks_path": str(plan.gitleaks_path) if plan.gitleaks_path else "",
        "transform": plan.transform,
        "overwrite": plan.overwrite,
        "create_parent": plan.create_parent,
        "ffmpeg_path": plan.ffmpeg_path,
        "audio_preserved": plan.audio_preserved,
        "dry_run": dry_run,
    }


def _load_manifest_detections(plan: OfflineVideoRedactionPlan) -> ManifestDetections:
    if not plan.detections_json:
        return ManifestDetections(boxes_by_frame={}, detected_rules=())
    assert plan.gitleaks_path is not None
    try:
        raw = json.loads(plan.detections_json.read_text(encoding="utf-8"))
        pack = load_gitleaks_rule_pack(plan.gitleaks_path)
    except (OSError, json.JSONDecodeError, SecretRulePackError) as exc:
        raise OfflineVideoRedactionError(str(exc)) from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("frames"), list):
        raise OfflineVideoRedactionError("detections JSON must contain a frames array")
    boxes_by_frame: dict[int, tuple[RedactionBox, ...]] = {}
    detected_rules: set[str] = set()
    for index, item in enumerate(raw["frames"]):
        if not isinstance(item, dict):
            raise OfflineVideoRedactionError(f"detections frame {index} must be an object")
        frame_number = _positive_int(item.get("frame"), f"detections frame {index} frame")
        text = item.get("text", "")
        if not isinstance(text, str):
            raise OfflineVideoRedactionError(f"detections frame {index} text must be a string")
        boxes = _parse_manifest_boxes(item.get("boxes"), index)
        findings = detect_secret_findings(
            text=text,
            rule_packs=(pack,),
            jurisdiction="US",
            idx_start=0,
            new_finding=_dict_finding,
            max_matches=64,
        )
        if not findings:
            continue
        boxes_by_frame[frame_number] = boxes
        detected_rules.update(str(finding["rule"]) for finding in findings)
    return ManifestDetections(boxes_by_frame=boxes_by_frame, detected_rules=tuple(sorted(detected_rules)))


def _extract_video_frames(plan: OfflineVideoRedactionPlan, output_dir: Path) -> None:
    argv = (
        plan.ffmpeg_path,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(plan.input_path),
        str(output_dir / "frame-%06d.png"),
    )
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise OfflineVideoRedactionError(str(exc)) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "ffmpeg failed").strip()
        raise OfflineVideoRedactionError(detail)


def _write_redacted_frames(
    frames: tuple[Path, ...],
    output_dir: Path,
    *,
    redaction_box: RedactionBox,
    detections: ManifestDetections,
    manual_all_frames: bool,
) -> int:
    redacted_count = 0
    for index, frame in enumerate(frames, start=1):
        boxes = detections.boxes_by_frame.get(index, (redaction_box,) if manual_all_frames else ())
        output_name = f"frame-{index:06d}.png"
        with Image.open(frame) as image:
            output = image.convert("RGBA")
            for box in boxes:
                output = apply_redaction_box(output, box)
            output.save(output_dir / output_name)
        if boxes:
            redacted_count += 1
    return redacted_count


def _parse_manifest_boxes(value: Any, frame_index: int) -> tuple[RedactionBox, ...]:
    if not isinstance(value, list) or not value:
        raise OfflineVideoRedactionError(f"detections frame {frame_index} boxes must be a non-empty array")
    return tuple(_parse_manifest_box(box, frame_index) for box in value)


def _parse_manifest_box(value: Any, frame_index: int) -> RedactionBox:
    if not isinstance(value, list) or len(value) != 4:
        raise OfflineVideoRedactionError(f"detections frame {frame_index} box must be [left, top, right, bottom]")
    if not all(isinstance(part, int) and not isinstance(part, bool) for part in value):
        raise OfflineVideoRedactionError(f"detections frame {frame_index} box coordinates must be integers")
    left, top, right, bottom = value
    if left < 0 or top < 0 or right <= left or bottom <= top:
        raise OfflineVideoRedactionError(f"detections frame {frame_index} box must have positive area")
    return RedactionBox(left=left, top=top, right=right, bottom=bottom)


def _validate_input_path(path: Path) -> Path:
    expanded = path.expanduser()
    resolved = expanded.resolve(strict=False)
    if not resolved.is_file():
        raise OfflineVideoRedactionError("input video does not exist")
    if resolved.suffix.lower() not in {".mov", ".mp4", ".m4v"}:
        raise OfflineVideoRedactionError("input video must end in .mov, .mp4, or .m4v")
    return resolved


def _validate_optional_file(path: Path | None, name: str) -> Path:
    assert path is not None
    resolved = path.expanduser().resolve(strict=False)
    if not resolved.is_file():
        raise OfflineVideoRedactionError(f"{name} does not exist")
    return resolved


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise OfflineVideoRedactionError(f"{name} must be a positive integer")
    return value


def _validate_fps(fps: int) -> int:
    if isinstance(fps, bool) or fps < 1 or fps > 240:
        raise OfflineVideoRedactionError("fps must be between 1 and 240")
    return fps


def _dict_finding(**kwargs):
    return kwargs
