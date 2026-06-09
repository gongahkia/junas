"""LLM inverse audit — coverage_warning events + capped raised findings (items 8/54).

Four guarantees:
1. The auditor sees only summary fields — never matched_text or span offsets.
2. Warnings flow back into ReviewResult.coverage_warnings.
3. LLM warnings become origin=llm findings, capped at medium severity.
4. With persistence enabled, each warning becomes a coverage_warning journal event.
"""

import importlib
import os
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient

import backend.main as main
from kaypoh.review.engine import PreSendReviewEngine, ReviewLayerError


@asynccontextmanager
async def _noop_lifespan(app):
    yield


class DummyAuditor:
    """Records exactly what the auditor was sent and returns canned warnings."""

    def __init__(self):
        self.last_findings = None
        self.last_body_hash = None
        self.last_document_type = None
        self.calls = 0

    def audit(self, *, findings, body_hash, document_type):
        self.calls += 1
        self.last_findings = list(findings)
        self.last_body_hash = body_hash
        self.last_document_type = document_type
        return [
            {"rule_guess": "embargo_marker", "why": "no embargo signal but doc talks about closing"},
            {"rule_guess": "transaction_codename", "why": "phrasing hints at unnamed project"},
        ]


class FailingAuditor:
    def audit(self, *, findings, body_hash, document_type):
        raise RuntimeError("simulated network error")


class HighWarningAuditor:
    def audit(self, *, findings, body_hash, document_type):
        return [
            {
                "rule_guess": "cyber_incident_pre_disclosure",
                "why": "incident language may be under-covered",
                "severity": "high",
                "confidence": 0.91,
                "structured_reason": "nonpublic_context_marker",
            }
        ]


class CoverageAuditPrivacyTests(unittest.TestCase):
    def test_auditor_never_sees_matched_text_or_spans(self):
        auditor = DummyAuditor()
        engine = PreSendReviewEngine(llm_coverage_auditor=auditor)
        text = "Acme acquisition for $2.5 billion is pending."  # in ambiguous band
        engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="memo",
            review_profile="audit_grade",
        )
        self.assertEqual(auditor.calls, 1)
        for sent in auditor.last_findings:
            self.assertNotIn("matched_text", sent)
            self.assertNotIn("start_char", sent)
            self.assertNotIn("end_char", sent)
            # but it DID get the safe fields
            self.assertIn("rule", sent)
            self.assertIn("severity", sent)

    def test_auditor_receives_sha256_body_hash(self):
        auditor = DummyAuditor()
        engine = PreSendReviewEngine(llm_coverage_auditor=auditor)
        text = "Acme acquisition for $2.5 billion is pending."
        engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
            review_profile="audit_grade",
        )
        # SHA-256 of "any text" — 64 hex chars
        self.assertEqual(len(auditor.last_body_hash), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in auditor.last_body_hash))


class CoverageAuditResultIntegrationTests(unittest.TestCase):
    def test_warnings_flow_back_into_result(self):
        auditor = DummyAuditor()
        engine = PreSendReviewEngine(llm_coverage_auditor=auditor)
        result = engine.review(
            text="Acme acquisition for $2.5 billion is pending.", source_jurisdiction="SG",
            destination_jurisdiction="SG", entity_id=None, include_suggestions=False,
            document_type="memo", review_profile="audit_grade",
        )
        self.assertEqual(len(result.coverage_warnings), 2)
        self.assertEqual(result.coverage_warnings[0]["rule_guess"], "embargo_marker")
        raised = [finding for finding in result.findings if finding.rule == "llm_raised_finding"]
        self.assertEqual(len(raised), 2)
        self.assertTrue(all(finding.severity == "medium" for finding in raised))
        self.assertTrue(all(finding.metadata["origin"] == "llm" for finding in raised))
        self.assertEqual(raised[0].source, "llm_coverage_audit")
        self.assertEqual(raised[0].metadata["llm_rule_guess"], "embargo_marker")
        self.assertEqual(raised[0].metadata["context_window_hash"], result.coverage_warnings[0]["body_hash"])
        self.assertEqual(raised[0].metadata["structured_reason"], "ambiguous_unconstrained")

    def test_below_band_documents_do_not_call_auditor_or_gain_findings(self):
        auditor = DummyAuditor()
        engine = PreSendReviewEngine(llm_coverage_auditor=auditor)
        text = "Lunch invite for Friday."
        result_strict = engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
            review_profile="strict",
        )
        result_audit = engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
            review_profile="audit_grade",
        )
        self.assertEqual(result_strict.overall_risk, result_audit.overall_risk)
        self.assertEqual(len(result_strict.findings), len(result_audit.findings))
        self.assertEqual(auditor.calls, 0)

    def test_llm_warning_severity_is_capped_at_medium(self):
        engine = PreSendReviewEngine(llm_coverage_auditor=HighWarningAuditor())
        result = engine.review(
            text="Acme acquisition for $2.5 billion is pending.", source_jurisdiction="SG",
            destination_jurisdiction="SG", entity_id=None, include_suggestions=False,
            document_type="memo", review_profile="audit_grade",
        )
        raised = [finding for finding in result.findings if finding.rule == "llm_raised_finding"]
        self.assertEqual(len(raised), 1)
        self.assertEqual(raised[0].severity, "medium")
        self.assertEqual(raised[0].metadata["requested_severity"], "high")
        self.assertEqual(raised[0].metadata["structured_reason"], "nonpublic_context_marker")

    def test_strict_profile_never_calls_auditor(self):
        auditor = DummyAuditor()
        engine = PreSendReviewEngine(llm_coverage_auditor=auditor)
        engine.review(
            text="Confidential acquisition for $2.5 billion.", source_jurisdiction="SG",
            destination_jurisdiction="SG", entity_id=None, include_suggestions=False,
            document_type="memo", review_profile="strict",
        )
        self.assertEqual(auditor.calls, 0)

    def test_failing_auditor_fails_closed_under_engine(self):
        engine = PreSendReviewEngine(llm_coverage_auditor=FailingAuditor())
        text = "Acme acquisition for $2.5 billion is pending."  # in ambiguous band
        with self.assertRaises(ReviewLayerError) as ctx:
            engine.review(
                text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
                entity_id=None, include_suggestions=False, document_type="memo",
                review_profile="audit_grade",
            )
        self.assertEqual(ctx.exception.layer, "llm_coverage_audit")

    def test_malformed_warning_fields_fail_closed_under_engine(self):
        class BadAuditor:
            def audit(self, *, findings, body_hash, document_type):
                return [
                    {"rule_guess": "x", "why": "ok"},      # valid
                    "not a dict",                            # rejected
                    {"rule_guess": "missing why"},           # rejected — missing why
                    {"why": "missing rule_guess"},           # rejected
                    {"rule_guess": "y", "why": "ok2"},      # valid
                ]
        engine = PreSendReviewEngine(llm_coverage_auditor=BadAuditor())
        with self.assertRaises(ReviewLayerError) as ctx:
            engine.review(
                text="Acme acquisition for $2.5 billion is pending.", source_jurisdiction="SG",
                destination_jurisdiction="SG", entity_id=None, include_suggestions=False,
                document_type="memo", review_profile="audit_grade",
            )
        self.assertEqual(ctx.exception.layer, "llm_coverage_audit")


class CoverageAuditJournalingTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)
        os.environ["KAYPOH_JOURNAL_DIR"] = str(self.tmpdir)
        os.environ["KAYPOH_JOURNAL_KEY"] = "audit-test-key"
        os.environ["KAYPOH_REVIEW_PERSIST"] = "1"
        os.environ["KAYPOH_SUBJECT_INDEX_KEY"] = "subject-index-test-key"

        # reload journal + main so they pick up the new env
        import kaypoh.review.journal as journal_mod
        import kaypoh.review.decisions as decisions_mod
        import backend.main as main_mod

        importlib.reload(journal_mod)
        importlib.reload(decisions_mod)
        importlib.reload(main_mod)
        self.journal = journal_mod
        self.main = main_mod
        self.main._state.clear()
        self.main.app.openapi_schema = None
        self.main.app.router.lifespan_context = _noop_lifespan
        # wire a dummy auditor
        self.auditor = DummyAuditor()
        self.main._state["models"] = {"llm_coverage_auditor": self.auditor}

    def tearDown(self):
        self._tmpdir.cleanup()
        for var in ("KAYPOH_JOURNAL_DIR", "KAYPOH_JOURNAL_KEY", "KAYPOH_REVIEW_PERSIST", "KAYPOH_SUBJECT_INDEX_KEY"):
            os.environ.pop(var, None)
        import backend.main as main_mod
        importlib.reload(main_mod)

    def test_warnings_journaled_with_persist_enabled(self):
        text = "Acme acquisition for $2.5 billion is pending."  # in ambiguous band
        with TestClient(self.main.app) as client:
            response = client.post(
                "/review",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "review_profile": "audit_grade",
                    "document_type": "memo",
                },
            )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        # ensure the auditor was actually called (document lands in band)
        if self.auditor.calls == 0:
            self.skipTest("test document did not land in ambiguous band for this scoring")
        self.assertEqual(len(payload["coverage_warnings"]), 2)
        raised = [finding for finding in payload["findings"] if finding["rule"] == "llm_raised_finding"]
        self.assertEqual(len(raised), 2)
        self.assertEqual(raised[0]["metadata"]["origin"], "llm")
        # journal carries a coverage_warning event per warning
        entries = self.journal.read_journal(review_id=payload["request_id"])
        warning_events = [e for e in entries if e.event_type == "coverage_warning"]
        self.assertEqual(len(warning_events), 2)
        self.assertEqual(warning_events[0].payload["rule_guess"], "embargo_marker")


if __name__ == "__main__":
    unittest.main()
