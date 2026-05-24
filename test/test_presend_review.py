import base64
import unittest
import zipfile
from contextlib import asynccontextmanager
from io import BytesIO

from fastapi.testclient import TestClient

import backend.main as main


@asynccontextmanager
async def _noop_lifespan(app):
    yield


main.app.router.lifespan_context = _noop_lifespan


def _docx_base64(paragraphs: list[str]) -> str:
    body = "".join(
        f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>"
        for paragraph in paragraphs
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body>"
        "</w:document>"
    )
    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", document_xml)
        return base64.b64encode(buffer.getvalue()).decode("ascii")


class PreSendReviewApiTests(unittest.TestCase):
    def setUp(self):
        main._state.clear()
        main.app.openapi_schema = None

    def test_review_flags_sg_pii_and_mnpi_with_suggestions(self):
        text = (
            "Please send the draft to Tan S1234567D.\n"
            "Confidential: Acme Corp will acquire GlobalTech before announcement for $2.5 billion."
        )

        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "document_type": "research_note",
                    "entity_id": "Acme Corp",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["overall_risk"], "HIGH_RISK")
        self.assertEqual(payload["classification"], "HIGH_RISK")
        self.assertGreater(payload["pii_score"], 0)
        self.assertGreater(payload["mnpi_score"], 0)
        self.assertEqual(payload["jurisdictions_applied"], ["SG"])
        self.assertEqual(payload["document"]["extraction_method"], "inline_text")
        self.assertTrue(payload["suggestions"])
        self.assertIn("PII", {finding["category"] for finding in payload["findings"]})
        self.assertIn("MNPI", {finding["category"] for finding in payload["findings"]})
        self.assertTrue(any(finding["matched_text"] == "S1234567D" for finding in payload["findings"]))

    def test_review_applies_strictest_wins_for_source_destination(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={
                    "text": "Confidential: Acme Corp has undisclosed Q1 earnings guidance.",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "US",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["jurisdiction_policy"], "strictest_wins")
        self.assertEqual(payload["jurisdictions_applied"], ["SG", "US"])
        self.assertEqual(payload["source_jurisdiction"], "SG")
        self.assertEqual(payload["destination_jurisdiction"], "US")

    def test_review_accepts_base64_text_document(self):
        encoded = base64.b64encode(
            b"Contact Dr Jane Tan at jane.tan@example.com about public update."
        ).decode("ascii")

        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={
                    "document_base64": encoded,
                    "document_filename": "memo.txt",
                    "document_mime_type": "text/plain",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["document"]["filename"], "memo.txt")
        self.assertEqual(payload["document"]["extraction_method"], "base64_text")
        self.assertTrue(any(finding["rule"] == "email_address" for finding in payload["findings"]))

    def test_review_accepts_docx_base64_document(self):
        encoded = _docx_base64(["Send passport no. E1234567 and confidential guidance to reviewer."])

        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={
                    "document_base64": encoded,
                    "document_filename": "draft.docx",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SEA",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["document"]["mime_type"], "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.assertEqual(payload["document"]["extraction_method"], "docx_xml")
        self.assertEqual(payload["jurisdictions_applied"], ["SG", "SEA"])
        self.assertTrue(any(finding["rule"] == "passport_number" for finding in payload["findings"]))

    def test_review_rejects_unsupported_document_type(self):
        encoded = base64.b64encode(b"raw bytes").decode("ascii")

        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={
                    "document_base64": encoded,
                    "document_filename": "memo.bin",
                    "document_mime_type": "application/octet-stream",
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("unsupported document_mime_type", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
