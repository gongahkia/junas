"""Cross-document defined-term inheritance: a SPA's `the "Purchaser"` definition carries
into a later /review call on a paired disclosure schedule when both share a session_id.

Two scopes covered:
1. Module-level store: load → add → load round-trip + validation of session_id format.
2. Engine integration: doc A defines "Purchaser", doc B (no defined-terms block) reviewed
   in the same session does NOT flag "Mr Purchaser" — because the inherited defined-term
   set suppresses it.
"""

import importlib
import os
import tempfile
import unittest

from junas.review import session_store
from junas.review.engine import PreSendReviewEngine, ReviewLayerError


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["JUNAS_JOURNAL_DIR"] = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()
        os.environ.pop("JUNAS_JOURNAL_DIR", None)

    def test_round_trip_load_after_add(self):
        merged = session_store.add_defined_terms("sess-1", {"Purchaser", "Vendor"})
        self.assertEqual(merged, {"purchaser", "vendor"})
        loaded = session_store.load_defined_terms("sess-1")
        self.assertEqual(loaded, {"purchaser", "vendor"})

    def test_add_is_idempotent(self):
        session_store.add_defined_terms("sess-2", {"Purchaser"})
        merged = session_store.add_defined_terms("sess-2", {"Purchaser", "Company"})
        self.assertEqual(merged, {"purchaser", "company"})

    def test_load_unknown_session_returns_empty(self):
        self.assertEqual(session_store.load_defined_terms("never-existed"), set())

    def test_corrupt_session_sidecar_raises(self):
        path = session_store.session_path("sess-corrupt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not-json", encoding="utf-8")
        with self.assertRaises(session_store.SessionStoreError):
            session_store.load_defined_terms("sess-corrupt")

    def test_invalid_session_id_raises(self):
        for bad in ("with space", "with/slash", "", "x" * 200, "../escape"):
            with self.assertRaises(ValueError, msg=f"expected reject for {bad!r}"):
                session_store.session_path(bad)


class EngineSessionInheritanceTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["JUNAS_JOURNAL_DIR"] = self._tmpdir.name
        importlib.reload(session_store)
        self.engine = PreSendReviewEngine()

    def tearDown(self):
        self._tmpdir.cleanup()
        os.environ.pop("JUNAS_JOURNAL_DIR", None)

    def test_paired_documents_share_defined_terms(self):
        # doc A introduces "Purchaser" as a defined term — engine suppresses it within A.
        doc_a = 'This Share Purchase Agreement (the "SPA") names Globex Pte. Ltd. (the "Purchaser").'
        result_a = self.engine.review(
            text=doc_a, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="SPA",
            session_id="deal-atlas-2026",
        )
        # confirm "Purchaser" is not surfaced as named_person in doc A
        names_a = {f.matched_text for f in result_a.findings if f.rule == "named_person"}
        self.assertNotIn("Purchaser", names_a)

        # doc B has NO defined-terms block of its own. Without inheritance, "Mr Purchaser"
        # (defined-term used as a quasi-honorific) would fire as named_person via NAME_RE.
        doc_b = "Mr Purchaser shall execute the disclosure schedule alongside Dr Jane Tan."
        result_b = self.engine.review(
            text=doc_b, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
            session_id="deal-atlas-2026",
        )
        names_b = {f.matched_text for f in result_b.findings if f.rule == "named_person"}
        self.assertNotIn("Mr Purchaser", names_b,
                         f"expected inherited defined term to suppress 'Mr Purchaser'; got {names_b}")
        # but Dr Jane Tan still fires — inheritance suppresses defined terms only
        self.assertIn("Dr Jane Tan", names_b)

    def test_corrupt_session_sidecar_fails_closed_in_engine(self):
        path = session_store.session_path("deal-corrupt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not-json", encoding="utf-8")
        with self.assertRaises(ReviewLayerError) as ctx:
            self.engine.review(
                text="Dr Jane Tan signs.",
                source_jurisdiction="SG",
                destination_jurisdiction="SG",
                entity_id=None,
                include_suggestions=False,
                document_type="generic",
                session_id="deal-corrupt",
            )
        self.assertEqual(ctx.exception.layer, "session_defined_terms")

    def test_no_session_means_no_inheritance(self):
        doc_a = 'This Agreement (the "Purchaser") names Globex.'
        self.engine.review(
            text=doc_a, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="SPA",
            session_id="deal-bravo-2026",
        )
        doc_b = "Mr Purchaser shall execute."
        # different session_id (or None) means doc_b sees no inherited terms
        result_b = self.engine.review(
            text=doc_b, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
            session_id=None,
        )
        names_b = {f.matched_text for f in result_b.findings if f.rule == "named_person"}
        self.assertIn("Mr Purchaser", names_b)


if __name__ == "__main__":
    unittest.main()
