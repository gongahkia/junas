from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


class Mp4SinkError(ValueError):
    pass


@dataclass(frozen=True)
class Mp4SinkPlan:
    frames_dir: Path
    frame_pattern: str
    frames: tuple[Path, ...]
    output_path: Path
    fps: int
    overwrite: bool
    create_parent: bool
    ffmpeg_path: str
    argv_template: tuple[str, ...]
    duration_seconds: float


def build_mp4_sink_plan(
    *,
    frames_dir: Path,
    output_path: Path,
    frame_pattern: str = "*.png",
    fps: int = 30,
    overwrite: bool = False,
    create_parent: bool = False,
    ffmpeg_path: str = "ffmpeg",
    require_ffmpeg: bool = False,
) -> Mp4SinkPlan:
    resolved_fps = _validate_fps(fps)
    resolved_frames_dir = _resolve_frames_dir(frames_dir)
    frames = discover_frame_paths(resolved_frames_dir, frame_pattern)
    resolved_output = validate_output_path(output_path, overwrite=overwrite, create_parent=create_parent)
    ffmpeg = resolve_ffmpeg_binary(ffmpeg_path, require=require_ffmpeg)
    duration_seconds = round(len(frames) / resolved_fps, 6)
    argv_template = build_ffmpeg_argv(
        ffmpeg_path=ffmpeg,
        concat_path=Path("<ffconcat>"),
        output_path=resolved_output,
        fps=resolved_fps,
        frame_count=len(frames),
        overwrite=overwrite,
    )
    return Mp4SinkPlan(
        frames_dir=resolved_frames_dir,
        frame_pattern=frame_pattern,
        frames=frames,
        output_path=resolved_output,
        fps=resolved_fps,
        overwrite=overwrite,
        create_parent=create_parent,
        ffmpeg_path=ffmpeg,
        argv_template=argv_template,
        duration_seconds=duration_seconds,
    )


def discover_frame_paths(frames_dir: Path, frame_pattern: str = "*.png") -> tuple[Path, ...]:
    if not frame_pattern or "/" in frame_pattern or "\\" in frame_pattern or ".." in frame_pattern:
        raise Mp4SinkError("frame pattern must stay inside frame directory")
    frames = tuple(sorted(path.resolve() for path in frames_dir.glob(frame_pattern) if path.is_file()))
    if not frames:
        raise Mp4SinkError(f"no frames matched {frame_pattern!r} in {frames_dir}")
    return frames


def validate_output_path(output_path: Path, *, overwrite: bool = False, create_parent: bool = False) -> Path:
    expanded = output_path.expanduser()
    if expanded.is_symlink():
        raise Mp4SinkError("output path must not be a symlink")
    resolved = expanded.resolve(strict=False)
    if resolved.suffix.lower() != ".mp4":
        raise Mp4SinkError("output path must end in .mp4")
    if resolved.exists() and resolved.is_dir():
        raise Mp4SinkError("output path is a directory")
    if resolved.exists() and not overwrite:
        raise Mp4SinkError("output path already exists; pass --overwrite to replace it")
    parent = resolved.parent
    if parent.exists() and not parent.is_dir():
        raise Mp4SinkError("output parent is not a directory")
    if not parent.exists() and not create_parent:
        raise Mp4SinkError("output parent does not exist; pass --create-parent to create it")
    return resolved


def resolve_ffmpeg_binary(ffmpeg_path: str = "ffmpeg", *, require: bool = True) -> str:
    resolved = shutil.which(ffmpeg_path)
    if resolved:
        return resolved
    if require:
        raise Mp4SinkError("ffmpeg not found; install it or pass --ffmpeg")
    return ffmpeg_path


def render_ffconcat_manifest(frames: tuple[Path, ...], *, fps: int) -> str:
    if not frames:
        raise Mp4SinkError("no frames to encode")
    frame_duration = 1 / _validate_fps(fps)
    lines = ["ffconcat version 1.0"]
    for frame in frames:
        lines.append(f"file {_quote_ffconcat_path(frame)}")
        lines.append(f"duration {frame_duration:.9f}")
    lines.append(f"file {_quote_ffconcat_path(frames[-1])}")  # ffmpeg needs the last file repeated for duration
    return "\n".join(lines) + "\n"


def build_ffmpeg_argv(
    *,
    ffmpeg_path: str,
    concat_path: Path,
    output_path: Path,
    fps: int,
    frame_count: int,
    overwrite: bool,
) -> tuple[str, ...]:
    if frame_count < 1:
        raise Mp4SinkError("frame_count must be >= 1")
    return (
        ffmpeg_path,
        "-y" if overwrite else "-n",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-vf",
        f"fps={_validate_fps(fps)},scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
        "-c:v",
        "libx264",
        "-movflags",
        "+faststart",
        "-frames:v",
        str(frame_count),
        str(output_path),
    )


def encode_mp4(plan: Mp4SinkPlan) -> None:
    if plan.create_parent:
        plan.output_path.parent.mkdir(parents=True, exist_ok=True)
    validate_output_path(plan.output_path, overwrite=plan.overwrite, create_parent=plan.create_parent)
    ffmpeg = resolve_ffmpeg_binary(plan.ffmpeg_path, require=True)
    concat_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            prefix=".junas-mp4-",
            suffix=".ffconcat",
            dir=plan.output_path.parent,
            delete=False,
        ) as manifest:
            manifest.write(render_ffconcat_manifest(plan.frames, fps=plan.fps))
            concat_path = Path(manifest.name)
        argv = build_ffmpeg_argv(
            ffmpeg_path=ffmpeg,
            concat_path=concat_path,
            output_path=plan.output_path,
            fps=plan.fps,
            frame_count=len(plan.frames),
            overwrite=plan.overwrite,
        )
        try:
            completed = subprocess.run(argv, capture_output=True, text=True, check=False)
        except OSError as exc:
            raise Mp4SinkError(str(exc)) from exc
    finally:
        if concat_path is not None:
            concat_path.unlink(missing_ok=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "ffmpeg failed").strip()
        raise Mp4SinkError(detail)


def _resolve_frames_dir(frames_dir: Path) -> Path:
    resolved = frames_dir.expanduser().resolve(strict=False)
    if not resolved.is_dir():
        raise Mp4SinkError("frames directory does not exist")
    return resolved


def _validate_fps(fps: int) -> int:
    if fps < 1 or fps > 240:
        raise Mp4SinkError("fps must be between 1 and 240")
    return fps


def _quote_ffconcat_path(path: Path) -> str:
    return "'" + str(path).replace("'", r"'\''") + "'"
