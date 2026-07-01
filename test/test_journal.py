import importlib
import os
import tempfile
import unittest
from pathlib import Path


def _reload_journal(tmpdir: Path, key: str = "test-key"):
    os.environ["JUNAS_JOURNAL_DIR"] = str(tmpdir)
    os.environ["JUNAS_JOURNAL_KEY"] = key
    import junas.review.journal as journal_mod

    return importlib.reload(journal_mod)


class JournalChainTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)
        self.journal = _reload_journal(self.tmpdir)

    def tearDown(self):
        self._tmpdir.cleanup()
        for var in ("JUNAS_JOURNAL_DIR", "JUNAS_JOURNAL_KEY", "JUNAS_JOURNAL_KEYS_FILE", "JUNAS_DEPLOYMENT_MODE"):
            os.environ.pop(var, None)
        importlib.reload(self.journal)

    def test_chain_is_valid_after_three_appends(self):
        self.journal.append_event(event_type="x", review_id="r1", payload={"a": 1})
        self.journal.append_event(event_type="y", review_id="r1", payload={"b": 2})
        self.journal.append_event(event_type="z", review_id="r1", payload={"c": 3})
        entries = self.journal.read_journal()
        self.assertEqual([e.seq for e in entries], [0, 1, 2])
        valid, errors = self.journal.verify_chain(entries)
        self.assertTrue(valid, errors)

    def test_tampered_payload_fails_chain(self):
        e1 = self.journal.append_event(event_type="x", review_id="r1", payload={"a": 1})
        self.journal.append_event(event_type="y", review_id="r1", payload={"b": 2})

        # rewrite the file with a modified payload on entry 0
        path = self.tmpdir / "journal.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        tampered = lines[0].replace('"a":1', '"a":999')
        self.assertNotEqual(tampered, lines[0])
        path.write_text("\n".join([tampered] + lines[1:]) + "\n", encoding="utf-8")

        valid, errors = self.journal.verify_chain()
        self.assertFalse(valid)
        self.assertTrue(any("hmac mismatch" in err for err in errors), errors)
        # the legitimate first entry's hmac is irrelevant to the failure but pulled into errors
        self.assertEqual(e1.seq, 0)

    def test_chain_sealed_with_key_a_fails_verification_under_key_b(self):
        self.journal.append_event(event_type="x", review_id="r1", payload={"a": 1})
        os.environ["JUNAS_JOURNAL_KEY"] = "key-b"

        valid, errors = self.journal.verify_chain()

        self.assertFalse(valid)
        self.assertTrue(any("hmac mismatch" in err for err in errors), errors)

    def test_production_mode_without_journal_key_fails_on_import(self):
        key = os.environ.pop("JUNAS_JOURNAL_KEY", None)
        os.environ.pop("JUNAS_JOURNAL_KEYS_FILE", None)
        os.environ["JUNAS_DEPLOYMENT_MODE"] = "production"
        try:
            with self.assertRaisesRegex(RuntimeError, "JUNAS_JOURNAL_KEY or JUNAS_JOURNAL_KEYS_FILE is required"):
                importlib.reload(self.journal)
        finally:
            if key is not None:
                os.environ["JUNAS_JOURNAL_KEY"] = key
            os.environ.pop("JUNAS_DEPLOYMENT_MODE", None)
            self.journal = importlib.reload(self.journal)

    def test_read_journal_filters_by_review_id(self):
        self.journal.append_event(event_type="x", review_id="r1", payload={})
        self.journal.append_event(event_type="x", review_id="r2", payload={})
        self.journal.append_event(event_type="x", review_id="r1", payload={})
        r1_only = self.journal.read_journal(review_id="r1")
        self.assertEqual([e.seq for e in r1_only], [0, 2])


if __name__ == "__main__":
    unittest.main()
