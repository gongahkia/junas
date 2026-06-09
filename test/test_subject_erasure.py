import importlib
import io
import json
import os
import tempfile
import unittest
from contextlib import asynccontextmanager, redirect_stdout
from pathlib import Path

from fastapi.testclient import TestClient


@asynccontextmanager
async def _noop_lifespan(app):
    yield


class SubjectErasureIndexTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)
        os.environ["KAYPOH_JOURNAL_DIR"] = str(self.tmpdir)
        os.environ["KAYPOH_JOURNAL_KEY"] = "subject-erasure-test-key"
        os.environ["KAYPOH_REVIEW_PERSIST"] = "1"
        os.environ["KAYPOH_SUBJECT_INDEX_KEY"] = "subject-index-test-key"

        import backend.main as main_mod
        import kaypoh.anonymize.mapping_store as mapping_mod
        import kaypoh.review.decisions as decisions_mod
        import kaypoh.review.journal as journal_mod
        import kaypoh.review.subject_index as subject_index_mod
        import scripts.erase_subject as erase_subject_mod

        importlib.reload(journal_mod)
        importlib.reload(subject_index_mod)
        importlib.reload(mapping_mod)
        importlib.reload(decisions_mod)
        importlib.reload(main_mod)
        importlib.reload(erase_subject_mod)
        self.main = main_mod
        self.mapping = mapping_mod
        self.decisions = decisions_mod
        self.journal = journal_mod
        self.subject_index = subject_index_mod
        self.erase_subject = erase_subject_mod
        self.main._state.clear()
        self.main.app.openapi_schema = None
        self.main.app.router.lifespan_context = _noop_lifespan

    def tearDown(self):
        self._tmpdir.cleanup()
        for var in (
            "KAYPOH_JOURNAL_DIR",
            "KAYPOH_JOURNAL_KEY",
            "KAYPOH_REVIEW_PERSIST",
            "KAYPOH_SUBJECT_INDEX_KEY",
        ):
            os.environ.pop(var, None)
        import backend.main as main_mod

        importlib.reload(main_mod)

    def test_mapping_index_contains_no_raw_pii(self):
        document_hash = self.mapping.compute_document_hash("secret")
        self.mapping.save_mapping(
            document_hash=document_hash,
            mapping=[
                {
                    "placeholder": "[PERSON_1]",
                    "entity_type": "PERSON",
                    "original_text": "Dr Jane Tan",
                    "occurrence_count": 1,
                },
                {
                    "placeholder": "[NRIC_1]",
                    "entity_type": "NRIC",
                    "original_text": "S1234567D",
                    "occurrence_count": 1,
                },
            ],
        )

        raw_index = self.subject_index.subject_index_path().read_text(encoding="utf-8")
        self.assertNotIn("Dr Jane Tan", raw_index)
        self.assertNotIn("S1234567D", raw_index)

        lookup = self.subject_index.lookup_subject("dr jane tan")
        self.assertEqual(lookup["entries"][0]["entry_type"], "mapping")
        self.assertEqual(lookup["entries"][0]["document_hash"], document_hash)

    def test_review_persistence_indexes_pii_without_raw_pii_in_index(self):
        with TestClient(self.main.app) as client:
            response = client.post(
                "/review",
                json={
                    "text": "Dr Jane Tan signed at jane@example.com. The Purchaser is Acme Pte Ltd.",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "document_type": "SPA",
                },
            )
        self.assertEqual(response.status_code, 200, response.text)

        raw_index = self.subject_index.subject_index_path().read_text(encoding="utf-8")
        self.assertNotIn("Dr Jane Tan", raw_index)
        self.assertNotIn("jane@example.com", raw_index)
        lookup = self.subject_index.lookup_subject("jane@example.com")
        self.assertTrue(any(entry["entry_type"] == "review" for entry in lookup["entries"]))

    def test_persistence_fails_closed_when_subject_index_key_missing(self):
        os.environ.pop("KAYPOH_SUBJECT_INDEX_KEY", None)
        with TestClient(self.main.app) as client:
            response = client.post(
                "/pseudonymize",
                json={
                    "text": "Send Dr Jane Tan S1234567D the draft.",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "document_type": "SPA",
                },
            )

        self.assertEqual(response.status_code, 503)
        detail = response.json()["detail"]
        self.assertEqual(detail["degraded_modes"][0]["mode"], "subject_index")
        self.assertFalse((self.tmpdir / "mappings").exists())

    def test_erase_subject_backfills_deletes_mapping_and_journals_tombstone(self):
        document_hash = self.mapping.compute_document_hash("secret")
        self.mapping.save_mapping(
            document_hash=document_hash,
            mapping=[
                {
                    "placeholder": "[PERSON_1]",
                    "entity_type": "PERSON",
                    "original_text": "Dr Jane Tan",
                    "occurrence_count": 1,
                }
            ],
        )
        self.decisions.start_review_session(
            review_id="rev-1",
            text_hash="review-doc-hash",
            document_type="memo",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            findings=[
                {
                    "id": "f1",
                    "category": "PII",
                    "rule": "named_person",
                    "severity": "high",
                    "matched_text": "Dr Jane Tan",
                    "start_char": 0,
                    "end_char": 11,
                }
            ],
        )
        self.subject_index.reset_index()

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = self.erase_subject.main(
                [
                    "--backfill",
                    "--value",
                    "Dr Jane Tan",
                    "--citation",
                    "DSR-2026-05-28",
                    "--json",
                ]
            )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        erase_payload = payload["operations"][1]
        self.assertEqual(erase_payload["pii_hash"], self.subject_index.subject_hash("Dr Jane Tan"))
        self.assertEqual(erase_payload["deleted_mapping_documents"], [document_hash])
        self.assertEqual(erase_payload["journaled_review_sessions"], ["rev-1"])
        self.assertFalse(self.mapping.mapping_exists(document_hash))

        erasure_events = [
            entry
            for entry in self.journal.read_journal(review_id="rev-1")
            if entry.event_type == self.decisions.EVENT_SUBJECT_ERASURE_RECORDED
        ]
        self.assertEqual(len(erasure_events), 1)
        self.assertEqual(erasure_events[0].payload["citation"], "DSR-2026-05-28")
        self.assertEqual(erasure_events[0].payload["finding_ids"], ["f1"])
        self.assertEqual(self.subject_index.lookup_subject("Dr Jane Tan")["entries"], [])


if __name__ == "__main__":
    unittest.main()
