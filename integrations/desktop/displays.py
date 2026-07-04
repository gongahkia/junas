from __future__ import annotations

import json
import platform
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


class DisplaySelectionError(ValueError):
    pass


@dataclass(frozen=True)
class DisplaySource:
    capture_index: int
    name: str
    display_id: str
    pixels: tuple[int, int] | None
    resolution: str
    is_main: bool
    is_online: bool
    connection_type: str


@dataclass(frozen=True)
class DisplayCaptureCommand:
    display: DisplaySource
    output_path: Path
    argv: tuple[str, ...]


def list_displays() -> tuple[DisplaySource, ...]:
    if platform.system() != "Darwin":
        return ()
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    if result.returncode != 0:
        return ()
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ()
    return parse_system_profiler_displays(payload)


def parse_system_profiler_displays(payload: dict[str, Any]) -> tuple[DisplaySource, ...]:
    raw_displays: list[dict[str, Any]] = []
    for gpu in payload.get("SPDisplaysDataType", []) or []:
        if not isinstance(gpu, dict):
            continue
        for display in gpu.get("spdisplays_ndrvs", []) or []:
            if isinstance(display, dict):
                raw_displays.append(display)
    raw_displays.sort(key=lambda item: (item.get("spdisplays_main") != "spdisplays_yes", str(item.get("_name", ""))))
    displays: list[DisplaySource] = []
    for index, item in enumerate(raw_displays, start=1):
        displays.append(
            DisplaySource(
                capture_index=index,
                name=str(item.get("_name") or f"Display {index}"),
                display_id=str(item.get("_spdisplays_displayID") or index),
                pixels=_parse_pixels(str(item.get("_spdisplays_pixels") or "")),
                resolution=str(item.get("_spdisplays_resolution") or ""),
                is_main=item.get("spdisplays_main") == "spdisplays_yes",
                is_online=item.get("spdisplays_online") != "spdisplays_no",
                connection_type=str(item.get("spdisplays_connection_type") or ""),
            )
        )
    return tuple(displays)


def select_displays(
    displays: Iterable[DisplaySource],
    selected_indexes: Iterable[int],
    *,
    ignore_missing: bool = False,
) -> tuple[DisplaySource, ...]:
    display_map = {display.capture_index: display for display in displays if display.is_online}
    requested = tuple(selected_indexes)
    if not requested:
        return tuple(display_map[index] for index in sorted(display_map))
    missing = [index for index in requested if index not in display_map]
    if missing and not ignore_missing:
        missing_text = ", ".join(str(index) for index in missing)
        raise DisplaySelectionError(f"display index not available: {missing_text}")
    return tuple(display_map[index] for index in requested if index in display_map)


def build_capture_plan(
    displays: Iterable[DisplaySource],
    *,
    selected_indexes: Iterable[int] = (),
    output_dir: Path,
    video_seconds: int | None = None,
    ignore_missing: bool = False,
    timestamp: str = "",
) -> tuple[DisplayCaptureCommand, ...]:
    selected = select_displays(displays, selected_indexes, ignore_missing=ignore_missing)
    if not selected:
        raise DisplaySelectionError("no online displays selected")
    suffix = "mov" if video_seconds else "png"
    commands: list[DisplayCaptureCommand] = []
    for display in selected:
        stem = f"display-{display.capture_index}"
        if timestamp:
            stem += f"-{timestamp}"
        output_path = output_dir / f"{stem}.{suffix}"
        argv = ["screencapture", "-x"]
        if video_seconds:
            argv.extend(["-v", "-V", str(video_seconds)])
        argv.extend(["-D", str(display.capture_index), str(output_path)])
        commands.append(DisplayCaptureCommand(display=display, output_path=output_path, argv=tuple(argv)))
    return tuple(commands)


def raw_frame_bandwidth_mbps(width: int, height: int, *, fps: int = 30, bytes_per_pixel: int = 4) -> float:
    return round(width * height * bytes_per_pixel * fps / 1_000_000, 1)


def _parse_pixels(value: str) -> tuple[int, int] | None:
    match = re.search(r"(\d+)\s*x\s*(\d+)", value)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))
