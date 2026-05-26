import base64
import os
import types
import unittest
import zipfile
from contextlib import asynccontextmanager
from io import BytesIO
from unittest import mock

from fastapi.testclient import TestClient
from PIL import Image

import backend.main as main
from kaypoh.review.document import extract_review_document
from kaypoh.review.image_scan import (
    AWSRekognitionImageScanner,
    AzureVisionImageScanner,
    GoogleVisionImageScanner,
    ImageBoundingBox,
    ImageCandidate,
    ImageLocator,
    ImageOcrResult,
    ImageScanError,
    ImageTextRegion,
    OpenAIVisionImageScanner,
    collect_docx_images,
    scan_image_candidates,
)
from kaypoh.workflow.privacy_guard import PrivacyGuard


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
        regions = [
            ImageTextRegion(
                text=self.text,
                start_char=0,
                end_char=len(self.text),
                bounding_box=ImageBoundingBox(x=0.05, y=0.1, width=0.6, height=0.5),
                confidence=0.98,
            )
        ]
        return ImageOcrResult(
            text=self.text,
            locator=candidate.locator,
            provider=self.provider,
            privacy_ledger=list(self.ledger),
            confidence=0.98,
            regions=regions,
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
        self.assertEqual(finding["image_ocr_confidence"], 0.98)
        self.assertEqual(finding["image_ocr_regions"][0]["bounding_box"]["x"], 0.05)
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
        detail = response.json()["detail"]
        self.assertEqual(detail["message"], "fake OCR unavailable")
        self.assertEqual(detail["degraded_modes"][0]["status"], "failed_closed")

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

    def test_anonymize_returns_redacted_image_artifact_when_boxes_exist(self):
        main._state["models"] = {"image_scanner": FakeImageScanner(text="S1234567D")}
        encoded = base64.b64encode(_png_bytes()).decode("ascii")
        with mock.patch.dict(os.environ, {"KAYPOH_IMAGE_SCAN_PROVIDER": "tesseract"}, clear=False):
            with TestClient(main.app) as client:
                response = client.post(
                    "/anonymize",
                    json={
                        "document_base64": encoded,
                        "document_filename": "scan.png",
                        "source_jurisdiction": "SG",
                        "destination_jurisdiction": "SG",
                    },
                )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("[NRIC_FIN_1]", payload["anonymized_text"])
        self.assertEqual(len(payload["redacted_images"]), 1)
        redacted = payload["redacted_images"][0]
        self.assertEqual(redacted["mime_type"], "image/png")
        self.assertGreater(len(base64.b64decode(redacted["document_base64"])), 0)
        self.assertEqual(payload["degraded_modes"], [])

    def test_anonymize_reports_degraded_mode_when_boxes_missing(self):
        class NoBoxScanner(FakeImageScanner):
            def scan(self, candidate):
                return ImageOcrResult(text="S1234567D", locator=candidate.locator, provider=self.provider)

        main._state["models"] = {"image_scanner": NoBoxScanner()}
        encoded = base64.b64encode(_png_bytes()).decode("ascii")
        with mock.patch.dict(os.environ, {"KAYPOH_IMAGE_SCAN_PROVIDER": "tesseract"}, clear=False):
            with TestClient(main.app) as client:
                response = client.post(
                    "/anonymize",
                    json={"document_base64": encoded, "document_filename": "scan.png"},
                )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["redacted_images"], [])
        self.assertEqual(payload["degraded_modes"][0]["mode"], "image_redaction")

    def test_scan_image_candidates_enforces_total_byte_limit(self):
        candidate = ImageCandidate(
            data=b"x" * 10,
            mime_type="image/png",
            locator=ImageLocator(container_path="a.png", image_index=0),
        )
        settings = types.SimpleNamespace(max_images=4, max_bytes=1024, max_total_bytes=12)
        with self.assertRaises(ImageScanError) as ctx:
            scan_image_candidates([candidate, candidate], scanner=FakeImageScanner(), settings=settings)

        self.assertIn("total image bytes", str(ctx.exception))

    def test_pdf_ocr_uses_page_render_fallback_when_no_embedded_images(self):
        rendered = ImageCandidate(
            data=_png_bytes(),
            mime_type="image/png",
            locator=ImageLocator(
                container_path="page-1.png",
                image_index=0,
                page_number=1,
                source_type="pdf_page_render",
            ),
        )
        payload = types.SimpleNamespace(
            document_base64=base64.b64encode(b"%PDF-stub").decode("ascii"),
            document_filename="scan.pdf",
            document_mime_type="application/pdf",
        )
        image_settings = types.SimpleNamespace(pdf_render_pages=True, pdf_render_max_pages=1, pdf_render_scale=1.0)
        with mock.patch("kaypoh.review.document._extract_pdf") as extract_pdf:
            with mock.patch("kaypoh.review.document.collect_pdf_images", return_value=[]):
                with mock.patch("kaypoh.review.document.collect_pdf_page_renders", return_value=[rendered]) as renderer:
                    extract_pdf.return_value = ("", 1, "ocr_pending", ["sparse PDF"])
                    document = extract_review_document(
                        payload,
                        types.SimpleNamespace(fail_closed=True),
                        image_scan_enabled=True,
                        image_scan_settings=image_settings,
                    )

        self.assertEqual(document.image_candidates, [rendered])
        renderer.assert_called_once()
        self.assertIn("PDF rendered 1 page", document.extraction_warnings[-1])

    def test_aws_rekognition_provider_parses_regions_and_ledger(self):
        class FakeRekognitionClient:
            def detect_text(self, Image):
                return {
                    "TextDetections": [
                        {
                            "Type": "LINE",
                            "DetectedText": "S1234567D",
                            "Confidence": 99.0,
                            "Geometry": {"BoundingBox": {"Left": 0.1, "Top": 0.2, "Width": 0.3, "Height": 0.4}},
                        }
                    ]
                }

        fake_boto3 = types.SimpleNamespace(client=lambda *args, **kwargs: FakeRekognitionClient())
        settings = types.SimpleNamespace(
            provider="aws_rekognition",
            aws_region="ap-southeast-1",
            tenant_opt_in_aws=False,
            tenant_opt_ins={"tenant-a": ("aws_rekognition",)},
        )
        guard = PrivacyGuard(external_query_policy="sanitized_only", max_query_chars=256)
        candidate = ImageCandidate(
            data=_png_bytes(),
            mime_type="image/png",
            locator=ImageLocator(container_path="scan.png", image_index=0),
        )
        with mock.patch.dict("sys.modules", {"boto3": fake_boto3}):
            scanner = AWSRekognitionImageScanner(settings, privacy_guard=guard, tenant_id="tenant-a")
            result = scanner.scan(candidate)

        self.assertEqual(result.text, "S1234567D")
        self.assertEqual(result.regions[0].bounding_box.x, 0.1)
        self.assertEqual(result.privacy_ledger[0]["allowed"], True)

    def test_openai_vision_provider_sends_image_and_parses_text(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"output_text": "S1234567D"}

        class FakeClient:
            last_json = None

            def __init__(self, timeout):
                self.timeout = timeout

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def post(self, url, headers, json):
                FakeClient.last_json = json
                return FakeResponse()

        settings = types.SimpleNamespace(
            provider="openai_vision",
            openai_api_key="sk-test",
            openai_base_url="https://api.openai.test/v1/responses",
            model="gpt-4o-mini",
            timeout_seconds=3.0,
            tenant_opt_in_openai=False,
            tenant_opt_ins={"tenant-a": ("openai_vision",)},
        )
        guard = PrivacyGuard(external_query_policy="sanitized_only", max_query_chars=256)
        candidate = ImageCandidate(
            data=_png_bytes(),
            mime_type="image/png",
            locator=ImageLocator(container_path="scan.png", image_index=0),
        )
        with mock.patch("kaypoh.review.image_scan.httpx.Client", FakeClient):
            scanner = OpenAIVisionImageScanner(settings, privacy_guard=guard, tenant_id="tenant-a")
            result = scanner.scan(candidate)

        self.assertEqual(result.text, "S1234567D")
        self.assertEqual(FakeClient.last_json["model"], "gpt-4o-mini")
        image_part = FakeClient.last_json["input"][0]["content"][1]
        self.assertTrue(image_part["image_url"].startswith("data:image/png;base64,"))
        self.assertEqual(result.privacy_ledger[0]["destination"], "openai_vision")

    def test_google_vision_provider_parses_annotations(self):
        class FakeVertex:
            def __init__(self, x, y):
                self.x = x
                self.y = y

        class FakeAnnotation:
            def __init__(self, description, vertices=None):
                self.description = description
                self.bounding_poly = types.SimpleNamespace(normalized_vertices=vertices or [])

        class FakeGoogleResponse:
            error = types.SimpleNamespace(message="")
            full_text_annotation = types.SimpleNamespace(text="S1234567D")
            text_annotations = [
                FakeAnnotation("S1234567D"),
                FakeAnnotation("S1234567D", [FakeVertex(0.1, 0.2), FakeVertex(0.4, 0.2), FakeVertex(0.4, 0.5)]),
            ]

        class FakeVisionModule:
            class Image:
                def __init__(self, content):
                    self.content = content

            class ImageAnnotatorClient:
                def document_text_detection(self, image):
                    return FakeGoogleResponse()

        settings = types.SimpleNamespace(
            provider="google_vision",
            tenant_opt_in_google=False,
            tenant_opt_ins={"tenant-a": ("google_vision",)},
        )
        guard = PrivacyGuard(external_query_policy="sanitized_only", max_query_chars=256)
        candidate = ImageCandidate(
            data=_png_bytes(),
            mime_type="image/png",
            locator=ImageLocator(container_path="scan.png", image_index=0),
        )
        with mock.patch.dict(
            "sys.modules",
            {
                "google": types.SimpleNamespace(),
                "google.cloud": types.SimpleNamespace(vision=FakeVisionModule),
                "google.cloud.vision": FakeVisionModule,
            },
        ):
            scanner = GoogleVisionImageScanner(settings, privacy_guard=guard, tenant_id="tenant-a")
            result = scanner.scan(candidate)

        self.assertEqual(result.text, "S1234567D")
        self.assertEqual(result.regions[0].bounding_box.x, 0.1)
        self.assertEqual(result.privacy_ledger[0]["destination"], "google_vision")

    def test_azure_vision_provider_parses_read_lines(self):
        class FakeImageAnalysisClient:
            def __init__(self, endpoint, credential):
                self.endpoint = endpoint
                self.credential = credential

            def analyze(self, image_data, visual_features):
                line = types.SimpleNamespace(
                    text="S1234567D",
                    bounding_polygon=[0.1, 0.2, 0.4, 0.2, 0.4, 0.5, 0.1, 0.5],
                )
                block = types.SimpleNamespace(lines=[line])
                return types.SimpleNamespace(read=types.SimpleNamespace(blocks=[block]))

        class FakeCredential:
            def __init__(self, key):
                self.key = key

        fake_imageanalysis = types.SimpleNamespace(ImageAnalysisClient=FakeImageAnalysisClient)
        fake_models = types.SimpleNamespace(VisualFeatures=types.SimpleNamespace(READ="read"))
        fake_credentials = types.SimpleNamespace(AzureKeyCredential=FakeCredential)
        settings = types.SimpleNamespace(
            provider="azure_vision",
            azure_endpoint="https://azure.test",
            azure_key="test-key",
            tenant_opt_in_azure=False,
            tenant_opt_ins={"tenant-a": ("azure_vision",)},
        )
        guard = PrivacyGuard(external_query_policy="sanitized_only", max_query_chars=256)
        candidate = ImageCandidate(
            data=_png_bytes(),
            mime_type="image/png",
            locator=ImageLocator(container_path="scan.png", image_index=0),
        )
        with mock.patch.dict(
            "sys.modules",
            {
                "azure": types.SimpleNamespace(),
                "azure.ai": types.SimpleNamespace(),
                "azure.ai.vision": types.SimpleNamespace(imageanalysis=fake_imageanalysis),
                "azure.ai.vision.imageanalysis": fake_imageanalysis,
                "azure.ai.vision.imageanalysis.models": fake_models,
                "azure.core": types.SimpleNamespace(credentials=fake_credentials),
                "azure.core.credentials": fake_credentials,
            },
        ):
            scanner = AzureVisionImageScanner(settings, privacy_guard=guard, tenant_id="tenant-a")
            result = scanner.scan(candidate)

        self.assertEqual(result.text, "S1234567D")
        self.assertAlmostEqual(result.regions[0].bounding_box.width, 0.3)
        self.assertEqual(result.privacy_ledger[0]["destination"], "azure_vision")

    def test_diagnostics_include_image_scan_dependency(self):
        with TestClient(main.app) as client:
            response = client.get("/diagnostics")

        self.assertEqual(response.status_code, 200)
        image_status = response.json()["dependency_status"]["image_scan"]
        self.assertEqual(image_status["status"], "disabled")
        self.assertFalse(image_status["configured"])


if __name__ == "__main__":
    unittest.main()
