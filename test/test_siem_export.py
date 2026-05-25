import importlib
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from kaypoh.backend import siem


class SIEMExportTests(unittest.TestCase):
    def test_privacy_ledger_event_hashes_query_and_preserves_policy_shape(self):
        raw_query = "Acme Corp jane.doe@example.com S1234567D acquisition"
        events = siem.build_privacy_ledger_siem_events(
            [
                {
                    "destination": "exa",
                    "operation": "external_query",
                    "allowed": False,
                    "reason": "blocked because query still contained PII",
                    "query": raw_query,
                    "redactions": ["email", "long_number"],
                }
            ],
            request_id="req-1",
            endpoint="/review",
        )

        self.assertEqual(len(events), 1)
        event = events[0]
        serialized = json.dumps(event, sort_keys=True)
        self.assertEqual(event["schema_version"], siem.SCHEMA_VERSION)
        self.assertEqual(event["category"], "privacy")
        self.assertEqual(event["outcome"], "blocked")
        self.assertEqual(event["details"]["query"]["char_count"], len(raw_query))
        self.assertIn("query_sha256", event["details"]["query"])
        self.assertNotIn("jane.doe", serialized)
        self.assertNotIn("S1234567D", serialized)
        self.assertNotIn(raw_query, serialized)

    def test_journal_event_exports_summary_without_finding_text(self):
        entry = SimpleNamespace(
            seq=7,
            ts="2026-05-25T00:00:00Z",
            event_type="review_started",
            review_id="review-1",
            key_version="v2",
            payload={
                "text_hash": "a" * 64,
                "findings": [
                    {
                        "id": "pii:1",
                        "rule": "sg_nric_fin",
                        "matched_text": "S1234567D",
                    }
                ],
            },
        )

        event = siem.build_journal_siem_event(entry)
        serialized = json.dumps(event, sort_keys=True)

        self.assertEqual(event["event_type"], "journal_event")
        self.assertEqual(event["category"], "audit")
        self.assertEqual(event["outcome"], "sealed")
        self.assertEqual(event["review_id"], "review-1")
        self.assertEqual(event["details"]["finding_count"], 1)
        self.assertIn("payload_sha256", event["details"])
        self.assertNotIn("S1234567D", serialized)
        self.assertNotIn("matched_text", serialized)

    def test_emit_siem_event_serializes_json_when_enabled(self):
        messages: list[str] = []
        settings = SimpleNamespace(
            enabled=True,
            sink="stdout",
            syslog_address="/var/run/syslog",
            facility="local4",
            app_name="kaypoh-test",
        )

        emitted = siem.emit_siem_event(
            siem.build_security_siem_event(action="api_key_check", outcome="denied"),
            settings=settings,
            emit=messages.append,
        )

        self.assertTrue(emitted)
        payload = json.loads(messages[0])
        self.assertEqual(payload["app"], "kaypoh-test")
        self.assertEqual(payload["schema_version"], siem.SCHEMA_VERSION)
        self.assertEqual(payload["category"], "security")

    def test_journal_append_invokes_siem_without_raw_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(
                os.environ,
                {
                    "KAYPOH_JOURNAL_DIR": tmp,
                    "KAYPOH_JOURNAL_KEY": "siem-test-key",
                },
                clear=False,
            ):
                import kaypoh.review.journal as journal_mod

                journal_mod = importlib.reload(journal_mod)
                captured: list[dict] = []

                def capture(event, **kwargs):
                    captured.append(dict(event))
                    return True

                with mock.patch("kaypoh.backend.siem.emit_siem_event", side_effect=capture):
                    journal_mod.append_event(
                        event_type="review_started",
                        review_id="review-1",
                        payload={
                            "findings": [{"id": "f1", "matched_text": "S1234567D"}],
                        },
                    )

        self.assertEqual(len(captured), 1)
        serialized = json.dumps(captured[0], sort_keys=True)
        self.assertEqual(captured[0]["event_type"], "journal_event")
        self.assertNotIn("S1234567D", serialized)
        self.assertNotIn("matched_text", serialized)


if __name__ == "__main__":
    unittest.main()
