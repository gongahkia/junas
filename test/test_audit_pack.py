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

        import kaypoh.review.decisions as decisions_mod
        import kaypoh.review.journal as journal_mod

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

    def test_manifest_reviewer_rollup_counts_actions_per_reviewer(self):
        self.decisions.start_review_session(
            review_id="rev-rollup",
            text_hash="hash-y",
            document_type="SPA",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            findings=[
                {"id": "f1", "category": "PII", "rule": "named_person", "severity": "high",
                 "matched_text": "Dr Jane Tan", "start_char": 0, "end_char": 11},
                {"id": "f2", "category": "PII", "rule": "named_person", "severity": "high",
                 "matched_text": "Mr John Lim", "start_char": 12, "end_char": 23},
                {"id": "f3", "category": "MNPI", "rule": "transaction_codename", "severity": "high",
                 "matched_text": "Project Atlas", "start_char": 24, "end_char": 37},
            ],
        )
        self.decisions.record_decision(
            review_id="rev-rollup",
            decision=self.decisions.Decision(finding_id="f1", action="accept", reviewer_id="alice"),
        )
        self.decisions.record_decision(
            review_id="rev-rollup",
            decision=self.decisions.Decision(finding_id="f2", action="reject", reviewer_id="alice"),
        )
        self.decisions.record_decision(
            review_id="rev-rollup",
            decision=self.decisions.Decision(finding_id="f3", action="rewrite", reviewer_id="bob"),
        )
        output = self.tmpdir / "rollup.zip"
        result = self._run("export_audit_pack.py", "rev-rollup", "--output", str(output))
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        with zipfile.ZipFile(output) as archive:
            manifest = json.loads(archive.read("manifest.json"))
        rollup = manifest["reviewer_rollup"]
        self.assertEqual(rollup["alice"], {"accept": 1, "reject": 1, "rewrite": 0})
        self.assertEqual(rollup["bob"], {"accept": 0, "reject": 0, "rewrite": 1})

    def test_export_with_defensibility_bundles_reports_and_sanitized_manifest(self):
        self.decisions.start_review_session(
            review_id="rev-def",
            text_hash="hash-z",
            document_type="memo",
            source_jurisdiction="SG",
            destination_jurisdiction="US",
            findings=[
                {
                    "id": "f1",
                    "category": "MNPI",
                    "rule": "conjunctive_mnpi",
                    "jurisdiction": "SG+US",
                    "severity": "medium",
                    "matched_text": "Confidential Acme Corp acquisition",
                    "start_char": 0,
                    "end_char": 34,
                    "legal_basis": "SG_SFA_INSIDE_INFORMATION+US_REG_FD",
                    "source_verification": "not_checked",
                    "metadata": {
                        "materiality_state": "undetermined",
                        "non_public_element_satisfied": True,
                        "entity_element_satisfied": True,
                    },
                },
            ],
        )
        self.decisions.record_decision(
            review_id="rev-def",
            decision=self.decisions.Decision(
                finding_id="f1",
                action="accept",
                rationale="raw reviewer rationale should not enter defensibility manifest",
                reviewer_id="alice",
            ),
        )
        self.journal.append_event(
            event_type=self.decisions.EVENT_ANONYMIZE_APPLIED,
            review_id="rev-def",
            payload={"privacy_operation": "pseudonymize"},
        )
        output = self.tmpdir / "def.zip"

        result = self._run("export_audit_pack.py", "rev-def", "--output", str(output), "--include-defensibility")
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            self.assertIn("statutory-coverage.md", names)
            self.assertIn("defensibility_manifest.json", names)
            self.assertIn("defensibility/SG.md", names)
            self.assertIn("defensibility/US.md", names)
            manifest = json.loads(archive.read("manifest.json"))
            defensibility = json.loads(archive.read("defensibility_manifest.json"))

        self.assertTrue(manifest["defensibility_included"])
        self.assertEqual(manifest["privacy_operations"], {"pseudonymize": 1})
        self.assertEqual(manifest["reviewer_action_rates_by_rule"]["conjunctive_mnpi"]["accept_rate"], 1.0)
        defensibility_text = json.dumps(defensibility)
        self.assertIn("conjunctive_mnpi", defensibility_text)
        self.assertNotIn("should not enter defensibility manifest", defensibility_text)
        self.assertNotIn("Confidential Acme Corp acquisition", defensibility_text)

        verify = self._run("verify_audit_pack.py", str(output))
        self.assertEqual(verify.returncode, 0, msg=verify.stderr)

    def test_min_wait_gate_flags_batch_approval(self):
        # immediate accept after session start should trip a non-zero wait bound.
        self._seed()
        output = self.tmpdir / "wait.zip"
        env = dict(os.environ)
        env["KAYPOH_AUDIT_MIN_WAIT_SECONDS"] = "60"
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "export_audit_pack.py"),
             "rev-pack", "--output", str(output)],
            capture_output=True, text=True, env=env, cwd=REPO_ROOT,
        )
        # exit 2 = chain valid but min-wait violation surfaced
        self.assertEqual(result.returncode, 2, msg=result.stderr)
        self.assertIn("min-wait violation", result.stderr)
        with zipfile.ZipFile(output) as archive:
            manifest = json.loads(archive.read("manifest.json"))
        self.assertEqual(manifest["min_wait_status"], "violation")

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
