"""Mocked coverage advice stays outside source findings and contextual decisions."""

import unittest

from junas.review.engine import PreSendReviewEngine, ReviewLayerError


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
        text = "Acme acquisition for $2.5 billion is pending."  # non-high MNPI findings
        engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="memo",
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
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
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
            text="Acme acquisition for $2.5 billion is pending.",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="memo",
            review_profile="audit_grade",
        )
        self.assertEqual(len(result.coverage_warnings), 2)
        self.assertEqual(result.coverage_warnings[0]["rule_guess"], "embargo_marker")
        self.assertFalse(any(f.rule == "llm_raised_finding" for f in result.findings))
        self.assertTrue(all(w["advisory_only"] for w in result.coverage_warnings))
        self.assertTrue(all(w["evidence_status"] == "unverified" for w in result.coverage_warnings))
        baseline = PreSendReviewEngine().review(
            text="Acme acquisition for $2.5 billion is pending.",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="memo",
            review_profile="audit_grade",
        )
        self.assertEqual(result.findings, baseline.findings)
        self.assertEqual(result.sensitivity, baseline.sensitivity)

    def test_documents_without_mnpi_do_not_call_auditor_or_gain_findings(self):
        auditor = DummyAuditor()
        engine = PreSendReviewEngine(llm_coverage_auditor=auditor)
        text = "Lunch invite for Friday."
        result_strict = engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile="strict",
        )
        result_audit = engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile="audit_grade",
        )
        self.assertEqual(result_strict.sensitivity, result_audit.sensitivity)
        self.assertEqual(len(result_strict.findings), len(result_audit.findings))
        self.assertEqual(auditor.calls, 0)

    def test_requested_high_severity_remains_advisory_only(self):
        engine = PreSendReviewEngine(llm_coverage_auditor=HighWarningAuditor())
        result = engine.review(
            text="Acme acquisition for $2.5 billion is pending.",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="memo",
            review_profile="audit_grade",
        )
        self.assertFalse(any(f.rule == "llm_raised_finding" for f in result.findings))
        self.assertEqual(result.coverage_warnings[0]["severity"], "high")
        self.assertFalse(result.coverage_warnings[0]["classification_applied"])

    def test_strict_profile_never_calls_auditor(self):
        auditor = DummyAuditor()
        engine = PreSendReviewEngine(llm_coverage_auditor=auditor)
        engine.review(
            text="Confidential acquisition for $2.5 billion.",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="memo",
            review_profile="strict",
        )
        self.assertEqual(auditor.calls, 0)

    def test_failing_auditor_fails_closed_under_engine(self):
        engine = PreSendReviewEngine(llm_coverage_auditor=FailingAuditor())
        text = "Acme acquisition for $2.5 billion is pending."  # non-high MNPI findings
        with self.assertRaises(ReviewLayerError) as ctx:
            engine.review(
                text=text,
                source_jurisdiction="SG",
                destination_jurisdiction="SG",
                entity_id=None,
                include_suggestions=False,
                document_type="memo",
                review_profile="audit_grade",
            )
        self.assertEqual(ctx.exception.layer, "llm_coverage_audit")

    def test_malformed_warning_fields_fail_closed_under_engine(self):
        class BadAuditor:
            def audit(self, *, findings, body_hash, document_type):
                return [
                    {"rule_guess": "x", "why": "ok"},  # valid
                    "not a dict",  # rejected
                    {"rule_guess": "missing why"},  # rejected — missing why
                    {"why": "missing rule_guess"},  # rejected
                    {"rule_guess": "y", "why": "ok2"},  # valid
                ]

        engine = PreSendReviewEngine(llm_coverage_auditor=BadAuditor())
        with self.assertRaises(ReviewLayerError) as ctx:
            engine.review(
                text="Acme acquisition for $2.5 billion is pending.",
                source_jurisdiction="SG",
                destination_jurisdiction="SG",
                entity_id=None,
                include_suggestions=False,
                document_type="memo",
                review_profile="audit_grade",
            )
        self.assertEqual(ctx.exception.layer, "llm_coverage_audit")


if __name__ == "__main__":
    unittest.main()
