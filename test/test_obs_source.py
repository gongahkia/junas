from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from junas.cli import main
from junas.desktop.time_buffer import parse_redaction_box
from junas.integrations.obs_source import build_obs_source_prototype_plan, run_obs_source_prototype

ROOT = Path(__file__).resolve().parent.parent


def _write_frame(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (12, 12), color).save(path)


class ObsSourcePrototypeTests(unittest.TestCase):
    def test_obs_source_prototype_applies_existing_redaction_transform(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = root / "frames"
            output = root / "obs"
            frames.mkdir()
            _write_frame(frames / "frame-000001.png", (255, 0, 0))
            _write_frame(frames / "frame-000002.png", (0, 255, 0))

            plan = build_obs_source_prototype_plan(
                frames_dir=frames,
                output_dir=output,
                redaction_box=parse_redaction_box("0,0,6,6"),
            )
            payload = run_obs_source_prototype(plan)

            self.assertEqual(payload["frame_count"], 2)
            self.assertEqual(payload["transform"], "time_buffer.redaction_box")
            self.assertFalse(payload["native_plugin_shipped"])
            self.assertTrue(payload["virtual_camera_unchanged"])
            processed = sorted((output / "processed_frames").glob("*.png"))
            self.assertEqual(len(processed), 2)
            with Image.open(processed[0]) as image:
                self.assertEqual(image.convert("RGBA").getpixel((1, 1)), (0, 0, 0, 255))

    def test_obs_cli_dry_run_does_not_write_processed_frames(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = root / "frames"
            output = root / "obs"
            frames.mkdir()
            _write_frame(frames / "frame-000001.png", (255, 255, 255))

            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "obs",
                        "prototype-source",
                        "--frames-dir",
                        str(frames),
                        "--output-dir",
                        str(output),
                        "--dry-run",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["frame_count"], 1)
            self.assertEqual(payload["transform"], "time_buffer.redaction_box")
            self.assertFalse((output / "processed_frames").exists())

    def test_obs_source_docs_cover_design_distribution_and_boundaries(self):
        doc = (ROOT / "docs" / "integrations" / "obs-source-plugin.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        integrations_index = (ROOT / "docs" / "integrations" / "README.md").read_text(encoding="utf-8")

        for token in (
            "OBS Source Plugin Design",
            "obs_source_info",
            "Frame Handoff",
            "time_buffer.redaction_box",
            "virtual-camera path remains intact",
            "Packaging And Distribution",
            "native_plugin_shipped=false",
            "https://docs.obsproject.com",
            "https://github.com/obsproject/obs-plugintemplate",
        ):
            self.assertIn(token, doc)
        self.assertIn("docs/integrations/obs-source-plugin.md", readme)
        self.assertIn("obs-source-plugin.md", integrations_index)


if __name__ == "__main__":
    unittest.main()
