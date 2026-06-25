import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kaypoh.advisory.signals import aggregate_signals, classifier_signal, fingerprint, similarity_signal
from kaypoh.configs.runtime import load_runtime_settings
from kaypoh.integrations.dms import scan_manifest
from kaypoh.review.detectors.semantic import clear_semantic_pii_state_for_tests
from kaypoh.review.engine import PreSendReviewEngine
from scripts.generate_tenant_credentials import generate_entry
from scripts.promote_journal_to_corpus import build_queue
from training.journal_preference_export import export_preferences
from training.severity_calibrator.train import train


class RoadmapSubstrateTests(unittest.TestCase):
    def test_local_socket_path_configures_runtime(self):
        settings = load_runtime_settings(
            {
                "local_daemon.socket_path": "/tmp/kaypoh.sock",
            }
        )
        self.assertEqual(settings.local_daemon.socket_path, "/tmp/kaypoh.sock")

    def test_semantic_appositive_dob_and_age_fallback(self):
        clear_semantic_pii_state_for_tests()
        with mock.patch.dict("os.environ", {"KAYPOH_SEMANTIC_PII_FALLBACK": "1"}):
            result = PreSendReviewEngine().review(
                text="Jane Tan (born 1988) joined. Mr Lee, age 42, is reviewer.",
                source_jurisdiction="SG",
                destination_jurisdiction="SG",
                entity_id=None,
                include_suggestions=False,
            )
        pairs = {(finding.rule, finding.matched_text) for finding in result.findings}
        self.assertIn(("date_of_birth", "1988"), pairs)
        self.assertIn(("age_reference", "42"), pairs)

    def test_advisory_signals_are_transparent(self):
        signal = classifier_signal("Confidential Project Falcon merger announcement before earnings.")
        self.assertGreater(signal.score, 0)
        similar = similarity_signal(
            "Confidential acquisition project",
            [{"doc_hash": "abc", "fingerprint": fingerprint("Confidential acquisition project")}],
        )
        self.assertGreater(similar.score, 0.9)
        aggregate = aggregate_signals(deterministic_score=80, extra_signals=[signal, similar])
        self.assertIn("aggregated_mnpi_score", aggregate)
        self.assertFalse(aggregate["deterministic_high_preserved"])

    def test_journal_preference_export_and_calibrator(self):
        with tempfile.TemporaryDirectory() as td:
            journal = Path(td) / "journal.jsonl"
            entries = [
                {
                    "event_type": "review_started",
                    "review_id": "r1",
                    "payload": {
                        "findings": [
                            {
                                "id": "finding:1",
                                "rule": "email_address",
                                "category": "PII",
                                "severity": "high",
                                "jurisdiction": "SG",
                                "matched_text": "a@example.com",
                            }
                        ]
                    },
                },
                {
                    "event_type": "decision_recorded",
                    "review_id": "r1",
                    "payload": {
                        "finding_id": "finding:1",
                        "action": "accept",
                        "rationale": "confirm a@example.com",
                        "reviewer_identity_source": "api_key",
                    },
                },
                {
                    "event_type": "decision_recorded",
                    "review_id": "r1",
                    "payload": {
                        "finding_id": "finding:1",
                        "action": "policy_exception",
                        "rationale": "approved exception for a@example.com",
                        "reviewer_identity_source": "api_key",
                    },
                },
            ]
            journal.write_text("\n".join(json.dumps(entry) for entry in entries), encoding="utf-8")
            rows = export_preferences(journal)
            self.assertEqual(rows[0]["rationale"], "confirm [REDACTED]")
            self.assertEqual(rows[1]["chosen"], "accept")
            self.assertEqual(rows[1]["rationale"], "approved exception for [REDACTED]")
            model = train(rows, min_rows=1)
            self.assertEqual(model["cells"]["email_address|SG|high"]["recommendation"], "keep_or_tighten")
            queue = build_queue(journal)
            self.assertEqual(queue[0]["queue"], "positive_candidate")
            self.assertEqual(queue[1]["action"], "policy_exception")
            self.assertEqual(queue[1]["queue"], "positive_candidate")

    def test_dms_manifest_scanner(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            doc = root / "doc.txt"
            doc.write_text("Email jane.tan@example.com about Project Falcon.", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "dms": "imanage",
                        "matter_id": "imanage:M123",
                        "documents": [{"document_id": "D1", "path": "doc.txt", "source_jurisdiction": "SG"}],
                    }
                ),
                encoding="utf-8",
            )
            payload = scan_manifest(manifest)
            self.assertEqual(payload["count"], 1)
            self.assertIn("email_address", payload["documents"][0]["rules"])

    def test_tenant_credential_generator_validates_roles(self):
        entry = generate_entry(tenant_id="tenant-a", subject="", roles=["reviewer", "auditor"])
        self.assertEqual(entry["subject"], "tenant-a")
        self.assertTrue(entry["api_key"].startswith("kp_"))
        with self.assertRaises(ValueError):
            generate_entry(tenant_id="tenant-a", subject="", roles=["owner"])


if __name__ == "__main__":
    unittest.main()
