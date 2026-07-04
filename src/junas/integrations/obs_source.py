from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from junas.desktop.mp4_sink import discover_frame_paths
from junas.desktop.time_buffer import RedactionBox, apply_redaction_box


class ObsSourcePrototypeError(ValueError):
    pass


@dataclass(frozen=True)
class ObsSourcePrototypePlan:
    frames_dir: Path
    output_dir: Path
    processed_frames_dir: Path
    manifest_path: Path
    frame_pattern: str
    frames: tuple[Path, ...]
    redaction_box: RedactionBox
    overwrite: bool
    create_parent: bool
    transform: str = "time_buffer.redaction_box"
    native_plugin_shipped: bool = False


def build_obs_source_prototype_plan(
    *,
    frames_dir: Path,
    output_dir: Path,
    frame_pattern: str = "*.png",
    redaction_box: RedactionBox,
    overwrite: bool = False,
    create_parent: bool = False,
) -> ObsSourcePrototypePlan:
    resolved_frames_dir = frames_dir.expanduser().resolve(strict=False)
    if not resolved_frames_dir.is_dir():
        raise ObsSourcePrototypeError("frames directory does not exist")
    frames = discover_frame_paths(resolved_frames_dir, frame_pattern)
    resolved_output = output_dir.expanduser().resolve(strict=False)
    return ObsSourcePrototypePlan(
        frames_dir=resolved_frames_dir,
        output_dir=resolved_output,
        processed_frames_dir=resolved_output / "processed_frames",
        manifest_path=resolved_output / "obs_source_manifest.json",
        frame_pattern=frame_pattern,
        frames=frames,
        redaction_box=redaction_box,
        overwrite=overwrite,
        create_parent=create_parent,
    )


def run_obs_source_prototype(plan: ObsSourcePrototypePlan) -> dict[str, Any]:
    _prepare_output_dir(plan)
    plan.processed_frames_dir.mkdir(parents=True, exist_ok=True)
    output_bytes = 0
    for index, frame in enumerate(plan.frames):
        target = plan.processed_frames_dir / f"frame-{index + 1:06d}.png"
        with Image.open(frame) as image:
            output = apply_redaction_box(image, plan.redaction_box)
            output.save(target)
        output_bytes += target.stat().st_size
    payload = plan_to_payload(plan, dry_run=False)
    payload["output_bytes"] = output_bytes
    plan.manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def plan_to_payload(plan: ObsSourcePrototypePlan, *, dry_run: bool) -> dict[str, Any]:
    return {
        "frames_dir": str(plan.frames_dir),
        "output_dir": str(plan.output_dir),
        "processed_frames_dir": str(plan.processed_frames_dir),
        "manifest_path": str(plan.manifest_path),
        "frame_pattern": plan.frame_pattern,
        "frame_count": len(plan.frames),
        "redaction_box": {
            "left": plan.redaction_box.left,
            "top": plan.redaction_box.top,
            "right": plan.redaction_box.right,
            "bottom": plan.redaction_box.bottom,
        },
        "transform": plan.transform,
        "dry_run": dry_run,
        "native_plugin_shipped": plan.native_plugin_shipped,
        "virtual_camera_unchanged": True,
    }


def _prepare_output_dir(plan: ObsSourcePrototypePlan) -> None:
    parent = plan.output_dir.parent
    if parent.exists() and not parent.is_dir():
        raise ObsSourcePrototypeError("output parent is not a directory")
    if not parent.exists() and not plan.create_parent:
        raise ObsSourcePrototypeError("output parent does not exist; pass --create-parent")
    if plan.create_parent:
        parent.mkdir(parents=True, exist_ok=True)
    if plan.output_dir.exists() and not plan.output_dir.is_dir():
        raise ObsSourcePrototypeError("output path is not a directory")
    managed = {plan.processed_frames_dir.name, plan.manifest_path.name}
    if plan.output_dir.exists():
        children = tuple(plan.output_dir.iterdir())
        unmanaged = [child.name for child in children if child.name not in managed]
        if unmanaged:
            raise ObsSourcePrototypeError("output directory contains unmanaged files")
        if children and not plan.overwrite:
            raise ObsSourcePrototypeError("output directory already contains prototype output; pass --overwrite")
        if plan.overwrite:
            for child in children:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
    plan.output_dir.mkdir(parents=True, exist_ok=True)
