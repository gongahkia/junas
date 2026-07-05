from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from junas.cli import main
from junas.desktop.offline_video import OfflineVideoRedactionError, build_offline_video_redaction_plan
from junas.desktop.time_buffer import parse_redaction_box

ROOT = Path(__file__).resolve().parent.parent
TOKEN = "a1b2c3d4e5f6g7h8i9j0"


class OfflineVideoRedactionTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_redact_video_cli_redacts_detected_secret_frame_without_leaking_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_frame = root / "source.png"
            input_video = root / "input.mov"
            output_video = root / "redacted.mp4"
            extracted_frame = root / "redacted-frame.png"
            detections = root / "detections.json"
            self._write_secret_frame(source_frame)
            self._run(
                [
                    shutil.which("ffmpeg") or "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-loop",
                    "1",
                    "-i",
                    str(source_frame),
                    "-t",
                    "1",
                    "-r",
                    "1",
                    "-pix_fmt",
                    "yuv420p",
                    str(input_video),
                ]
            )
            detections.write_text(
                json.dumps(
                    {
                        "frames": [
                            {
                                "frame": 1,
                                "text": f"ACME_API_KEY = {TOKEN}",
                                "boxes": [[0, 0, 155, 36]],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "redact",
                        str(input_video),
                        "--output",
                        str(output_video),
                        "--fps",
                        "1",
                        "--detections-json",
                        str(detections),
                        "--gitleaks",
                        str(ROOT / "rules" / "community" / "gitleaks-acme-demo.toml"),
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            payload_text = stdout.getvalue()
            payload = json.loads(payload_text)
            self.assertTrue(output_video.exists())
            self.assertNotIn(TOKEN, payload_text)
            self.assertEqual(payload["frame_count"], 1)
            self.assertEqual(payload["redacted_frame_count"], 1)
            self.assertEqual(payload["detected_frame_count"], 1)
            self.assertEqual(payload["detected_rules"], ["external_secret_acme-api-token"])
            self.assertEqual(payload["detection_mode"], "manifest_secret_rules")
            self.assertEqual(payload["transform"], "time_buffer.redaction_box")
            self.assertFalse(payload["audio_preserved"])
            self._run(
                [
                    shutil.which("ffmpeg") or "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(output_video),
                    "-frames:v",
                    "1",
                    str(extracted_frame),
                ]
            )
            with Image.open(extracted_frame) as image:
                pixel = image.convert("RGB").getpixel((4, 8))
            self.assertLess(max(pixel), 16)

    def test_redact_plan_rejects_original_overwrite_and_manifest_without_rule_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_video = root / "input.mp4"
            detections = root / "detections.json"
            input_video.write_bytes(b"not a real video")
            detections.write_text('{"frames":[]}', encoding="utf-8")

            with self.assertRaisesRegex(OfflineVideoRedactionError, "input video"):
                build_offline_video_redaction_plan(
                    input_path=input_video,
                    output_path=input_video,
                    redaction_box=parse_redaction_box("0,0,10,10"),
                    overwrite=True,
                )
            with self.assertRaisesRegex(OfflineVideoRedactionError, "--gitleaks"):
                build_offline_video_redaction_plan(
                    input_path=input_video,
                    output_path=root / "out.mp4",
                    redaction_box=parse_redaction_box("0,0,10,10"),
                    detections_json=detections,
                )

    def test_offline_video_docs_cover_command_detection_and_output_safety(self):
        doc = (ROOT / "docs" / "integrations" / "offline-video-redaction.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        integrations_index = (ROOT / "docs" / "integrations" / "README.md").read_text(encoding="utf-8")

        for token in (
            "junas redact",
            "--output",
            "--detections-json",
            "manifest_secret_rules",
            "time_buffer.redaction_box",
            "does not overwrite",
            "audio_preserved=false",
        ):
            self.assertIn(token, doc)
        self.assertIn("docs/integrations/offline-video-redaction.md", readme)
        self.assertIn("integrations/offline-video-redaction.md", docs_index)
        self.assertIn("offline-video-redaction.md", integrations_index)

    def _write_secret_frame(self, path: Path) -> None:
        image = Image.new("RGB", (180, 72), "white")
        draw = ImageDraw.Draw(image)
        draw.text((4, 8), f"ACME_API_KEY = {TOKEN}", fill="black")
        image.save(path)

    def _run(self, argv: list[str]) -> None:
        completed = subprocess.run(argv, capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)


if __name__ == "__main__":
    unittest.main()
