from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from junas.desktop.mp4_sink import discover_frame_paths


class TimeBufferError(ValueError):
    pass


@dataclass(frozen=True)
class RedactionBox:
    left: int
    top: int
    right: int
    bottom: int

    def to_tuple(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.right, self.bottom)


@dataclass(frozen=True)
class TimeBufferPlan:
    frames_dir: Path
    output_dir: Path
    final_frames_dir: Path
    buffer_frames_dir: Path
    manifest_path: Path
    frame_pattern: str
    fps: int
    seconds: float
    redact_last_seconds: float
    capacity_frames: int
    source_frame_count: int
    retained_frames: tuple[Path, ...]
    evicted_frame_count: int
    redaction_frame_count: int
    redaction_start_index: int
    redaction_box: RedactionBox
    memory_bytes_estimate: int
    disk_bytes_estimate: int
    write_buffer_copy: bool
    overwrite: bool
    create_parent: bool
    live_stream_undo_supported: bool = False


def parse_redaction_box(value: str) -> RedactionBox:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise TimeBufferError("box must be left,top,right,bottom")
    try:
        left, top, right, bottom = (int(part) for part in parts)
    except ValueError as exc:
        raise TimeBufferError("box coordinates must be integers") from exc
    if left < 0 or top < 0 or right <= left or bottom <= top:
        raise TimeBufferError("box must have non-negative coordinates and positive area")
    return RedactionBox(left=left, top=top, right=right, bottom=bottom)


def build_time_buffer_plan(
    *,
    frames_dir: Path,
    output_dir: Path,
    frame_pattern: str = "*.png",
    fps: int = 30,
    seconds: float = 30.0,
    redact_last_seconds: float = 5.0,
    redaction_box: RedactionBox,
    overwrite: bool = False,
    create_parent: bool = False,
    write_buffer_copy: bool = False,
) -> TimeBufferPlan:
    resolved_fps = _validate_fps(fps)
    resolved_seconds = _validate_seconds(seconds, "seconds")
    resolved_redact_seconds = _validate_seconds(redact_last_seconds, "redact_last_seconds", allow_zero=True)
    if resolved_redact_seconds > resolved_seconds:
        raise TimeBufferError("redact_last_seconds must be <= seconds")
    resolved_frames_dir = frames_dir.expanduser().resolve(strict=False)
    if not resolved_frames_dir.is_dir():
        raise TimeBufferError("frames directory does not exist")
    source_frames = discover_frame_paths(resolved_frames_dir, frame_pattern)
    capacity_frames = max(1, round(resolved_fps * resolved_seconds))
    retained_frames = source_frames[-capacity_frames:]
    redaction_frame_count = min(len(retained_frames), round(resolved_fps * resolved_redact_seconds))
    redaction_start_index = len(retained_frames) - redaction_frame_count
    memory_bytes, disk_bytes = _measure_frame_costs(retained_frames)
    resolved_output = output_dir.expanduser().resolve(strict=False)
    return TimeBufferPlan(
        frames_dir=resolved_frames_dir,
        output_dir=resolved_output,
        final_frames_dir=resolved_output / "final_frames",
        buffer_frames_dir=resolved_output / "buffer_frames",
        manifest_path=resolved_output / "buffer_manifest.json",
        frame_pattern=frame_pattern,
        fps=resolved_fps,
        seconds=resolved_seconds,
        redact_last_seconds=resolved_redact_seconds,
        capacity_frames=capacity_frames,
        source_frame_count=len(source_frames),
        retained_frames=retained_frames,
        evicted_frame_count=max(0, len(source_frames) - len(retained_frames)),
        redaction_frame_count=redaction_frame_count,
        redaction_start_index=redaction_start_index,
        redaction_box=redaction_box,
        memory_bytes_estimate=memory_bytes,
        disk_bytes_estimate=disk_bytes,
        write_buffer_copy=write_buffer_copy,
        overwrite=overwrite,
        create_parent=create_parent,
    )


def write_time_buffer_output(plan: TimeBufferPlan) -> dict[str, Any]:
    _prepare_output_dir(plan)
    plan.final_frames_dir.mkdir(parents=True, exist_ok=True)
    if plan.write_buffer_copy:
        plan.buffer_frames_dir.mkdir(parents=True, exist_ok=True)
    final_bytes = 0
    for index, frame in enumerate(plan.retained_frames):
        output_name = f"frame-{index + 1:06d}.png"
        final_path = plan.final_frames_dir / output_name
        with Image.open(frame) as image:
            output = image.convert("RGBA")
            if index >= plan.redaction_start_index:
                output = apply_redaction_box(output, plan.redaction_box)
            output.save(final_path)
        final_bytes += final_path.stat().st_size
        if plan.write_buffer_copy:
            shutil.copy2(frame, plan.buffer_frames_dir / output_name)
    payload = plan_to_payload(plan, dry_run=False)
    payload["final_disk_bytes"] = final_bytes
    plan.manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def apply_redaction_box(image: Image.Image, box: RedactionBox) -> Image.Image:
    output = image.convert("RGBA")
    _draw_redaction(output, box)
    return output


def plan_to_payload(plan: TimeBufferPlan, *, dry_run: bool) -> dict[str, Any]:
    return {
        "frames_dir": str(plan.frames_dir),
        "output_dir": str(plan.output_dir),
        "final_frames_dir": str(plan.final_frames_dir),
        "buffer_frames_dir": str(plan.buffer_frames_dir) if plan.write_buffer_copy else "",
        "manifest_path": str(plan.manifest_path),
        "frame_pattern": plan.frame_pattern,
        "fps": plan.fps,
        "seconds": plan.seconds,
        "redact_last_seconds": plan.redact_last_seconds,
        "capacity_frames": plan.capacity_frames,
        "source_frame_count": plan.source_frame_count,
        "retained_frame_count": len(plan.retained_frames),
        "evicted_frame_count": plan.evicted_frame_count,
        "redaction_frame_count": plan.redaction_frame_count,
        "redaction_start_index": plan.redaction_start_index,
        "redaction_box": {
            "left": plan.redaction_box.left,
            "top": plan.redaction_box.top,
            "right": plan.redaction_box.right,
            "bottom": plan.redaction_box.bottom,
        },
        "memory_bytes_estimate": plan.memory_bytes_estimate,
        "disk_bytes_estimate": plan.disk_bytes_estimate,
        "write_buffer_copy": plan.write_buffer_copy,
        "dry_run": dry_run,
        "live_stream_undo_supported": plan.live_stream_undo_supported,
    }


def _prepare_output_dir(plan: TimeBufferPlan) -> None:
    parent = plan.output_dir.parent
    if parent.exists() and not parent.is_dir():
        raise TimeBufferError("output parent is not a directory")
    if not parent.exists() and not plan.create_parent:
        raise TimeBufferError("output parent does not exist; pass --create-parent to create it")
    if plan.create_parent:
        parent.mkdir(parents=True, exist_ok=True)
    if plan.output_dir.exists() and not plan.output_dir.is_dir():
        raise TimeBufferError("output path is not a directory")
    managed = {plan.final_frames_dir.name, plan.buffer_frames_dir.name, plan.manifest_path.name}
    if plan.output_dir.exists():
        children = tuple(plan.output_dir.iterdir())
        unmanaged = [child.name for child in children if child.name not in managed]
        if unmanaged:
            raise TimeBufferError("output directory contains unmanaged files")
        if children and not plan.overwrite:
            raise TimeBufferError("output directory already contains a prior buffer run; pass --overwrite")
        if plan.overwrite:
            for child in children:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
    plan.output_dir.mkdir(parents=True, exist_ok=True)


def _measure_frame_costs(frames: tuple[Path, ...]) -> tuple[int, int]:
    memory_bytes = 0
    disk_bytes = 0
    for frame in frames:
        with Image.open(frame) as image:
            width, height = image.size
        memory_bytes += width * height * 4
        disk_bytes += frame.stat().st_size
    return memory_bytes, disk_bytes


def _draw_redaction(image: Image.Image, box: RedactionBox) -> None:
    left, top, right, bottom = _clamp_box(box, image.size)
    if right <= left or bottom <= top:
        return
    ImageDraw.Draw(image).rectangle((left, top, right, bottom), fill=(0, 0, 0, 255))


def _clamp_box(box: RedactionBox, size: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = size
    return (
        min(max(0, box.left), width),
        min(max(0, box.top), height),
        min(max(0, box.right), width),
        min(max(0, box.bottom), height),
    )


def _validate_fps(fps: int) -> int:
    if fps < 1 or fps > 240:
        raise TimeBufferError("fps must be between 1 and 240")
    return fps


def _validate_seconds(value: float, name: str, *, allow_zero: bool = False) -> float:
    if value < 0 or (value == 0 and not allow_zero) or value > 300:
        minimum = "0" if allow_zero else "> 0"
        raise TimeBufferError(f"{name} must be {minimum} and <= 300")
    return float(value)
