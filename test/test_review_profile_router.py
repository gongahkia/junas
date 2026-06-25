"""Two-tier router + audit_grade profile gating.

Three guarantees:
1. `review_profile=strict` (default): LLM tier never engages, even when adjudicator wired.
2. `review_profile=audit_grade` + score in [LLM_TIER_MNPI_LOWER, LLM_TIER_MNPI_UPPER): LLM fires.
3. `review_profile=audit_grade` but score outside band: LLM does NOT fire (no wasted tokens).
"""

import unittest

from junas.review.engine import (
    LLM_TIER_MNPI_LOWER,
    LLM_TIER_MNPI_UPPER,
    PreSendReviewEngine,
    ReviewLayerError,
)


class DummyAdjudicator:
    def __init__(self):
        self.calls = 0

    def adjudicate(self, **kwargs):
        self.calls += 1
        return {
            "status": "adjudicated",
            "risk_label": "SAFE",
            "public_status": "public",
            "materiality_reason": "synthesised public sources match the claim",
            "matched_public_sources": [],
            "unverified_claims": [],
        }


class DummyPublicEvidence:
    def __init__(self):
        self.calls = 0

    def retrieve(self, *, text, entity_id=None, lexicon=None):
        self.calls += 1
        return {
            "status": "queried",
            "provider": "exa",
            "privacy_ledger": [],
        }


class StrictProfileTests(unittest.TestCase):
    def setUp(self):
        self.adj = DummyAdjudicator()
        self.pe = DummyPublicEvidence()
        self.engine = PreSendReviewEngine(
            public_evidence_retriever=self.pe,
            llm_adjudicator=self.adj,
        )

    def test_strict_never_calls_llm_even_with_ambiguous_score(self):
        # this text produces an ambiguous-band mnpi score (acquisition + $ amount, public context)
        text = "Acme Corp publicly announced its acquisition of GlobalTech for $2.5 billion."
        result = self.engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id="Acme Corp", include_suggestions=False, document_type="generic",
            review_profile="strict",
        )
        self.assertEqual(self.adj.calls, 0, "strict profile must not call the LLM adjudicator")
        self.assertEqual(self.pe.calls, 0, "strict profile must not call public-evidence retrieval")
        self.assertIsNone(result.llm_adjudication)
        self.assertIsNone(result.public_evidence)


class AuditGradeProfileTests(unittest.TestCase):
    def setUp(self):
        self.adj = DummyAdjudicator()
        self.pe = DummyPublicEvidence()
        self.engine = PreSendReviewEngine(
            public_evidence_retriever=self.pe,
            llm_adjudicator=self.adj,
        )

    def test_audit_grade_in_band_calls_llm(self):
        text = "Acme Corp publicly announced its acquisition of GlobalTech for $2.5 billion."
        result = self.engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id="Acme Corp", include_suggestions=False, document_type="generic",
            review_profile="audit_grade",
        )
        # confirm the document lands in the ambiguous band
        self.assertTrue(LLM_TIER_MNPI_LOWER <= result.mnpi_score < LLM_TIER_MNPI_UPPER)
        self.assertEqual(self.adj.calls, 1)
        self.assertEqual(self.pe.calls, 1)

    def test_audit_grade_below_band_skips_llm(self):
        # plain text with no MNPI signal — score should be 0.0, below LOWER
        text = "Hello, this is a perfectly normal sentence with no financial content."
        result = self.engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
            review_profile="audit_grade",
        )
        self.assertLess(result.mnpi_score, LLM_TIER_MNPI_LOWER)
        self.assertEqual(self.adj.calls, 0)
        self.assertEqual(self.pe.calls, 0)

    def test_audit_grade_above_band_skips_llm(self):
        # high-MNPI text: confidential + acquisition + nonpublic — pushes score >= UPPER
        text = (
            "Confidential pre-announcement acquisition of GlobalTech for $2.5 billion. "
            "Material non-public information; do not distribute."
        )
        result = self.engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
            review_profile="audit_grade",
        )
        self.assertGreaterEqual(result.mnpi_score, LLM_TIER_MNPI_UPPER)
        self.assertEqual(self.adj.calls, 0, "score above UPPER means LLM cannot lift it; skip")
        self.assertEqual(self.pe.calls, 0)

    def test_public_evidence_failure_fails_closed(self):
        class FailingPublicEvidence:
            def retrieve(self, **kwargs):
                raise RuntimeError("retriever down")

        engine = PreSendReviewEngine(public_evidence_retriever=FailingPublicEvidence())
        with self.assertRaises(ReviewLayerError) as ctx:
            engine.review(
                text="Acme Corp publicly announced its acquisition of GlobalTech for $2.5 billion.",
                source_jurisdiction="SG",
                destination_jurisdiction="SG",
                entity_id="Acme Corp",
                include_suggestions=False,
                document_type="generic",
                review_profile="audit_grade",
            )

        self.assertEqual(ctx.exception.layer, "public_evidence")

    def test_public_evidence_error_status_fails_closed(self):
        class ErrorPublicEvidence:
            def retrieve(self, **kwargs):
                return {
                    "status": "error",
                    "detail": "provider timeout",
                    "privacy_ledger": [],
                }

        engine = PreSendReviewEngine(public_evidence_retriever=ErrorPublicEvidence())
        with self.assertRaises(ReviewLayerError) as ctx:
            engine.review(
                text="Acme Corp publicly announced its acquisition of GlobalTech for $2.5 billion.",
                source_jurisdiction="SG",
                destination_jurisdiction="SG",
                entity_id="Acme Corp",
                include_suggestions=False,
                document_type="generic",
                review_profile="audit_grade",
            )

        self.assertEqual(ctx.exception.layer, "public_evidence")

    def test_public_evidence_missing_key_status_fails_closed(self):
        class MissingKeyPublicEvidence:
            def retrieve(self, **kwargs):
                return {
                    "status": "skipped",
                    "detail": "EXA_API_KEY is not configured",
                    "privacy_ledger": [],
                }

        engine = PreSendReviewEngine(public_evidence_retriever=MissingKeyPublicEvidence())
        with self.assertRaises(ReviewLayerError) as ctx:
            engine.review(
                text="Acme Corp publicly announced its acquisition of GlobalTech for $2.5 billion.",
                source_jurisdiction="SG",
                destination_jurisdiction="SG",
                entity_id="Acme Corp",
                include_suggestions=False,
                document_type="generic",
                review_profile="audit_grade",
            )

        self.assertEqual(ctx.exception.layer, "public_evidence")

    def test_llm_adjudicator_failure_fails_closed(self):
        class FailingLLM:
            def adjudicate(self, **kwargs):
                raise RuntimeError("llm down")

        engine = PreSendReviewEngine(llm_adjudicator=FailingLLM())
        with self.assertRaises(ReviewLayerError) as ctx:
            engine.review(
                text="Acme Corp publicly announced its acquisition of GlobalTech for $2.5 billion.",
                source_jurisdiction="SG",
                destination_jurisdiction="SG",
                entity_id="Acme Corp",
                include_suggestions=False,
                document_type="generic",
                review_profile="audit_grade",
            )

        self.assertEqual(ctx.exception.layer, "llm_adjudicator")

    def test_llm_adjudicator_error_status_fails_closed(self):
        class ErrorLLM:
            def adjudicate(self, **kwargs):
                return {
                    "status": "error",
                    "review_recommendation": "llm provider timeout",
                }

        engine = PreSendReviewEngine(llm_adjudicator=ErrorLLM())
        with self.assertRaises(ReviewLayerError) as ctx:
            engine.review(
                text="Acme Corp publicly announced its acquisition of GlobalTech for $2.5 billion.",
                source_jurisdiction="SG",
                destination_jurisdiction="SG",
                entity_id="Acme Corp",
                include_suggestions=False,
                document_type="generic",
                review_profile="audit_grade",
            )

        self.assertEqual(ctx.exception.layer, "llm_adjudicator")


class ProfileValidationTests(unittest.TestCase):
    def test_unknown_profile_raises(self):
        engine = PreSendReviewEngine()
        with self.assertRaises(ValueError):
            engine.review(
                text="x", source_jurisdiction="SG", destination_jurisdiction="SG",
                entity_id=None, include_suggestions=False, document_type="generic",
                review_profile="paranoid",  # not valid
            )


if __name__ == "__main__":
    unittest.main()
