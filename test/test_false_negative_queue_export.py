import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_false_negative_queue import build_queue, write_queue


class FalseNegativeQueueExportTests(unittest.TestCase):
    def _entries(self):
        return [
            {
                "seq": 0,
                "ts": "2026-07-01T00:00:00Z",
                "event_type": "review_started",
                "review_id": "review-1",
                "payload": {
                    "text_hash": "doc-hash-1",
                    "findings": [
                        {
                            "id": "f1",
                            "category": "MNPI",
                            "rule": "material_event",
                            "jurisdiction": "SG",
                            "severity": "high",
                            "matched_text": "Project Falcon",
                            "matched_text_sha256": "hash-project-falcon",
                            "matched_text_char_count": 14,
                        },
                        {
                            "id": "f2",
                            "category": "PII",
                            "rule": "email_address",
                            "jurisdiction": "SG",
                            "severity": "medium",
                            "matched_text_sha256": "hash-email",
                            "matched_text_char_count": 16,
                        },
                    ],
                },
                "prev_hash": "GENESIS",
                "hmac": "h0",
            },
            {
                "seq": 1,
                "ts": "2026-07-01T00:00:01Z",
                "event_type": "approval_requested",
                "review_id": "review-1",
                "payload": {
                    "approval_status": "pending",
                    "requested_action": "request_approval",
                    "finding_ids": ["f1", "f2"],
                    "reason_code": "approval_required",
                    "requester_id": "requester@example.com",
                    "requester_identity_source": "api_key",
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
                    "finding_id": "f2",
                    "action": "approve",
                    "reviewer_id": "checker",
                    "reviewer_identity_source": "api_key",
                },
                "prev_hash": "h1",
                "hmac": "h2",
            },
            {
                "seq": 3,
                "ts": "2026-07-01T00:00:03Z",
                "event_type": "reviewer_finding_added",
                "review_id": "review-1",
                "payload": {
                    "finding_id": "miss-1",
                    "category": "PII",
                    "rule": "phone_number",
                    "jurisdiction": "SG",
                    "severity": "medium",
                    "matched_text": "+65 6123 4567",
                    "reviewer_id": "checker",
                    "reviewer_identity_source": "jwt",
                    "decision_taxonomy": "false_negative",
                },
                "prev_hash": "h2",
                "hmac": "h3",
            },
            {
                "seq": 4,
                "ts": "2026-07-01T00:00:04Z",
                "event_type": "reviewer_finding_added",
                "review_id": "review-1",
                "payload": {
                    "finding_id": "miss-2",
                    "category": "PII",
                    "rule": "email_address",
                    "matched_text": "jane@example.com",
                    "reviewer_id": "",
                    "reviewer_identity_source": "none",
                },
                "prev_hash": "h3",
                "hmac": "h4",
            },
        ]

    def test_build_queue_exports_unresolved_approval_and_authorized_added_finding(self):
        rows = build_queue(self._entries())

        self.assertEqual([row["signal_type"] for row in rows], ["approval_required_unresolved", "reviewer_added"])
        approval = rows[0]
        self.assertEqual(approval["finding_id"], "f1")
        self.assertEqual(approval["rule"], "material_event")
        self.assertEqual(approval["reason_code"], "approval_required")
        self.assertEqual(approval["matched_text_sha256"], "hash-project-falcon")
        self.assertEqual(approval["document_id_hash"], hashlib.sha256(b"doc-hash-1").hexdigest())
        added = rows[1]
        self.assertEqual(added["finding_id"], "miss-1")
        self.assertEqual(added["rule"], "phone_number")
        self.assertEqual(added["decision_taxonomy"], "false_negative")
        self.assertEqual(added["matched_text_sha256"], hashlib.sha256(b"+65 6123 4567").hexdigest())
        serialized = json.dumps(rows, sort_keys=True)
        self.assertNotIn("Project Falcon", serialized)
        self.assertNotIn("+65 6123 4567", serialized)
        self.assertNotIn("review-1", serialized)
        self.assertNotIn("miss-2", serialized)

    def test_write_queue_emits_candidate_sidecar_templates_without_raw_text(self):
        rows = build_queue(self._entries())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "queue.jsonl"
            sidecar_dir = root / "sidecars"

            summary = write_queue(rows, output, sidecar_dir)

            self.assertEqual(summary["rows"], 2)
            queue_text = output.read_text(encoding="utf-8")
            self.assertNotIn("Project Falcon", queue_text)
            first_row = json.loads(queue_text.splitlines()[0])
            sidecar = json.loads(Path(first_row["candidate_sidecar_template"]).read_text(encoding="utf-8"))
            self.assertEqual(sidecar["schema_version"], "junas.false_negative_candidate_sidecar.v1")
            self.assertFalse(sidecar["customer_sample_approved"])
            self.assertTrue(sidecar["requires_human_review"])
            self.assertEqual(sidecar["candidate_label_template"]["ideal_must_detect"][0]["rule"], "material_event")
            sidecar_text = json.dumps(sidecar, sort_keys=True)
            self.assertNotIn("Project Falcon", sidecar_text)
            self.assertNotIn("review-1", sidecar_text)


if __name__ == "__main__":
    unittest.main()
