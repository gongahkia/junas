"""Matter-scoped defined-term inheritance (item 55).

Matter sits above session: defined terms accumulate at matter level and inherit into every
session within that matter. Closes the M&A real-world case of 30+ docs over weeks across
multiple reviewers — session-scoping was the right v1 but loses inheritance the moment the
review session rotates.

Two scopes covered:
1. Module-level store: load → add → load round-trip + matter_id format + tenant isolation.
2. Engine integration: doc A in matter M1 defines "Purchaser"; doc B reviewed weeks later
   under a different session_id but the same matter_id inherits the term.
"""

import importlib
import os
import tempfile
import unittest

from kaypoh.review import matter_store
from kaypoh.review.engine import PreSendReviewEngine


class MatterStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["KAYPOH_JOURNAL_DIR"] = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()
        os.environ.pop("KAYPOH_JOURNAL_DIR", None)

    def test_round_trip_load_after_add(self):
        merged = matter_store.add_defined_terms("matter-1", {"Purchaser", "Vendor"})
        self.assertEqual(merged, {"purchaser", "vendor"})
        loaded = matter_store.load_defined_terms("matter-1")
        self.assertEqual(loaded, {"purchaser", "vendor"})

    def test_add_is_idempotent(self):
        matter_store.add_defined_terms("matter-2", {"Purchaser"})
        merged = matter_store.add_defined_terms("matter-2", {"Purchaser", "Company"})
        self.assertEqual(merged, {"purchaser", "company"})

    def test_load_unknown_matter_returns_empty(self):
        self.assertEqual(matter_store.load_defined_terms("never-existed"), set())

    def test_dms_vendor_colon_composite_key_allowed(self):
        # iManage / NetDocuments matter IDs are commonly composed as `{vendor}:{id}`.
        merged = matter_store.add_defined_terms("imanage:M-2026-0042", {"SPA"})
        self.assertEqual(merged, {"spa"})

    def test_invalid_matter_id_raises(self):
        for bad in ("with space", "with/slash", "", "x" * 200, "../escape"):
            with self.assertRaises(ValueError, msg=f"expected reject for {bad!r}"):
                matter_store.matter_path(bad)

    def test_tenant_isolation(self):
        matter_store.add_defined_terms("matter-3", {"Purchaser"}, tenant_id="tenant-A")
        self.assertEqual(
            matter_store.load_defined_terms("matter-3", tenant_id="tenant-A"),
            {"purchaser"},
        )
        self.assertEqual(
            matter_store.load_defined_terms("matter-3", tenant_id="tenant-B"), set()
        )


class EngineMatterInheritanceTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["KAYPOH_JOURNAL_DIR"] = self._tmpdir.name
        importlib.reload(matter_store)
        self.engine = PreSendReviewEngine()

    def tearDown(self):
        self._tmpdir.cleanup()
        os.environ.pop("KAYPOH_JOURNAL_DIR", None)

    def test_matter_inheritance_across_sessions(self):
        # doc A: matter M1 / session S1 — defines "Purchaser"
        doc_a = 'Globex Pte. Ltd. (the "Purchaser") agrees to acquire Target Pte. Ltd. (the "Vendor").'
        self.engine.review(
            text=doc_a, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="SPA",
            session_id="S1", matter_id="M1",
        )
        # confirm matter store now holds the term
        self.assertIn("purchaser", matter_store.load_defined_terms("M1"))
        self.assertIn("vendor", matter_store.load_defined_terms("M1"))

        # doc B: matter M1 / session S2 (different session) — Purchaser still suppressed
        doc_b = "Mr Purchaser shall execute the disclosure schedule alongside Dr Jane Tan."
        result_b = self.engine.review(
            text=doc_b, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
            session_id="S2", matter_id="M1",
        )
        names_b = {f.matched_text for f in result_b.findings if f.rule == "named_person"}
        self.assertNotIn("Mr Purchaser", names_b,
                         f"expected matter-inherited defined term to suppress; got {names_b}")
        self.assertIn("Dr Jane Tan", names_b)

    def test_no_matter_means_no_inheritance(self):
        doc_a = 'Acme Pte. Ltd. (the "Purchaser") signs the SPA.'
        self.engine.review(
            text=doc_a, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="SPA",
            matter_id="MX",
        )
        # doc_b reviewed with NO matter_id should see no inheritance
        doc_b = "Mr Purchaser shall execute."
        result_b = self.engine.review(
            text=doc_b, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
        )
        names_b = {f.matched_text for f in result_b.findings if f.rule == "named_person"}
        self.assertIn("Mr Purchaser", names_b)

    def test_matter_inheritance_persists_across_engine_instances(self):
        # the real-world case: reviewer 1 reviews doc A today; reviewer 2 reviews doc B
        # next week with a fresh engine instance. Matter store carries the inheritance.
        engine_1 = PreSendReviewEngine()
        engine_2 = PreSendReviewEngine()
        doc_a = 'Globex (the "Purchaser") signs the SPA.'
        engine_1.review(
            text=doc_a, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="SPA",
            matter_id="MZ",
        )
        doc_b = "Mr Purchaser executes the closing certificate."
        result_b = engine_2.review(
            text=doc_b, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
            matter_id="MZ",
        )
        names_b = {f.matched_text for f in result_b.findings if f.rule == "named_person"}
        self.assertNotIn("Mr Purchaser", names_b)


if __name__ == "__main__":
    unittest.main()
