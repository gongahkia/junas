import base64
import io
import json
import unittest
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin

import junas.backend.main as main


@asynccontextmanager
async def _noop_lifespan(app):
    yield


class IrreversiblePrivacyTests(unittest.TestCase):
    def setUp(self):
        self.previous = main.app.router.lifespan_context
        main.app.router.lifespan_context = _noop_lifespan
        main._state.clear()

    def tearDown(self):
        main.app.router.lifespan_context = self.previous

    def _assert_response(self, endpoint):
        secrets = ["S1234567D", "synthetic@example.test"]
        with TestClient(main.app) as client:
            response = client.post(
                endpoint,
                json={
                    "text": "中文🙂 Send S1234567D to synthetic@example.test.",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "US",
                },
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(any(f["rule"] == "quasi_identifier_combination" for f in data["findings"]))
        for secret in secrets:
            self.assertNotIn(secret, json.dumps(data), "irreversible diagnostics must not echo matched values")
        self.assertTrue(all(f["id"] and f["start_char"] < f["end_char"] for f in data["findings"]))
        self.assertFalse(data["send_allowed"])
        self.assertFalse(data["mapping_persisted"])

    def test_redact_does_not_echo_nested_quasi_identifier_components(self):
        self._assert_response("/redact")

    def test_anonymize_does_not_echo_findings_or_suggestion_rationales(self):
        self._assert_response("/anonymize")

    def test_irreversible_response_omits_original_container_metadata_previews(self):
        secret = "T1234567D"
        image = Image.new("RGB", (32, 32), "white")
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("SyntheticPrivateNote", secret)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", pnginfo=metadata)
        payload = {
            "document_base64": base64.b64encode(buffer.getvalue()).decode(),
            "document_filename": "synthetic.png",
            "document_mime_type": "image/png",
        }
        with TestClient(main.app) as client:
            for endpoint in ["/redact", "/anonymize"]:
                response = client.post(endpoint, json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["document"]["metadata_findings"])
                self.assertNotIn(secret, response.text)

    def test_validation_errors_do_not_echo_invalid_text_mapping_or_unexpected_field_names(self):
        secret = "S1234567D"
        cases = [
            ("/review", {"text": {"private_marker": secret}}),
            ("/classify", {"text": [secret]}),
            ("/redact", {"text": [secret]}),
            (
                "/reidentify",
                {
                    "anonymized_text": "[PERSON_1]",
                    "mapping": [
                        {"placeholder": "[PERSON_1]", "original_text": {"private_marker": secret}},
                    ],
                },
            ),
            ("/adapter-telemetry", {"events": [{secret: "synthetic private field"}]}),
        ]
        with TestClient(main.app) as client:
            for endpoint, payload in cases:
                with self.subTest(endpoint=endpoint):
                    response = client.post(endpoint, json=payload)
                    self.assertEqual(response.status_code, 422)
                    self.assertNotIn(secret, response.text)
                    self.assertTrue(response.json()["detail"])
