import unittest

from kaypoh.review.entity_linker import canonical_org, canonical_person, strip_honorific


class CanonicalPersonTests(unittest.TestCase):
    def test_strip_honorific_handles_common_titles(self):
        for raw in ["Dr Jane Tan", "Dr. Jane Tan", "Mrs Jane Tan", "Mdm Jane Tan"]:
            self.assertEqual(strip_honorific(raw), "Jane Tan")

    def test_person_variants_collapse_to_same_key(self):
        self.assertEqual(canonical_person("Dr Jane Tan"), canonical_person("Jane Tan"))
        self.assertEqual(canonical_person("Mr. John Lim"), canonical_person("John Lim"))

    def test_person_keeps_distinct_full_names_distinct(self):
        self.assertNotEqual(canonical_person("Jane Tan"), canonical_person("John Lim"))


class CanonicalOrgTests(unittest.TestCase):
    def test_org_variants_collapse_to_same_key(self):
        self.assertEqual(canonical_org("Acme Pte. Ltd."), canonical_org("Acme"))
        self.assertEqual(canonical_org("Acme Limited"), canonical_org("Acme"))
        self.assertEqual(canonical_org("Globex Holdings Pte Ltd"), canonical_org("Globex Holdings"))

    def test_org_keeps_distinct_companies_distinct(self):
        self.assertNotEqual(canonical_org("Acme Pte Ltd"), canonical_org("Globex Pte Ltd"))


class SurnameVariantTests(unittest.TestCase):
    def test_named_person_does_not_cross_line_boundaries(self):
        from kaypoh.review.engine import PreSendReviewEngine

        engine = PreSendReviewEngine()
        text = "Mr. John Tan  \nBlk 789, Jurong East Street 21"
        result = engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="SPA",
        )
        matched = [f.matched_text for f in result.findings if f.rule == "named_person"]
        self.assertIn("Mr. John Tan", matched)
        self.assertNotIn("Mr. John Tan  \nBlk", matched)

    def test_named_person_handles_malay_name_particles(self):
        from kaypoh.review.engine import PreSendReviewEngine

        engine = PreSendReviewEngine()
        text = "Ms. Siti Aishah binti Abdullah briefed the board."
        result = engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="SPA",
        )
        matched = [f.matched_text for f in result.findings if f.rule == "named_person"]
        self.assertIn("Ms. Siti Aishah binti Abdullah", matched)

    def test_surname_only_reference_resolves_after_anchored_honorific(self):
        from kaypoh.review.engine import PreSendReviewEngine

        engine = PreSendReviewEngine()
        text = "Dr Jane Tan met the buyer. Tan confirmed the terms."
        result = engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="SPA",
        )
        matched = [f.matched_text for f in result.findings if f.rule == "named_person"]
        self.assertIn("Dr Jane Tan", matched)
        self.assertIn("Tan", matched)

    def test_surname_only_skips_corporate_suffix_denylist(self):
        from kaypoh.review.engine import PreSendReviewEngine

        engine = PreSendReviewEngine()
        # "Ltd" can be accidentally captured as the trailing token of a NAME_RE match. the
        # surname pass must NOT then fire \bLtd\b across the document.
        text = "Mr Lee Ltd signed. Acme Ltd is the buyer. Globex Ltd is the seller."
        result = engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="SPA",
        )
        ltd_findings = [
            f for f in result.findings if f.rule == "named_person" and f.matched_text == "Ltd"
        ]
        self.assertEqual(ltd_findings, [])

    def test_surname_only_skips_when_defined_term(self):
        from kaypoh.review.engine import PreSendReviewEngine

        engine = PreSendReviewEngine()
        # "Tan" is defined as a contract term — should not collapse to a named_person variant.
        text = 'Dr Jane Tan signed. "Tan" means the trustee. The Tan trust held the shares.'
        result = engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="SPA",
        )
        bare_tan = [
            f for f in result.findings
            if f.rule == "named_person" and f.matched_text == "Tan" and f.start_char != text.index("Dr Jane Tan")
        ]
        self.assertEqual(bare_tan, [])


if __name__ == "__main__":
    unittest.main()
