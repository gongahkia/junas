"""Item 36: public-status proof states on MNPI findings.

Five guarantees:
1. PII findings always carry source_verification=not_checked.
2. Strict-profile MNPI with public-language only (no URL) does NOT soften — severity stays
   medium and source_verification stays not_checked. Item 36's core invariant.
3. Strict-profile MNPI with public-language + in-document http(s) URL softens to low and
   flips source_verification to public_source_matched.
4. Audit-grade with retriever returning sources → MNPI findings flip to public_source_matched.
5. Audit-grade with retriever returning queried+empty → MNPI findings flip to
   no_public_source_found.
"""

import unittest

from kaypoh.review.engine import (
    PreSendReviewEngine,
    SOURCE_VERIFICATION_AMBIGUOUS,
    SOURCE_VERIFICATION_NOT_CHECKED,
    SOURCE_VERIFICATION_NO_PUBLIC_SOURCE_FOUND,
    SOURCE_VERIFICATION_PUBLIC_SOURCE_MATCHED,
)


class _RetrieverWithSources:
    def retrieve(self, *, text, entity_id=None, lexicon=None):
        return {
            "status": "queried",
            "provider": "exa",
            "sources": [{"title": "Acme acquisition", "url": "https://example.com/x"}],
            "privacy_ledger": [],
        }


class _RetrieverNoSources:
    def retrieve(self, *, text, entity_id=None, lexicon=None):
        return {
            "status": "queried",
            "provider": "exa",
            "sources": [],
            "privacy_ledger": [],
        }


class _RetrieverWithHKMarketSource:
    def retrieve(self, *, text, entity_id=None, lexicon=None):
        return {
            "status": "queried",
            "provider": "exa",
            "sources": [{"title": "Inside information announcement", "url": "https://www.hkexnews.hk/x"}],
            "privacy_ledger": [],
        }


class SourceVerificationTests(unittest.TestCase):
    def test_pii_findings_always_not_checked(self):
        engine = PreSendReviewEngine()
        text = "Contact Dr Jane Tan at jane@example.com about NRIC S1234567D."
        result = engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
            review_profile="strict",
        )
        pii = [f for f in result.findings if f.category == "PII"]
        self.assertGreater(len(pii), 0, "expected PII findings for fixture")
        for f in pii:
            self.assertEqual(f.source_verification, SOURCE_VERIFICATION_NOT_CHECKED)

    def test_strict_material_event_public_phrasing_only_stays_medium(self):
        # item 36 core invariant: "publicly announced" alone must NOT soften severity.
        engine = PreSendReviewEngine()
        text = "Acme Corp publicly announced its acquisition of GlobalTech for $2.5 billion."
        result = engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
            review_profile="strict",
        )
        material = [f for f in result.findings if f.rule == "material_event"]
        self.assertEqual(len(material), 1)
        self.assertEqual(material[0].severity, "medium")
        self.assertEqual(material[0].source_verification, SOURCE_VERIFICATION_NOT_CHECKED)

    def test_strict_material_event_with_indoc_url_softens_to_low(self):
        # item 36 carve-out: "document itself contains a citable public source reference".
        engine = PreSendReviewEngine()
        text = (
            "Acme Corp publicly announced its acquisition of GlobalTech for $2.5 billion "
            "(see https://acme.example.com/press/01)."
        )
        result = engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
            review_profile="strict",
        )
        material = [f for f in result.findings if f.rule == "material_event"]
        self.assertEqual(len(material), 1)
        self.assertEqual(material[0].severity, "low")
        self.assertEqual(
            material[0].source_verification, SOURCE_VERIFICATION_PUBLIC_SOURCE_MATCHED
        )

    def test_audit_grade_retriever_match_flips_to_public_source_matched(self):
        engine = PreSendReviewEngine(public_evidence_retriever=_RetrieverWithSources())
        text = "Acme Corp publicly announced its acquisition of GlobalTech for $2.5 billion."
        result = engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id="Acme Corp", include_suggestions=False, document_type="generic",
            review_profile="audit_grade",
        )
        # the deterministic-engine PUBLIC_RE softener no longer fires without a URL, so the
        # doc lands in the ambiguous band and retrieval engages.
        mnpi = [f for f in result.findings if f.category == "MNPI"]
        self.assertGreater(len(mnpi), 0)
        for f in mnpi:
            self.assertEqual(
                f.source_verification, SOURCE_VERIFICATION_PUBLIC_SOURCE_MATCHED,
                f"{f.rule} should have flipped",
            )

    def test_audit_grade_retriever_empty_flips_to_no_public_source_found(self):
        engine = PreSendReviewEngine(public_evidence_retriever=_RetrieverNoSources())
        text = "Acme Corp publicly announced its acquisition of GlobalTech for $2.5 billion."
        result = engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id="Acme Corp", include_suggestions=False, document_type="generic",
            review_profile="audit_grade",
        )
        mnpi = [f for f in result.findings if f.category == "MNPI"]
        self.assertGreater(len(mnpi), 0)
        for f in mnpi:
            self.assertEqual(
                f.source_verification, SOURCE_VERIFICATION_NO_PUBLIC_SOURCE_FOUND,
                f"{f.rule} should reflect retriever miss",
            )

    def test_hk_generic_web_source_is_ambiguous_not_market_known(self):
        engine = PreSendReviewEngine(public_evidence_retriever=_RetrieverWithSources())
        text = "Acme Corp publicly announced its acquisition of GlobalTech for $2.5 billion."
        result = engine.review(
            text=text, source_jurisdiction="HK", destination_jurisdiction="HK",
            entity_id="Acme Corp", include_suggestions=False, document_type="generic",
            review_profile="audit_grade",
        )
        mnpi = [f for f in result.findings if f.category == "MNPI"]
        self.assertGreater(len(mnpi), 0)
        for f in mnpi:
            self.assertEqual(f.source_verification, SOURCE_VERIFICATION_AMBIGUOUS)
            self.assertEqual(f.metadata.get("hk_public_status"), "available_but_not_generally_known")

    def test_hk_market_source_flips_to_public_source_matched(self):
        engine = PreSendReviewEngine(public_evidence_retriever=_RetrieverWithHKMarketSource())
        text = "Acme Corp publicly announced its acquisition of GlobalTech for $2.5 billion."
        result = engine.review(
            text=text, source_jurisdiction="HK", destination_jurisdiction="HK",
            entity_id="Acme Corp", include_suggestions=False, document_type="generic",
            review_profile="audit_grade",
        )
        mnpi = [f for f in result.findings if f.category == "MNPI"]
        self.assertGreater(len(mnpi), 0)
        for f in mnpi:
            self.assertEqual(f.source_verification, SOURCE_VERIFICATION_PUBLIC_SOURCE_MATCHED)
            self.assertNotIn("hk_public_status", f.metadata)

    def test_strict_without_retriever_leaves_mnpi_not_checked(self):
        # no retriever wired, no in-doc URL: even high-severity MNPI must carry not_checked.
        engine = PreSendReviewEngine()
        text = "Confidential acquisition of GlobalTech for $2.5 billion. Material non-public."
        result = engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
            review_profile="strict",
        )
        mnpi = [f for f in result.findings if f.category == "MNPI"]
        self.assertGreater(len(mnpi), 0)
        for f in mnpi:
            self.assertEqual(f.source_verification, SOURCE_VERIFICATION_NOT_CHECKED)


if __name__ == "__main__":
    unittest.main()
