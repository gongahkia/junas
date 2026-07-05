from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from junas.cli import main
from junas.desktop.time_buffer import (
    TimeBufferError,
    build_time_buffer_plan,
    parse_redaction_box,
    write_time_buffer_output,
)

ROOT = Path(__file__).resolve().parent.parent


def _write_frame(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (10, 10), color).save(path)


class TimeBufferTests(unittest.TestCase):
    def test_time_buffer_retains_recent_frames_and_redacts_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = root / "frames"
            output = root / "out"
            frames.mkdir()
            for index in range(5):
                _write_frame(frames / f"frame-{index + 1:06d}.png", (index * 40, 20, 30))

            plan = build_time_buffer_plan(
                frames_dir=frames,
                output_dir=output,
                fps=1,
                seconds=3,
                redact_last_seconds=2,
                redaction_box=parse_redaction_box("0,0,5,5"),
            )
            payload = write_time_buffer_output(plan)

            self.assertEqual(plan.source_frame_count, 5)
            self.assertEqual(len(plan.retained_frames), 3)
            self.assertEqual(plan.evicted_frame_count, 2)
            self.assertEqual(plan.redaction_frame_count, 2)
            self.assertEqual(plan.memory_bytes_estimate, 1200)
            self.assertGreater(plan.disk_bytes_estimate, 0)
            self.assertFalse(payload["live_stream_undo_supported"])
            self.assertGreater(payload["final_disk_bytes"], 0)
            final_frames = sorted((output / "final_frames").glob("*.png"))
            self.assertEqual(len(final_frames), 3)
            with (
                Image.open(final_frames[0]) as first,
                Image.open(final_frames[1]) as second,
                Image.open(final_frames[2]) as third,
            ):
                self.assertNotEqual(first.convert("RGBA").getpixel((1, 1)), (0, 0, 0, 255))
                self.assertEqual(second.convert("RGBA").getpixel((1, 1)), (0, 0, 0, 255))
                self.assertEqual(third.convert("RGBA").getpixel((1, 1)), (0, 0, 0, 255))

    def test_time_buffer_rejects_invalid_window_and_unmanaged_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = root / "frames"
            output = root / "out"
            frames.mkdir()
            output.mkdir()
            (output / "notes.txt").write_text("operator note", encoding="utf-8")
            _write_frame(frames / "frame-000001.png", (255, 0, 0))

            with self.assertRaisesRegex(TimeBufferError, "redact_last_seconds"):
                build_time_buffer_plan(
                    frames_dir=frames,
                    output_dir=output,
                    fps=1,
                    seconds=2,
                    redact_last_seconds=3,
                    redaction_box=parse_redaction_box("0,0,5,5"),
                )

            plan = build_time_buffer_plan(
                frames_dir=frames,
                output_dir=output,
                fps=1,
                seconds=1,
                redact_last_seconds=1,
                redaction_box=parse_redaction_box("0,0,5,5"),
            )
            with self.assertRaisesRegex(TimeBufferError, "unmanaged"):
                write_time_buffer_output(plan)

    def test_buffer_cli_dry_run_reports_metrics_without_writing(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = root / "frames"
            output = root / "out"
            frames.mkdir()
            for index in range(4):
                _write_frame(frames / f"frame-{index + 1:06d}.png", (index * 20, 40, 60))

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "buffer",
                        "prototype",
                        "--frames-dir",
                        str(frames),
                        "--output-dir",
                        str(output),
                        "--fps",
                        "2",
                        "--seconds",
                        "1",
                        "--redact-last-seconds",
                        "0.5",
                        "--dry-run",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["capacity_frames"], 2)
            self.assertEqual(payload["retained_frame_count"], 2)
            self.assertEqual(payload["evicted_frame_count"], 2)
            self.assertEqual(payload["redaction_frame_count"], 1)
            self.assertFalse(payload["live_stream_undo_supported"])
            self.assertFalse(output.exists())

    def test_time_buffer_docs_define_recording_boundary_and_metrics(self):
        doc = (ROOT / "docs" / "integrations" / "time-machine-buffer.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "integrations" / "README.md").read_text(encoding="utf-8")

        for token in (
            "recording-only",
            "live_stream_undo_supported=false",
            "Memory And Disk Implications",
            "Retroactive Transform",
            "does not unsend pixels from live streams",
            "junas mp4 from-redacted-frames",
        ):
            self.assertIn(token, doc)
        self.assertIn("docs/integrations/time-machine-buffer.md", readme)
        self.assertIn("time-machine-buffer.md", docs_index)


if __name__ == "__main__":
    unittest.main()
