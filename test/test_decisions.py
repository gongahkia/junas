import importlib
import os
import tempfile
import unittest
from pathlib import Path


def _setup_isolated_journal(tmpdir: Path):
    os.environ["KAYPOH_JOURNAL_DIR"] = str(tmpdir)
    os.environ["KAYPOH_JOURNAL_KEY"] = "test-key"
    import kaypoh.review.decisions as decisions_mod
    import kaypoh.review.journal as journal_mod

    importlib.reload(journal_mod)
    importlib.reload(decisions_mod)
    return journal_mod, decisions_mod


class DecisionStateMachineTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)
        self.journal_mod, self.decisions_mod = _setup_isolated_journal(self.tmpdir)

    def tearDown(self):
        self._tmpdir.cleanup()
        for var in ("KAYPOH_JOURNAL_DIR", "KAYPOH_JOURNAL_KEY"):
            os.environ.pop(var, None)
        importlib.reload(self.journal_mod)
        importlib.reload(self.decisions_mod)

    def _seed_session(self):
        return self.decisions_mod.start_review_session(
            review_id="rev-1",
            text_hash="hash-1",
            document_type="SPA",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            findings=[
                {"id": "f1", "category": "PII", "rule": "named_person", "severity": "high",
                 "matched_text": "Dr Jane Tan", "start_char": 0, "end_char": 11},
                {"id": "f2", "category": "PII", "rule": "email_address", "severity": "medium",
                 "matched_text": "jane@x.com", "start_char": 20, "end_char": 30},
            ],
        )

    def test_record_decision_appends_event_and_returns_seq(self):
        self._seed_session()
        result = self.decisions_mod.record_decision(
            review_id="rev-1",
            decision=self.decisions_mod.Decision(finding_id="f1", action="reject", rationale="defined term"),
        )
        self.assertEqual(result["action"], "reject")
        self.assertEqual(result["reviewer_identity_source"], "none")
        self.assertEqual(result["seq"], 1)
        self.assertTrue(result["hmac"])

    def test_record_decision_rejects_unknown_finding(self):
        self._seed_session()
        with self.assertRaises(self.decisions_mod.ReviewSessionError):
            self.decisions_mod.record_decision(
                review_id="rev-1",
                decision=self.decisions_mod.Decision(finding_id="bogus", action="accept"),
            )

    def test_record_decision_rejects_unknown_session(self):
        with self.assertRaises(self.decisions_mod.ReviewSessionError):
            self.decisions_mod.record_decision(
                review_id="missing",
                decision=self.decisions_mod.Decision(finding_id="f1", action="accept"),
            )

    def test_record_decision_rejects_invalid_action(self):
        self._seed_session()
        with self.assertRaises(self.decisions_mod.ReviewSessionError):
            self.decisions_mod.record_decision(
                review_id="rev-1",
                decision=self.decisions_mod.Decision(finding_id="f1", action="archive"),
            )

    def test_findings_after_decisions_drops_rejected_keeps_undecided(self):
        self._seed_session()
        self.decisions_mod.record_decision(
            review_id="rev-1",
            decision=self.decisions_mod.Decision(
                finding_id="f1",
                action="reject",
                reviewer_id="casey",
                reviewer_identity_source="api_key",
            ),
        )
        state = self.decisions_mod.get_session_state(review_id="rev-1")
        kept = self.decisions_mod.findings_after_decisions(state)
        kept_ids = {f["id"] for f in kept}
        self.assertEqual(kept_ids, {"f2"})  # f1 rejected, f2 undecided defaults to kept

    def test_findings_after_decisions_keeps_unauthorized_reject(self):
        self._seed_session()
        self.decisions_mod.record_decision(
            review_id="rev-1",
            decision=self.decisions_mod.Decision(finding_id="f1", action="reject"),
        )
        state = self.decisions_mod.get_session_state(review_id="rev-1")
        kept = self.decisions_mod.findings_after_decisions(state)
        kept_ids = {f["id"] for f in kept}
        self.assertEqual(kept_ids, {"f1", "f2"})

    def test_verify_journal_warns_on_mixed_identity_sources(self):
        import scripts.verify_journal as verify_journal

        entries = [
            self.journal_mod.JournalEntry(
                seq=0,
                ts="2026-05-28T00:00:00Z",
                event_type="decision_recorded",
                review_id="rev-1",
                payload={"reviewer_id": "legacy-reviewer"},
                prev_hash="",
                hmac="",
            ),
            self.journal_mod.JournalEntry(
                seq=1,
                ts="2026-05-28T00:00:01Z",
                event_type="decision_recorded",
                review_id="rev-1",
                payload={"reviewer_id": "casey", "reviewer_identity_source": "jwt"},
                prev_hash="",
                hmac="",
            ),
        ]

        self.assertEqual(
            verify_journal._identity_source_warnings(entries),
            ["review rev-1 has mixed reviewer identity sources: jwt, legacy"],
        )


if __name__ == "__main__":
    unittest.main()
