"""Tests for the persistent per-document mapping store.

Covers:
- /anonymize writes mapping to ${KAYPOH_JOURNAL_DIR}/mappings/<hash>.json when persistence is on
- /reidentify recovers from document_hash alone
- /reidentify 404s on unknown hash
- /reidentify still works with inline mapping when persistence is off
"""

import importlib
import os
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient


@asynccontextmanager
async def _noop_lifespan(app):
    yield


class MappingStorePersistTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)
        os.environ["KAYPOH_JOURNAL_DIR"] = str(self.tmpdir)
        os.environ["KAYPOH_JOURNAL_KEY"] = "mapping-test-key"
        os.environ["KAYPOH_REVIEW_PERSIST"] = "1"

        import kaypoh.review.journal as journal_mod
        import kaypoh.anonymize.mapping_store as mapping_mod
        import backend.main as main_mod

        importlib.reload(journal_mod)
        importlib.reload(mapping_mod)
        importlib.reload(main_mod)
        self.main = main_mod
        self.mapping_mod = mapping_mod
        self.main._state.clear()
        self.main.app.openapi_schema = None
        self.main.app.router.lifespan_context = _noop_lifespan

    def tearDown(self):
        self._tmpdir.cleanup()
        for var in ("KAYPOH_JOURNAL_DIR", "KAYPOH_JOURNAL_KEY", "KAYPOH_REVIEW_PERSIST"):
            os.environ.pop(var, None)
        import backend.main as main_mod
        importlib.reload(main_mod)

    def test_anonymize_persists_mapping_and_reidentify_recovers_from_hash(self):
        text = "Send Dr Jane Tan S1234567D the draft."

        with TestClient(self.main.app) as client:
            anon = client.post(
                "/anonymize",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "document_type": "SPA",
                },
            )
            self.assertEqual(anon.status_code, 200, anon.text)
            anon_payload = anon.json()
            self.assertTrue(anon_payload["document_hash"])
            self.assertTrue(anon_payload["mapping_persisted"])

            # mapping file should exist on disk
            mapping_path = self.tmpdir / "mappings" / f"{anon_payload['document_hash']}.json"
            self.assertTrue(mapping_path.exists(), f"expected mapping at {mapping_path}")

            # /reidentify with only the hash (no inline mapping) recovers the original text
            restored = client.post(
                "/reidentify",
                json={
                    "anonymized_text": anon_payload["anonymized_text"],
                    "document_hash": anon_payload["document_hash"],
                },
            )
            self.assertEqual(restored.status_code, 200, restored.text)
            self.assertEqual(restored.json()["text"], text)

    def test_reidentify_returns_404_for_unknown_hash(self):
        with TestClient(self.main.app) as client:
            response = client.post(
                "/reidentify",
                json={
                    "anonymized_text": "[PERSON_1] sent it.",
                    "document_hash": "0" * 64,
                },
            )
            self.assertEqual(response.status_code, 404)

    def test_anonymize_does_not_persist_when_persistence_disabled(self):
        os.environ["KAYPOH_REVIEW_PERSIST"] = "0"
        # rebind the persistence flag without reimporting the whole module
        import backend.main as main_mod
        importlib.reload(main_mod)
        main_mod._state.clear()
        main_mod.app.openapi_schema = None
        main_mod.app.router.lifespan_context = _noop_lifespan

        with TestClient(main_mod.app) as client:
            anon = client.post(
                "/anonymize",
                json={
                    "text": "Send Dr Jane Tan S1234567D the draft.",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                },
            )
            self.assertEqual(anon.status_code, 200, anon.text)
            payload = anon.json()
            self.assertTrue(payload["document_hash"])  # hash always returned
            self.assertFalse(payload["mapping_persisted"])  # but not written
            # no mapping dir written
            self.assertFalse((self.tmpdir / "mappings").exists())


class ReidentifyInlineMappingStillWorksTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("KAYPOH_REVIEW_PERSIST", None)
        import backend.main as main_mod
        importlib.reload(main_mod)
        self.main = main_mod
        self.main._state.clear()
        self.main.app.openapi_schema = None
        self.main.app.router.lifespan_context = _noop_lifespan

    def tearDown(self):
        import backend.main as main_mod
        importlib.reload(main_mod)

    def test_inline_mapping_still_accepted_without_document_hash(self):
        with TestClient(self.main.app) as client:
            response = client.post(
                "/reidentify",
                json={
                    "anonymized_text": "[PERSON_1] sent it.",
                    "mapping": [{"placeholder": "[PERSON_1]", "original_text": "Dr Jane Tan"}],
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["text"], "Dr Jane Tan sent it.")

    def test_request_with_neither_mapping_nor_hash_returns_422(self):
        with TestClient(self.main.app) as client:
            response = client.post(
                "/reidentify",
                json={"anonymized_text": "[PERSON_1] sent it."},
            )
            self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
