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


class AnonymizeApiTests(unittest.TestCase):
    def setUp(self):
        main._state.clear()
        main.app.openapi_schema = None

    def test_anonymize_returns_deterministic_placeholders_and_mapping(self):
        text = (
            "Send Dr Jane Tan S1234567D at jane@example.com. "
            "Acme expects $2.5 billion before announcement. jane@example.com again."
        )

        with TestClient(main.app) as client:
            response = client.post(
                "/anonymize",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "US",
                    "document_type": "email",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["classification"], "HIGH_RISK")
        self.assertEqual(payload["jurisdictions_applied"], ["SG", "US"])
        self.assertEqual(
            payload["anonymized_text"],
            (
                "Send [PERSON_1] [NRIC_FIN_1] at [EMAIL_1]. "
                "Acme expects [MONETARY_1] before announcement. [EMAIL_1] again."
            ),
        )
        mapping = {entry["placeholder"]: entry for entry in payload["mapping"]}
        self.assertEqual(mapping["[PERSON_1]"]["original_text"], "Dr Jane Tan")
        self.assertEqual(mapping["[NRIC_FIN_1]"]["original_text"], "S1234567D")
        self.assertEqual(mapping["[EMAIL_1]"]["occurrence_count"], 2)
        self.assertEqual(mapping["[MONETARY_1]"]["original_text"], "$2.5 billion")
        self.assertEqual(len(payload["replacements"]), 5)
        self.assertIn("review", payload["timings_ms"])
        self.assertIn("anonymize", payload["timings_ms"])

    def test_anonymize_can_leave_mnpi_scalars_in_review_only(self):
        text = "Send Dr Jane Tan S1234567D. Confidential acquisition value is $2.5 billion."

        with TestClient(main.app) as client:
            response = client.post(
                "/anonymize",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "include_mnpi_scalars": False,
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("[PERSON_1]", payload["anonymized_text"])
        self.assertIn("[NRIC_FIN_1]", payload["anonymized_text"])
        self.assertIn("$2.5 billion", payload["anonymized_text"])
        self.assertTrue(any(finding["rule"] == "financial_amount" for finding in payload["findings"]))
        self.assertFalse(any(entry["entity_type"] == "MONETARY" for entry in payload["mapping"]))

    def test_anonymize_accepts_docx_base64_document(self):
        encoded = _docx_base64(["Send passport no. E1234567 to Dr Jane Tan at jane@example.com."])

        with TestClient(main.app) as client:
            response = client.post(
                "/anonymize",
                json={
                    "document_base64": encoded,
                    "document_filename": "draft.docx",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SEA",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["document"]["extraction_method"], "docx_xml")
        self.assertEqual(payload["document"]["filename"], "draft.docx")
        self.assertIn("[PASSPORT_1]", payload["anonymized_text"])
        self.assertIn("[PERSON_1]", payload["anonymized_text"])
        self.assertIn("[EMAIL_1]", payload["anonymized_text"])


if __name__ == "__main__":
    unittest.main()
