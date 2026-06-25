import base64
import json
import os
import tempfile
import unittest
import uuid
import zipfile
from contextlib import asynccontextmanager
from io import BytesIO

from fastapi.testclient import TestClient

import kaypoh.backend.main as main


@asynccontextmanager
async def _noop_lifespan(app):
    yield


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
        self._old_lifespan = main.app.router.lifespan_context
        main.app.router.lifespan_context = _noop_lifespan
        main._state.clear()
        main.app.openapi_schema = None

    def tearDown(self):
        main.app.router.lifespan_context = self._old_lifespan

    def test_pseudonymize_returns_deterministic_placeholders_and_mapping(self):
        text = (
            "Send Dr Jane Tan S1234567D at jane@example.com. "
            "Acme expects $2.5 billion before announcement. jane@example.com again."
        )

        with TestClient(main.app) as client:
            response = client.post(
                "/pseudonymize",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "US",
                    "document_type": "email",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["privacy_operation"], "pseudonymize")
        self.assertEqual(payload["classification"], "HIGH_RISK")
        self.assertEqual(payload["jurisdictions_applied"], ["SG", "US"])
        self.assertEqual(
            payload["pseudonymized_text"],
            (
                "Send [PERSON_1] [NRIC_FIN_1] at [EMAIL_1]. "
                "Acme expects [MONETARY_1] before announcement. [EMAIL_1] again."
            ),
        )
        self.assertEqual(payload["anonymized_text"], payload["pseudonymized_text"])
        mapping = {entry["placeholder"]: entry for entry in payload["mapping"]}
        self.assertEqual(mapping["[PERSON_1]"]["original_text"], "Dr Jane Tan")
        self.assertEqual(mapping["[NRIC_FIN_1]"]["original_text"], "S1234567D")
        self.assertEqual(mapping["[EMAIL_1]"]["occurrence_count"], 2)
        self.assertEqual(mapping["[MONETARY_1]"]["original_text"], "$2.5 billion")
        self.assertEqual(len(payload["replacements"]), 5)
        self.assertIn("review", payload["timings_ms"])
        self.assertIn("pseudonymize", payload["timings_ms"])

    def test_anonymize_is_irreversible_placeholder_only(self):
        text = "Send Dr Jane Tan S1234567D at jane@example.com."

        with TestClient(main.app) as client:
            response = client.post(
                "/anonymize",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "document_type": "email",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["privacy_operation"], "anonymize")
        self.assertEqual(payload["anonymization_mode"], "placeholder_only")
        self.assertEqual(payload["anonymized_text"], "Send [PERSON_1] [NRIC_FIN_1] at [EMAIL_1].")
        self.assertIn("[PERSON_1]", payload["anonymized_text"])
        self.assertNotIn("[QUASI_IDENTIFIER_COMBINATION_1]", payload["anonymized_text"])
        self.assertTrue(any(finding["rule"] == "quasi_identifier_combination" for finding in payload["findings"]))
        self.assertNotIn("mapping", payload)
        self.assertFalse(payload["mapping_persisted"])
        self.assertTrue(payload["replacements"])
        self.assertFalse(any("original_text" in item for item in payload["replacements"]))

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
        self.assertFalse(any(entry["entity_type"] == "MONETARY" for entry in payload["replacements"]))

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
        self.assertEqual(payload["document"]["extraction_method"], "docx_container_xml")
        self.assertEqual(payload["document"]["filename"], "draft.docx")
        self.assertIn("[PASSPORT_1]", payload["anonymized_text"])
        self.assertIn("[PERSON_1]", payload["anonymized_text"])
        self.assertIn("[EMAIL_1]", payload["anonymized_text"])

    def test_anonymize_flags_sg_uen_as_high_severity_pii(self):
        text = "Counterparty Acme Pte Ltd (UEN 200512345A) and trustee T08LL1234A signed today."

        with TestClient(main.app) as client:
            response = client.post(
                "/anonymize",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        uen_findings = [f for f in payload["findings"] if f["rule"] == "sg_uen"]
        matched_text = {f["matched_text"] for f in uen_findings}
        self.assertEqual(matched_text, {"200512345A", "T08LL1234A"})
        for finding in uen_findings:
            self.assertEqual(finding["severity"], "high")
        # legacy uen 200512345A occupies the same span as a potential nric scan but nric requires
        # a leading letter so the two recognizers should not collide. confirm uen replacements landed.
        self.assertIn("[UEN_1]", payload["anonymized_text"])
        self.assertIn("[UEN_2]", payload["anonymized_text"])

    def test_named_person_severity_lifts_for_sensitive_document_types(self):
        text = "The Vendor is Dr Jane Tan and the Purchaser is Mr John Lim."

        with TestClient(main.app) as client:
            generic = client.post(
                "/review",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "document_type": "generic",
                },
            )
            spa = client.post(
                "/review",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "document_type": "SPA",
                },
            )

        generic_named = [f for f in generic.json()["findings"] if f["rule"] == "named_person"]
        spa_named = [f for f in spa.json()["findings"] if f["rule"] == "named_person"]
        self.assertTrue(generic_named)
        self.assertTrue(spa_named)
        for finding in generic_named:
            self.assertEqual(finding["severity"], "low")
        for finding in spa_named:
            self.assertEqual(finding["severity"], "high")

    def test_reidentify_restores_anonymized_text_round_trip(self):
        original = (
            "Send Dr Jane Tan S1234567D at jane@example.com. "
            "Acme expects $2.5 billion before announcement. jane@example.com again."
        )

        with TestClient(main.app) as client:
            anon = client.post(
                "/pseudonymize",
                json={
                    "text": original,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "US",
                    "document_type": "email",
                },
            )
            self.assertEqual(anon.status_code, 200)
            anon_payload = anon.json()

            restored = client.post(
                "/reidentify",
                json={
                    "anonymized_text": anon_payload["anonymized_text"],
                    "mapping": [
                        {"placeholder": entry["placeholder"], "original_text": entry["original_text"]}
                        for entry in anon_payload["mapping"]
                    ],
                },
            )

        self.assertEqual(restored.status_code, 200)
        restored_payload = restored.json()
        # the original text used the normalized form (whitespace collapsed). round-trip must reproduce
        # the engine's normalized text exactly.
        self.assertEqual(restored_payload["text"], original)
        self.assertGreaterEqual(restored_payload["replacement_count"], len(anon_payload["replacements"]))
        self.assertIn("reidentify", restored_payload["timings_ms"])

    def test_reidentify_by_anonymize_hash_returns_404(self):
        original_journal_dir = os.environ.get("KAYPOH_JOURNAL_DIR")
        original_persist = os.environ.get("KAYPOH_REVIEW_PERSIST")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["KAYPOH_JOURNAL_DIR"] = tmp
            os.environ["KAYPOH_REVIEW_PERSIST"] = "1"
            text = f"Send Dr Jane Tan S1234567D. {uuid.uuid4()}"

            with TestClient(main.app) as client:
                anon = client.post(
                    "/anonymize",
                    json={
                        "text": text,
                        "source_jurisdiction": "SG",
                        "destination_jurisdiction": "SG",
                    },
                )
                self.assertEqual(anon.status_code, 200)
                anon_payload = anon.json()
                restored = client.post(
                    "/reidentify",
                    json={
                        "anonymized_text": anon_payload["anonymized_text"],
                        "document_hash": anon_payload["document_hash"],
                    },
                )

            self.assertEqual(restored.status_code, 404)
        if original_journal_dir is None:
            os.environ.pop("KAYPOH_JOURNAL_DIR", None)
        else:
            os.environ["KAYPOH_JOURNAL_DIR"] = original_journal_dir
        if original_persist is None:
            os.environ.pop("KAYPOH_REVIEW_PERSIST", None)
        else:
            os.environ["KAYPOH_REVIEW_PERSIST"] = original_persist

    def test_redact_uses_opaque_markers_without_original_text(self):
        text = "Send Dr Jane Tan S1234567D at jane@example.com."

        with TestClient(main.app) as client:
            response = client.post(
                "/redact",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "document_type": "email",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["privacy_operation"], "redact")
        self.assertEqual(payload["redaction_style"], "opaque_text_marker")
        self.assertIn("[REDACTED_1]", payload["redacted_text"])
        self.assertNotIn("Dr Jane Tan", payload["redacted_text"])
        self.assertFalse(payload["mapping_persisted"])
        self.assertEqual(payload["suggestions"], [])
        self.assertTrue(payload["findings"])
        self.assertFalse(any("matched_text" in finding for finding in payload["findings"]))
        self.assertFalse(any("original_text" in item or "entity_type" in item for item in payload["redactions"]))

    def test_redact_response_does_not_leak_original_text_outside_findings(self):
        text = "Send Dr Jane Tan S1234567D at jane@example.com."
        sensitive_values = ("Dr Jane Tan", "S1234567D", "jane@example.com")

        with TestClient(main.app) as client:
            review = client.post(
                "/review",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "document_type": "email",
                },
            )
            redacted = client.post(
                "/redact",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "document_type": "email",
                },
            )

        self.assertEqual(review.status_code, 200, review.text)
        review_matches = {finding.get("matched_text") for finding in review.json()["findings"]}
        self.assertTrue(set(sensitive_values) & review_matches)

        self.assertEqual(redacted.status_code, 200, redacted.text)
        payload = redacted.json()
        non_finding_payload = dict(payload)
        non_finding_payload.pop("findings", None)
        non_finding_json = json.dumps(non_finding_payload, sort_keys=True)
        for value in sensitive_values:
            self.assertNotIn(value, non_finding_json)
        self.assertFalse(any("matched_text" in finding for finding in payload["findings"]))

    def test_anonymize_and_redact_do_not_persist_mapping_or_subject_index(self):
        original_persist = os.environ.get("KAYPOH_REVIEW_PERSIST")
        os.environ["KAYPOH_REVIEW_PERSIST"] = "1"
        original_save = main._save_persisted_mapping
        original_index = main.index_review_findings

        def fail_mapping(*args, **kwargs):
            raise AssertionError("mapping persistence should not be called")

        def fail_subject_index(*args, **kwargs):
            raise AssertionError("subject index should not be written")

        main._save_persisted_mapping = fail_mapping
        main.index_review_findings = fail_subject_index
        try:
            with TestClient(main.app) as client:
                for endpoint, text_field in (("/anonymize", "anonymized_text"), ("/redact", "redacted_text")):
                    response = client.post(
                        endpoint,
                        json={
                            "text": "Send Dr Jane Tan S1234567D at jane@example.com.",
                            "source_jurisdiction": "SG",
                            "destination_jurisdiction": "SG",
                        },
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(text_field, response.json())
        finally:
            main._save_persisted_mapping = original_save
            main.index_review_findings = original_index
            if original_persist is None:
                os.environ.pop("KAYPOH_REVIEW_PERSIST", None)
            else:
                os.environ["KAYPOH_REVIEW_PERSIST"] = original_persist

    def test_reidentify_handles_placeholder_prefix_collision(self):
        # PERSON_1 must not be replaced first when PERSON_10 also exists. longest-placeholder-first
        # ordering is what guarantees this.
        anonymized = "[PERSON_10] met [PERSON_1] at noon."
        mapping = [
            {"placeholder": "[PERSON_1]", "original_text": "Jane"},
            {"placeholder": "[PERSON_10]", "original_text": "John"},
        ]

        with TestClient(main.app) as client:
            response = client.post(
                "/reidentify",
                json={"anonymized_text": anonymized, "mapping": mapping},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["text"], "John met Jane at noon.")
        self.assertEqual(payload["replacement_count"], 2)


if __name__ == "__main__":
    unittest.main()
