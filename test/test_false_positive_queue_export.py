import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_false_positive_queue import build_queue, write_queue


class FalsePositiveQueueExportTests(unittest.TestCase):
    def _entries(self):
        return [
            {
                "seq": 0,
                "ts": "2026-07-01T00:00:00Z",
                "event_type": "review_started",
                "review_id": "review-1",
                "payload": {
                    "text_hash": "doc-hash-1",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "findings": [
                        {
                            "id": "f1",
                            "category": "PII",
                            "rule": "named_person",
                            "jurisdiction": "SG",
                            "severity": "high",
                            "matched_text": "Dr Jane Tan",
                            "matched_text_sha256": "hash-of-name",
                            "matched_text_char_count": 11,
                        }
                    ],
                },
                "prev_hash": "GENESIS",
                "hmac": "h0",
            },
            {
                "seq": 1,
                "ts": "2026-07-01T00:00:01Z",
                "event_type": "decision_recorded",
                "review_id": "review-1",
                "payload": {
                    "finding_id": "f1",
                    "action": "reject",
                    "reviewer_id": "alice",
                    "reviewer_identity_source": "api_key",
                    "decision_taxonomy": "false_positive",
                    "reviewer_confidence": 0.91,
                    "detector_feedback": {
                        "detector_issue_category": "defined_term_or_placeholder",
                        "rule_id": "named_person",
                    },
                },
                "prev_hash": "h0",
                "hmac": "h1",
            },
            {
                "seq": 2,
                "ts": "2026-07-01T00:00:02Z",
                "event_type": "decision_recorded",
                "review_id": "review-1",
                "payload": {
                    "finding_id": "f1",
                    "action": "reject",
                    "reviewer_id": "",
                    "reviewer_identity_source": "none",
                },
                "prev_hash": "h1",
                "hmac": "h2",
            },
            {
                "seq": 3,
                "ts": "2026-07-01T00:00:03Z",
                "event_type": "decision_recorded",
                "review_id": "review-1",
                "payload": {
                    "finding_id": "f1",
                    "action": "accept",
                    "reviewer_id": "alice",
                    "reviewer_identity_source": "api_key",
                },
                "prev_hash": "h2",
                "hmac": "h3",
            },
        ]

    def test_build_queue_exports_only_authorized_reviewer_rejects(self):
        rows = build_queue(self._entries())

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["queue_type"], "false_positive_review")
        self.assertEqual(row["finding_id"], "f1")
        self.assertEqual(row["rule"], "named_person")
        self.assertEqual(row["decision_taxonomy"], "false_positive")
        self.assertEqual(row["detector_issue_category"], "defined_term_or_placeholder")
        self.assertEqual(row["document_id_hash"], hashlib.sha256(b"doc-hash-1").hexdigest())
        self.assertEqual(row["document_hash_source"], "text_hash")
        self.assertEqual(row["reviewer_id_hash"], hashlib.sha256(b"alice").hexdigest())
        serialized = json.dumps(row, sort_keys=True)
        self.assertNotIn("review-1", serialized)
        self.assertNotIn("Dr Jane Tan", serialized)

    def test_write_queue_emits_fixture_sidecar_templates_without_raw_text(self):
        rows = build_queue(self._entries())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "queue.jsonl"
            sidecar_dir = root / "sidecars"

            summary = write_queue(rows, output, sidecar_dir)

            self.assertEqual(summary["rows"], 1)
            queue_text = output.read_text(encoding="utf-8")
            self.assertNotIn("Dr Jane Tan", queue_text)
            written_row = json.loads(queue_text)
            sidecar_path = Path(written_row["fixture_sidecar_template"])
            self.assertTrue(sidecar_path.exists())
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            self.assertEqual(sidecar["schema_version"], "junas.false_positive_fixture_sidecar.v1")
            self.assertFalse(sidecar["customer_sample_approved"])
            self.assertTrue(sidecar["requires_human_review"])
            self.assertEqual(sidecar["must_not_detect"][0]["rule"], "named_person")
            sidecar_text = json.dumps(sidecar, sort_keys=True)
            self.assertNotIn("Dr Jane Tan", sidecar_text)
            self.assertNotIn("review-1", sidecar_text)


if __name__ == "__main__":
    unittest.main()
