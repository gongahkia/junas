"""JUNAS_JOURNAL_KEYS_FILE keystore + rotate_journal_key sentinel events.

Three guarantees:
1. Entries written under the keystore embed `key_version`; verify_chain resolves keys per-entry.
2. A `journal_key_rolled` sentinel under the new key cleanly bridges old and new entries when
   both keys are still in the keystore.
3. If an auditor drops the OLD key from the keystore, entries sealed under that version fail
   verification with a key-resolution error — proves the rotation isn't a no-op.
"""

import importlib
import os
import tempfile
import unittest
from pathlib import Path


def _write_keystore(path: Path, *, active: str, keys: dict[str, str]) -> None:
    lines = [f'active = "{active}"', ""]
    for version, secret in keys.items():
        lines.append(f"[keys.{version}]")
        lines.append(f'secret = "{secret}"')
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _reload_journal():
    import junas.review.journal as journal_mod
    return importlib.reload(journal_mod)


class JournalKeyRotationTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)
        self.keys_path = self.tmpdir / "keys.toml"
        os.environ["JUNAS_JOURNAL_DIR"] = str(self.tmpdir)
        os.environ.pop("JUNAS_JOURNAL_KEY", None)
        os.environ["JUNAS_JOURNAL_KEYS_FILE"] = str(self.keys_path)

    def tearDown(self):
        self._tmpdir.cleanup()
        for var in ("JUNAS_JOURNAL_DIR", "JUNAS_JOURNAL_KEY", "JUNAS_JOURNAL_KEYS_FILE"):
            os.environ.pop(var, None)
        _reload_journal()

    def test_entries_carry_key_version_when_keystore_configured(self):
        _write_keystore(self.keys_path, active="v1", keys={"v1": "secret-one"})
        journal = _reload_journal()
        entry = journal.append_event(event_type="x", review_id="r1", payload={"a": 1})
        self.assertEqual(entry.key_version, "v1")
        on_disk = (self.tmpdir / "journal.jsonl").read_text(encoding="utf-8")
        self.assertIn('"key_version":"v1"', on_disk)

    def test_legacy_mode_omits_key_version_field(self):
        # no keystore file: behave like the pre-rotation journal — no key_version in the output
        os.environ.pop("JUNAS_JOURNAL_KEYS_FILE", None)
        os.environ["JUNAS_JOURNAL_KEY"] = "legacy-key"
        journal = _reload_journal()
        entry = journal.append_event(event_type="x", review_id="r1", payload={"a": 1})
        self.assertEqual(entry.key_version, "")
        on_disk = (self.tmpdir / "journal.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("key_version", on_disk)
        valid, errors = journal.verify_chain()
        self.assertTrue(valid, errors)

    def test_rotation_writes_sentinel_and_chain_stays_valid(self):
        _write_keystore(self.keys_path, active="v1", keys={"v1": "secret-one"})
        journal = _reload_journal()
        journal.append_event(event_type="x", review_id="r1", payload={"a": 1})
        journal.append_event(event_type="x", review_id="r1", payload={"a": 2})

        # rotate: rewrite keystore with v2 active, both v1+v2 present
        _write_keystore(self.keys_path, active="v2",
                        keys={"v1": "secret-one", "v2": "secret-two"})
        sentinel = journal.rotate_journal_key(to_version="v2", reason="quarterly rotation")
        self.assertEqual(sentinel.event_type, journal.EVENT_JOURNAL_KEY_ROLLED)
        self.assertEqual(sentinel.payload["from_version"], "v1")
        self.assertEqual(sentinel.payload["to_version"], "v2")
        self.assertEqual(sentinel.key_version, "v2")

        # post-rotation event sealed under v2
        post = journal.append_event(event_type="y", review_id="r1", payload={"b": 99})
        self.assertEqual(post.key_version, "v2")

        valid, errors = journal.verify_chain()
        self.assertTrue(valid, errors)

    def test_chain_fails_when_old_key_is_dropped(self):
        _write_keystore(self.keys_path, active="v1", keys={"v1": "secret-one"})
        journal = _reload_journal()
        journal.append_event(event_type="x", review_id="r1", payload={"a": 1})

        _write_keystore(self.keys_path, active="v2",
                        keys={"v1": "secret-one", "v2": "secret-two"})
        journal.rotate_journal_key(to_version="v2", reason="rotate")
        journal.append_event(event_type="y", review_id="r1", payload={"b": 2})

        # auditor view: only v2 in the keystore — v1-sealed entry must fail
        _write_keystore(self.keys_path, active="v2", keys={"v2": "secret-two"})
        valid, errors = journal.verify_chain()
        self.assertFalse(valid)
        self.assertTrue(any("key resolution failed" in e for e in errors), errors)

    def test_rotation_refuses_when_keystore_active_does_not_match(self):
        _write_keystore(self.keys_path, active="v1", keys={"v1": "secret-one"})
        journal = _reload_journal()
        journal.append_event(event_type="x", review_id="r1", payload={"a": 1})
        # keystore still on v1; rotate_journal_key(to_version="v2") should refuse
        with self.assertRaises(journal.KeyResolutionError):
            journal.rotate_journal_key(to_version="v2", reason="premature")

    def test_rotation_refuses_when_no_keystore_configured(self):
        os.environ.pop("JUNAS_JOURNAL_KEYS_FILE", None)
        os.environ["JUNAS_JOURNAL_KEY"] = "legacy"
        journal = _reload_journal()
        with self.assertRaises(journal.KeyResolutionError):
            journal.rotate_journal_key(to_version="v2", reason="no keystore")


if __name__ == "__main__":
    unittest.main()
