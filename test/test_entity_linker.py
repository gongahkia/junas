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


if __name__ == "__main__":
    unittest.main()
