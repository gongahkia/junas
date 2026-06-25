"""LLM-assisted defined-term extraction (item 6).

Three guarantees:
1. The extractor is called and its output is merged into the defined-term suppression
   set so a non-regex defined-term pattern stops triggering downstream named_person /
   definitive_agreement findings.
2. Results are cached by SHA-256(document text); a second review of the same text
   does NOT re-call the extractor.
3. Engine only calls the extractor when review_profile == "audit_grade".
"""

import importlib
import os
import tempfile
import unittest

from junas.review import llm_defined_terms
from junas.review.engine import PreSendReviewEngine, ReviewLayerError


class DummyExtractor:
    """Returns a fixed list every time it's called, counts calls."""

    def __init__(self, terms=None):
        self.terms = terms or ["the Seller"]
        self.calls = 0

    def extract(self, preamble: str) -> list[str]:
        self.calls += 1
        self.last_preamble = preamble
        return list(self.terms)


class FailingExtractor:
    def __init__(self):
        self.calls = 0

    def extract(self, preamble: str) -> list[str]:
        self.calls += 1
        raise RuntimeError("simulated network error")


class LLMDefinedTermCacheTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["JUNAS_JOURNAL_DIR"] = self._tmpdir.name
        importlib.reload(llm_defined_terms)

    def tearDown(self):
        self._tmpdir.cleanup()
        os.environ.pop("JUNAS_JOURNAL_DIR", None)
        importlib.reload(llm_defined_terms)

    def test_extract_with_cache_returns_casefolded_terms(self):
        extractor = DummyExtractor(["Purchaser", "The Seller"])
        result = llm_defined_terms.extract_with_cache(text="any text", extractor=extractor)
        self.assertEqual(result, {"purchaser", "the seller"})

    def test_second_call_hits_cache_no_re_extraction(self):
        extractor = DummyExtractor(["Foo"])
        text = "doc body"
        llm_defined_terms.extract_with_cache(text=text, extractor=extractor)
        llm_defined_terms.extract_with_cache(text=text, extractor=extractor)
        self.assertEqual(extractor.calls, 1, "second call must be served from cache")

    def test_failing_extractor_returns_empty_set_not_raises(self):
        extractor = FailingExtractor()
        result = llm_defined_terms.extract_with_cache(text="x", extractor=extractor)
        self.assertEqual(result, set())
        self.assertEqual(extractor.calls, 1)

    def test_failing_extractor_raises_when_fail_closed(self):
        extractor = FailingExtractor()
        with self.assertRaises(llm_defined_terms.LLMDefinedTermError):
            llm_defined_terms.extract_with_cache(text="x", extractor=extractor, fail_closed=True)
        self.assertEqual(extractor.calls, 1)

    def test_malformed_extractor_output_raises_when_fail_closed(self):
        class BadExtractor:
            def extract(self, preamble: str):
                return "Seller"

        with self.assertRaises(llm_defined_terms.LLMDefinedTermError):
            llm_defined_terms.extract_with_cache(text="x", extractor=BadExtractor(), fail_closed=True)

    def test_preamble_is_truncated_to_cap(self):
        long_text = "A" * (llm_defined_terms.PREAMBLE_CHAR_CAP + 5000)
        extractor = DummyExtractor()
        llm_defined_terms.extract_with_cache(text=long_text, extractor=extractor)
        self.assertEqual(len(extractor.last_preamble), llm_defined_terms.PREAMBLE_CHAR_CAP)


class EngineLLMDefinedTermIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["JUNAS_JOURNAL_DIR"] = self._tmpdir.name
        importlib.reload(llm_defined_terms)

    def tearDown(self):
        self._tmpdir.cleanup()
        os.environ.pop("JUNAS_JOURNAL_DIR", None)
        importlib.reload(llm_defined_terms)

    def test_audit_grade_engages_extractor_and_suppresses_named_person(self):
        # "Mr Seller" would normally fire as named_person. LLM extractor returns "Seller"
        # so it gets suppressed (after honorific strip).
        extractor = DummyExtractor(["Seller"])
        engine = PreSendReviewEngine(llm_defined_term_extractor=extractor)
        text = "Mr Seller shall execute the contract."
        result = engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="SPA",
            review_profile="audit_grade",
        )
        self.assertEqual(extractor.calls, 1)
        named = {f.matched_text for f in result.findings if f.rule == "named_person"}
        self.assertNotIn("Mr Seller", named)

    def test_strict_profile_skips_extractor(self):
        extractor = DummyExtractor(["Seller"])
        engine = PreSendReviewEngine(llm_defined_term_extractor=extractor)
        engine.review(
            text="Mr Seller signs.", source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
            review_profile="strict",
        )
        self.assertEqual(extractor.calls, 0, "strict profile must not call the LLM extractor")

    def test_repeat_review_of_same_doc_hits_cache(self):
        extractor = DummyExtractor(["Seller"])
        engine = PreSendReviewEngine(llm_defined_term_extractor=extractor)
        text = "Mr Seller shall execute the contract."
        for _ in range(3):
            engine.review(
                text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
                entity_id=None, include_suggestions=False, document_type="SPA",
                review_profile="audit_grade",
            )
        self.assertEqual(extractor.calls, 1, "calls 2+ must be served from on-disk cache")

    def test_audit_grade_failing_extractor_fails_closed(self):
        extractor = FailingExtractor()
        engine = PreSendReviewEngine(llm_defined_term_extractor=extractor)
        with self.assertRaises(ReviewLayerError) as ctx:
            engine.review(
                text="Mr Seller shall execute the contract.",
                source_jurisdiction="SG",
                destination_jurisdiction="SG",
                entity_id=None,
                include_suggestions=False,
                document_type="SPA",
                review_profile="audit_grade",
            )
        self.assertEqual(ctx.exception.layer, "llm_defined_terms")


if __name__ == "__main__":
    unittest.main()
