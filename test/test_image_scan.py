import base64
import os
import unittest
import zipfile
from contextlib import asynccontextmanager
from io import BytesIO
from unittest import mock

from fastapi.testclient import TestClient
from PIL import Image

import backend.main as main
from kaypoh.review.image_scan import ImageOcrResult, ImageScanError, collect_docx_images


@asynccontextmanager
async def _noop_lifespan(app):
    yield


main.app.router.lifespan_context = _noop_lifespan


def _png_bytes() -> bytes:
    image = Image.new("RGB", (80, 30), color=(255, 255, 255))
    with BytesIO() as buffer:
        image.save(buffer, format="PNG")
        return buffer.getvalue()


def _docx_with_embedded_png() -> bytes:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t></w:t></w:r></w:p></w:body></w:document>"
    )
    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", document_xml)
            archive.writestr("word/media/image1.png", _png_bytes())
        return buffer.getvalue()


class FakeImageScanner:
    provider = "fake_ocr"

    def __init__(self, *, text: str = "Dr Jane Tan S1234567D", fail: bool = False, ledger: list[dict] | None = None):
        self.text = text
        self.fail = fail
        self.ledger = ledger or []
        self.last_candidate = None

    def scan(self, candidate):
        self.last_candidate = candidate
        if self.fail:
            raise ImageScanError("fake OCR unavailable")
        return ImageOcrResult(
            text=self.text,
            locator=candidate.locator,
            provider=self.provider,
            privacy_ledger=list(self.ledger),
        )


class ImageScanTests(unittest.TestCase):
    def setUp(self):
        main.app.router.lifespan_context = _noop_lifespan
        main._state.clear()
        main.app.openapi_schema = None

    def test_docx_embedded_images_are_collected_for_ocr(self):
        candidates = collect_docx_images(_docx_with_embedded_png())

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.mime_type, "image/png")
        self.assertEqual(candidate.locator.container_path, "word/media/image1.png")

    def test_standalone_image_requires_provider(self):
        encoded = base64.b64encode(_png_bytes()).decode("ascii")
        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={
                    "document_base64": encoded,
                    "document_filename": "scan.png",
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("unsupported document_mime_type", response.json()["detail"])

    def test_image_ocr_findings_carry_source_and_locator(self):
        scanner = FakeImageScanner()
        main._state["models"] = {"image_scanner": scanner}
        encoded = base64.b64encode(_png_bytes()).decode("ascii")
        with mock.patch.dict(os.environ, {"KAYPOH_IMAGE_SCAN_PROVIDER": "tesseract"}, clear=False):
            with TestClient(main.app) as client:
                response = client.post(
                    "/review",
                    json={
                        "document_base64": encoded,
                        "document_filename": "scan.png",
                        "source_jurisdiction": "SG",
                        "destination_jurisdiction": "SG",
                    },
                )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        finding = next(item for item in payload["findings"] if item["rule"] == "sg_nric_fin")
        self.assertEqual(finding["source"], "image_ocr")
        self.assertEqual(finding["image_locator"]["container_path"], "scan.png")
        self.assertEqual(finding["image_locator"]["image_index"], 0)
        self.assertEqual(scanner.last_candidate.mime_type, "image/png")

    def test_image_ocr_failure_fails_closed(self):
        main._state["models"] = {"image_scanner": FakeImageScanner(fail=True)}
        encoded = base64.b64encode(_png_bytes()).decode("ascii")
        with mock.patch.dict(os.environ, {"KAYPOH_IMAGE_SCAN_PROVIDER": "tesseract"}, clear=False):
            with TestClient(main.app) as client:
                response = client.post(
                    "/review",
                    json={"document_base64": encoded, "document_filename": "scan.png"},
                )

        self.assertEqual(response.status_code, 422)
        self.assertIn("fake OCR unavailable", response.json()["detail"])

    def test_cloud_image_ocr_privacy_ledger_is_returned(self):
        ledger = [
            {
                "destination": "openai_vision",
                "operation": "image_ocr",
                "allowed": True,
                "reason": "external image OCR content transfer approved",
                "query": "",
                "redactions": [],
                "input_mode": "",
                "content_sha256": "a" * 64,
                "content_type": "image/png",
            }
        ]
        main._state["models"] = {"image_scanner": FakeImageScanner(ledger=ledger)}
        encoded = base64.b64encode(_png_bytes()).decode("ascii")
        env = {
            "KAYPOH_IMAGE_SCAN_PROVIDER": "openai_vision",
            "KAYPOH_IMAGE_SCAN_TENANT_OPT_IN_OPENAI": "1",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            with TestClient(main.app) as client:
                response = client.post(
                    "/review",
                    json={"document_base64": encoded, "document_filename": "scan.png"},
                )

        self.assertEqual(response.status_code, 200, response.text)
        entry = response.json()["privacy_ledger"][0]
        self.assertEqual(entry["operation"], "image_ocr")
        self.assertEqual(entry["content_sha256"], "a" * 64)
        self.assertEqual(entry["content_type"], "image/png")


if __name__ == "__main__":
    unittest.main()
