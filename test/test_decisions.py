import importlib
import os
import tempfile
import unittest
from pathlib import Path


def _setup_isolated_journal(tmpdir: Path):
    os.environ["JUNAS_JOURNAL_DIR"] = str(tmpdir)
    os.environ["JUNAS_JOURNAL_KEY"] = "test-key"
    import junas.review.decisions as decisions_mod
    import junas.review.journal as journal_mod

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
        for var in ("JUNAS_JOURNAL_DIR", "JUNAS_JOURNAL_KEY", "JUNAS_REVIEW_PERSIST_SPANS"):
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

    def test_review_started_hashes_matched_text_by_default(self):
        self._seed_session()
        state = self.decisions_mod.get_session_state(review_id="rev-1")
        finding = state["findings"][0]

        self.assertNotIn("matched_text", finding)
        self.assertIn("matched_text_sha256", finding)
        self.assertEqual(finding["matched_text_char_count"], len("Dr Jane Tan"))

    def test_review_started_persists_matched_text_only_with_explicit_flag(self):
        os.environ["JUNAS_REVIEW_PERSIST_SPANS"] = "1"
        self._seed_session()
        state = self.decisions_mod.get_session_state(review_id="rev-1")
        finding = state["findings"][0]

        self.assertEqual(finding["matched_text"], "Dr Jane Tan")
        self.assertIn("matched_text_sha256", finding)

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

    def test_decision_taxonomy_contract_is_stable(self):
        self.assertEqual(
            self.decisions_mod.DECISION_TAXONOMY,
            (
                "false_positive",
                "false_negative",
                "acceptable_risk",
                "public_source_confirmed",
                "stale_information",
                "policy_exception",
            ),
        )
        self.assertEqual(
            self.decisions_mod.normalize_decision_taxonomy(" false_positive "),
            "false_positive",
        )
        with self.assertRaises(self.decisions_mod.ReviewSessionError):
            self.decisions_mod.normalize_decision_taxonomy("detector_error")

    def test_decision_taxonomy_persists_and_replays_from_journal(self):
        self._seed_session()
        self.decisions_mod.record_decision(
            review_id="rev-1",
            decision=self.decisions_mod.Decision(
                finding_id="f1",
                action="reject",
                decision_taxonomy="false_positive",
                reviewer_confidence=0.9,
                detector_feedback={
                    "detector_issue_category": "defined_term_or_placeholder",
                    "rule_id": "named_person",
                    "evidence_hashes": ["9b86d081884c7d659a2feaa0c55ad015"],
                },
            ),
        )

        entries = self.journal_mod.read_journal(review_id="rev-1")
        payload = entries[-1].payload
        self.assertEqual(payload["decision_taxonomy"], "false_positive")
        self.assertEqual(payload["reviewer_confidence"], 0.9)
        self.assertEqual(payload["detector_feedback"]["rule_id"], "named_person")
        self.assertNotIn("matched_text", payload["detector_feedback"])

        state = self.decisions_mod.get_session_state(review_id="rev-1")
        decision = state["decisions"][0]
        self.assertEqual(decision["decision_taxonomy"], "false_positive")
        self.assertEqual(decision["reviewer_confidence"], 0.9)
        self.assertEqual(decision["detector_feedback"]["detector_issue_category"], "defined_term_or_placeholder")

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
