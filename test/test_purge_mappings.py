import importlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


class PurgeMappingsTenantTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)
        self._env = {
            "JUNAS_JOURNAL_DIR": str(self.tmpdir),
            "JUNAS_REVIEW_PERSIST": "1",
            "JUNAS_MAPPING_STORE_KEY": "q5cVCBcQ0PHsgxBpwoXOrp0tGSgZBz7oBfZmuZBFLJk=",
            "JUNAS_SUBJECT_INDEX_KEY": "subject-index-test-key",
        }
        self._old_env = {key: os.environ.get(key) for key in self._env}
        os.environ.update(self._env)

        import junas.anonymize.mapping_store as mapping_mod
        import junas.review.subject_index as subject_index_mod
        import scripts.purge_mappings as purge_mappings_mod

        importlib.reload(subject_index_mod)
        importlib.reload(mapping_mod)
        importlib.reload(purge_mappings_mod)
        self.mapping = mapping_mod
        self.purge_mappings = purge_mappings_mod

    def tearDown(self):
        self._tmpdir.cleanup()
        for key, old_value in self._old_env.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value

    def _run_json(self, *args: str) -> dict:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = self.purge_mappings.main([*args, "--json"])
        self.assertEqual(exit_code, 0)
        return json.loads(stdout.getvalue())

    def test_tenant_a_cannot_list_or_match_tenant_b_mapping_by_guessed_hash(self):
        mapping = [
            {
                "placeholder": "[PERSON_1]",
                "entity_type": "PERSON",
                "original_text": "Dr Jane Tan",
                "occurrence_count": 1,
            }
        ]
        tenant_a_hash = self.mapping.compute_document_hash("tenant-a-secret")
        tenant_b_hash = self.mapping.compute_document_hash("tenant-b-secret")
        self.mapping.save_mapping(document_hash=tenant_a_hash, mapping=mapping, tenant_id="tenant-a")
        self.mapping.save_mapping(document_hash=tenant_b_hash, mapping=mapping, tenant_id="tenant-b")

        listed = self._run_json("--tenant", "tenant-a", "--older-than-days", "0", "--dry-run")
        listed_hashes = {item["document_hash"] for item in listed["mappings"]}
        self.assertIn(tenant_a_hash, listed_hashes)
        self.assertNotIn(tenant_b_hash, listed_hashes)

        guessed = self._run_json("--tenant", "tenant-a", "--document-hash", tenant_b_hash, "--dry-run")
        self.assertFalse(guessed["matched"])
        self.assertTrue(self.mapping.mapping_exists(tenant_b_hash, tenant_id="tenant-b"))


if __name__ == "__main__":
    unittest.main()
