import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class AuditPackTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)
        os.environ["KAYPOH_JOURNAL_DIR"] = str(self.tmpdir)
        os.environ["KAYPOH_JOURNAL_KEY"] = "audit-test-key"

        import kaypoh.review.journal as journal_mod
        import kaypoh.review.decisions as decisions_mod

        importlib.reload(journal_mod)
        importlib.reload(decisions_mod)
        self.journal = journal_mod
        self.decisions = decisions_mod

    def tearDown(self):
        self._tmpdir.cleanup()
        for var in ("KAYPOH_JOURNAL_DIR", "KAYPOH_JOURNAL_KEY"):
            os.environ.pop(var, None)
        importlib.reload(self.journal)
        importlib.reload(self.decisions)

    def _seed(self):
        self.decisions.start_review_session(
            review_id="rev-pack",
            text_hash="hash-x",
            document_type="SPA",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            findings=[
                {"id": "f1", "category": "PII", "rule": "named_person", "severity": "high",
                 "matched_text": "Dr Jane Tan", "start_char": 0, "end_char": 11},
            ],
        )
        self.decisions.record_decision(
            review_id="rev-pack",
            decision=self.decisions.Decision(finding_id="f1", action="reject", rationale="defined term"),
        )

    def _run(self, script: str, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / script), *args],
            capture_output=True,
            text=True,
            env=env,
            cwd=REPO_ROOT,
        )

    def test_export_and_verify_round_trip(self):
        self._seed()
        output = self.tmpdir / "pack.zip"

        export = self._run("export_audit_pack.py", "rev-pack", "--output", str(output))
        self.assertEqual(export.returncode, 0, msg=export.stderr)
        self.assertTrue(output.exists())

        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            self.assertIn("manifest.json", names)
            self.assertIn("journal.jsonl", names)
            self.assertIn("findings.json", names)
            self.assertIn("decisions.json", names)
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["review_id"], "rev-pack")
            self.assertEqual(manifest["decisions_total"], 1)
            self.assertEqual(manifest["journal_chain_status"], "valid")

        verify = self._run("verify_audit_pack.py", str(output))
        self.assertEqual(verify.returncode, 0, msg=verify.stderr)
        self.assertIn("valid", verify.stdout)

    def test_verify_detects_tampered_manifest(self):
        self._seed()
        output = self.tmpdir / "pack.zip"
        self.assertEqual(self._run("export_audit_pack.py", "rev-pack", "--output", str(output)).returncode, 0)

        # rewrite the ZIP with a mutated manifest while leaving pack_hmac unchanged
        with zipfile.ZipFile(output) as src:
            payloads = {name: src.read(name) for name in src.namelist()}
        manifest = json.loads(payloads["manifest.json"])
        manifest["document_type"] = "NDA"  # tampered
        payloads["manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True).encode()
        tampered_path = self.tmpdir / "tampered.zip"
        with zipfile.ZipFile(tampered_path, "w", zipfile.ZIP_DEFLATED) as dst:
            for name, payload in payloads.items():
                dst.writestr(name, payload)

        verify = self._run("verify_audit_pack.py", str(tampered_path))
        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("pack_hmac mismatch", verify.stderr)


if __name__ == "__main__":
    unittest.main()
