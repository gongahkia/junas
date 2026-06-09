"""Tests for the persistent per-document mapping store.

Covers:
- /pseudonymize writes mapping to ${KAYPOH_JOURNAL_DIR}/mappings/<hash>.json when persistence is on
- /reidentify recovers from document_hash alone
- /reidentify 404s on unknown hash
- /reidentify still works with inline mapping when persistence is off
"""

import importlib
import json
import os
import tempfile
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from cryptography.fernet import Fernet
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
        os.environ["KAYPOH_SUBJECT_INDEX_KEY"] = "subject-index-test-key"

        import backend.main as main_mod
        import kaypoh.anonymize.mapping_store as mapping_mod
        import kaypoh.review.journal as journal_mod

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
        for var in (
            "KAYPOH_JOURNAL_DIR",
            "KAYPOH_JOURNAL_KEY",
            "KAYPOH_REVIEW_PERSIST",
            "KAYPOH_MAPPING_STORE_KEY",
            "KAYPOH_SUBJECT_INDEX_KEY",
        ):
            os.environ.pop(var, None)
        import backend.main as main_mod
        importlib.reload(main_mod)

    def test_pseudonymize_persists_mapping_and_reidentify_recovers_from_hash(self):
        text = "Send Dr Jane Tan S1234567D the draft."

        with TestClient(self.main.app) as client:
            anon = client.post(
                "/pseudonymize",
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

    def test_pseudonymize_mapping_store_failure_fails_closed(self):
        with mock.patch.object(self.main, "_save_persisted_mapping", side_effect=OSError("disk full")):
            with TestClient(self.main.app) as client:
                response = client.post(
                    "/pseudonymize",
                    json={
                        "text": "Send Dr Jane Tan S1234567D the draft.",
                        "source_jurisdiction": "SG",
                        "destination_jurisdiction": "SG",
                    },
                )

        self.assertEqual(response.status_code, 503)
        detail = response.json()["detail"]
        self.assertEqual(detail["degraded_modes"][0]["mode"], "mapping_store")
        self.assertEqual(detail["degraded_modes"][0]["status"], "failed_closed")

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

    def test_encrypted_mapping_persists_without_plaintext_and_reidentifies(self):
        os.environ["KAYPOH_MAPPING_STORE_KEY"] = Fernet.generate_key().decode("ascii")
        import backend.main as main_mod
        import kaypoh.anonymize.mapping_store as mapping_mod

        importlib.reload(mapping_mod)
        importlib.reload(main_mod)
        main_mod._state.clear()
        main_mod.app.openapi_schema = None
        main_mod.app.router.lifespan_context = _noop_lifespan

        text = "Send Dr Jane Tan S1234567D the draft."
        with TestClient(main_mod.app) as client:
            anon = client.post(
                "/pseudonymize",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "document_type": "SPA",
                },
            )
            self.assertEqual(anon.status_code, 200, anon.text)
            payload = anon.json()
            mapping_path = self.tmpdir / "mappings" / f"{payload['document_hash']}.json"
            raw_file = mapping_path.read_text(encoding="utf-8")
            self.assertIn('"storage_format": "fernet-v1"', raw_file)
            self.assertNotIn("Dr Jane Tan", raw_file)
            self.assertNotIn("S1234567D", raw_file)

            restored = client.post(
                "/reidentify",
                json={
                    "anonymized_text": payload["anonymized_text"],
                    "document_hash": payload["document_hash"],
                },
            )
            self.assertEqual(restored.status_code, 200, restored.text)
            self.assertEqual(restored.json()["text"], text)

    def test_encrypted_mapping_wrong_or_missing_key_fails_closed(self):
        key = Fernet.generate_key().decode("ascii")
        os.environ["KAYPOH_MAPPING_STORE_KEY"] = key
        import kaypoh.anonymize.mapping_store as mapping_mod

        importlib.reload(mapping_mod)
        doc_hash = mapping_mod.compute_document_hash("secret")
        mapping_mod.save_mapping(
            document_hash=doc_hash,
            mapping=[{"placeholder": "[PERSON_1]", "entity_type": "PERSON", "original_text": "Dr Jane Tan"}],
        )

        os.environ.pop("KAYPOH_MAPPING_STORE_KEY", None)
        with self.assertRaises(mapping_mod.MappingStoreKeyError):
            mapping_mod.load_mapping(doc_hash)

        os.environ["KAYPOH_MAPPING_STORE_KEY"] = Fernet.generate_key().decode("ascii")
        with self.assertRaises(mapping_mod.MappingStoreKeyError):
            mapping_mod.load_mapping(doc_hash)

    def test_legacy_plaintext_mapping_still_loads(self):
        import kaypoh.anonymize.mapping_store as mapping_mod

        importlib.reload(mapping_mod)
        doc_hash = "a" * 64
        mapping_dir = self.tmpdir / "mappings"
        mapping_dir.mkdir(parents=True)
        (mapping_dir / f"{doc_hash}.json").write_text(
            json.dumps(
                {
                    "document_hash": doc_hash,
                    "created_at": "2026-05-24T00:00:00Z",
                    "mapping": [
                        {
                            "placeholder": "[PERSON_1]",
                            "entity_type": "PERSON",
                            "original_text": "Dr Jane Tan",
                            "occurrence_count": 1,
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )

        loaded = mapping_mod.load_mapping(doc_hash)
        self.assertEqual(loaded[0]["original_text"], "Dr Jane Tan")

    def test_purge_by_hash_and_retention(self):
        import kaypoh.anonymize.mapping_store as mapping_mod

        importlib.reload(mapping_mod)
        old_hash = "b" * 64
        new_hash = "c" * 64
        mapping_mod.save_mapping(document_hash=old_hash, mapping=[])
        mapping_mod.save_mapping(document_hash=new_hash, mapping=[])

        old_path = self.tmpdir / "mappings" / f"{old_hash}.json"
        old_payload = json.loads(old_path.read_text(encoding="utf-8"))
        old_payload["created_at"] = (datetime.now(timezone.utc) - timedelta(days=31)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        old_path.write_text(json.dumps(old_payload) + "\n", encoding="utf-8")

        dry_run = mapping_mod.purge_expired_mappings(older_than_days=30, dry_run=True)
        self.assertEqual([item["document_hash"] for item in dry_run], [old_hash])
        self.assertTrue(old_path.exists())

        deleted = mapping_mod.purge_expired_mappings(older_than_days=30, dry_run=False)
        self.assertEqual([item["document_hash"] for item in deleted], [old_hash])
        self.assertFalse(old_path.exists())
        self.assertTrue((self.tmpdir / "mappings" / f"{new_hash}.json").exists())

        self.assertTrue(mapping_mod.mapping_exists(new_hash))
        self.assertTrue(mapping_mod.purge_mapping(new_hash))
        self.assertFalse(mapping_mod.mapping_exists(new_hash))
        self.assertFalse(mapping_mod.purge_mapping(new_hash))


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
