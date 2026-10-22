"""Real optional local OCR regressions, separate from fake provider API tests."""

import base64
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

import junas.backend.main as main
from junas.review.image_scan import (
    ImageCandidate,
    ImageLocator,
    ImageScanError,
    TesseractImageScanner,
)

HAS_TESSERACT = importlib.util.find_spec("pytesseract") is not None and shutil.which("tesseract") is not None
FIXTURE = Path(__file__).parent / "fixtures/ocr/ambiguous-s-prefix.png"


@unittest.skipUnless(HAS_TESSERACT, "optional pytesseract and native Tesseract required")
class TesseractOcrTests(unittest.TestCase):
    def test_preserved_s_prefix_fixture_is_detected_and_its_pixels_are_redacted(self):
        import io

        import pytesseract

        main._state.clear()
        data = FIXTURE.read_bytes()
        payload = {
            "document_base64": base64.b64encode(data).decode(),
            "document_filename": "synthetic-identity.png",
            "document_mime_type": "image/png",
            "review_profile": "strict",
            "degraded_policy": "block_send",
        }
        with (
            mock.patch.dict(
                os.environ,
                {"JUNAS_IMAGE_SCAN_PROVIDER": "tesseract", "JUNAS_LLM_ENABLED": "0", "JUNAS_REVIEW_PERSIST": "0"},
            ),
            TestClient(main.app) as client,
        ):
            response = client.post("/review", json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            findings = response.json()["findings"]
            nric = next((finding for finding in findings if finding["rule"] == "sg_nric_fin"), None)
            self.assertIsNotNone(nric, "the preserved S-prefix input must be detected")
            self.assertEqual(nric["matched_text"], "S1234567D")
            self.assertEqual(nric["source"], "image_ocr")
            self.assertTrue(nric["image_ocr_regions"][0]["bounding_box"])
            self.assertFalse(response.json()["send_allowed"])
            redacted = client.post("/redact", json=payload)
            self.assertEqual(redacted.status_code, 200, redacted.text)
            output = redacted.json()
            image = Image.open(io.BytesIO(base64.b64decode(output["redacted_document"]["document_base64"])))
            independent = pytesseract.image_to_string(image, timeout=5)
            self.assertNotIn("1234567", independent)
            self.assertNotIn("synthetic@example.test", independent)
            self.assertNotIn("1234567", json.dumps(output))
            self.assertNotIn("1234567", json.dumps(image.info))

    @unittest.skipUnless(Path("/System/Library/Fonts/Supplemental/Arial.ttf").exists(), "macOS control font required")
    def test_actual_currency_and_digit_prefix_are_not_changed_into_identity_prefixes(self):
        import io

        scanner = TesseractImageScanner()
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 64)
        for value in ("$1234567D", "51234567D", "11234567D", "111234567D", "1T1234567D", "S1234567D", "T1234567D"):
            with self.subTest(value=value):
                image = Image.new("RGB", (1000, 160), "white")
                ImageDraw.Draw(image).text((30, 30), value, font=font, fill="black")
                stream = io.BytesIO()
                image.save(stream, format="PNG")
                result = scanner.scan(ImageCandidate(stream.getvalue(), "image/png", ImageLocator("control.png", 0)))
                self.assertEqual(result.text, value)
                self.assertEqual(result.regions[0].text, value)
                self.assertEqual(result.text[result.regions[0].start_char : result.regions[0].end_char], value)

    def test_configured_timeout_terminates_an_actual_stalled_ocr_subprocess(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "stalled-tesseract"
            pid_path = Path(directory) / "child.pid"
            script.write_text(
                '#!/bin/sh\nif [ "$1" = "--version" ]\nthen\n'
                " printf '%s\\n' 'tesseract 5.5.3'\nelse\n"
                f' printf "%s" "$$" > {shlex.quote(str(pid_path))}\n'
                " exec /bin/sleep 3\nfi\n"
            )
            script.chmod(0o700)
            # Other suite tests stub optional modules. Exercise the real SDK in a
            # fresh process so its command globals and imports cannot be stale.
            code = """
import json, sys, time
from pathlib import Path
from types import SimpleNamespace
import pytesseract
from junas.external.privacy_guard import PrivacyGuard
from junas.review.image_scan import ImageCandidate, ImageLocator, ImageScanError, build_image_scanner
pytesseract.pytesseract.tesseract_cmd = sys.argv[1]
scanner = build_image_scanner(SimpleNamespace(provider='tesseract', timeout_seconds=0.5), PrivacyGuard())
start = time.monotonic()
try:
    scanner.scan(ImageCandidate(Path(sys.argv[2]).read_bytes(), 'image/png', ImageLocator('timeout.png', 0)))
except ImageScanError as error:
    print(json.dumps({'elapsed':time.monotonic()-start, 'error':str(error)}))
else:
    raise AssertionError('stalled OCR unexpectedly succeeded')
"""
            result = subprocess.run(
                [sys.executable, "-c", code, str(script), str(FIXTURE)], capture_output=True, text=True, timeout=10
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            recorded = json.loads(result.stdout)
            self.assertIn("timeout", recorded["error"].lower())
            self.assertLess(recorded["elapsed"], 1.5)
            self.assertTrue(pid_path.exists(), "the owned subprocess must actually have started")
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pid_path.read_text()), 0)

    def test_identity_and_currency_glyphs_across_mac_fonts(self):
        import io

        fonts = [
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/System/Library/Fonts/Menlo.ttc"),
            Path("/System/Library/Fonts/Supplemental/Courier New.ttf"),
        ]
        if not all(path.exists() for path in fonts):
            self.skipTest("three macOS control fonts required")
        scanner = TesseractImageScanner()
        for path in fonts:
            font = ImageFont.truetype(str(path), 64)
            for value in ("S1234567D", "$1234567D", "T1234567D"):
                with self.subTest(font=path.name, value=value):
                    image = Image.new("RGB", (2200, 320), "white")
                    ImageDraw.Draw(image).text((70, 50), "NRIC " + value, font=font, fill="black")
                    stream = io.BytesIO()
                    image.save(stream, format="PNG")
                    result = scanner.scan(ImageCandidate(stream.getvalue(), "image/png", ImageLocator("font.png", 0)))
                    self.assertEqual(result.text, "NRIC " + value)


class TesseractBudgetTests(unittest.TestCase):
    def candidate(self):
        return ImageCandidate(FIXTURE.read_bytes(), "image/png", ImageLocator("budget.png", 0))

    def test_data_timeout_does_not_start_another_fallback_subprocess(self):
        fake = SimpleNamespace(
            Output=SimpleNamespace(DICT="dict"),
            image_to_data=mock.Mock(side_effect=RuntimeError("Tesseract process timeout")),
            image_to_string=mock.Mock(return_value="fallback"),
        )
        with mock.patch.dict("sys.modules", {"pytesseract": fake}):
            with self.assertRaises(ImageScanError):
                TesseractImageScanner(timeout_seconds=1).scan(self.candidate())
        fake.image_to_string.assert_not_called()

    def test_fallback_receives_only_the_remaining_budget(self):
        fake = SimpleNamespace(
            Output=SimpleNamespace(DICT="dict"),
            image_to_data=mock.Mock(side_effect=ValueError("synthetic TSV conversion failure")),
            image_to_string=mock.Mock(return_value="fallback"),
        )
        with (
            mock.patch.dict("sys.modules", {"pytesseract": fake}),
            mock.patch("junas.review.image_scan.time.monotonic", side_effect=[100, 100.25, 100.75]),
        ):
            result = TesseractImageScanner(timeout_seconds=1).scan(self.candidate())
        self.assertEqual(result.text, "fallback")
        self.assertEqual(fake.image_to_data.call_args.kwargs["timeout"], 0.75)
        self.assertEqual(fake.image_to_string.call_args.kwargs["timeout"], 0.25)

    def test_secondary_recognition_failure_cannot_return_partial_success(self):
        fake = SimpleNamespace(
            Output=SimpleNamespace(DICT="dict"),
            image_to_data=mock.Mock(return_value={"text": ["$1234567D"]}),
            image_to_boxes=mock.Mock(side_effect=RuntimeError("Tesseract process timeout")),
            image_to_string=mock.Mock(return_value="S"),
        )
        with mock.patch.dict("sys.modules", {"pytesseract": fake}):
            with self.assertRaises(ImageScanError):
                TesseractImageScanner(timeout_seconds=1).scan(self.candidate())
        fake.image_to_string.assert_not_called()


if __name__ == "__main__":
    unittest.main()
