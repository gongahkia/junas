"""Jurisdiction-age-cliff minors detector (item 107).

Single rule `minor_data_reference` with per-jurisdiction-resolved severity from
_MINOR_AGE_CLIFFS. Age cliffs verified against statute text 2026-05-27:
  - DPDPA India 2023 s2(f) + s9: <18
  - PDPC SG Advisory Guidelines on Children's Personal Data (Mar 2024): <18
  - UK ICO Age-Appropriate Design Code: <18
  - AU OAIC Children's Online Privacy Code (2026 consultation; due Dec 2026): <18
  - HK PCPD Minors Guidance Note: <18
  - UAE PDPL via Wadeema Law / KSA PDPL via Child Protection Law: <18
  - GDPR Art 8: default <16 (member states may lower to 13)
  - PIPL China Art 31: <14
  - COPPA US 16 CFR Part 312: <13
"""

import unittest

from junas.review.engine import PreSendReviewEngine


class MinorDataReferenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _fires(self, text, source="SG", dest="SG"):
        r = self.engine.review(
            text=text, source_jurisdiction=source, destination_jurisdiction=dest,
            entity_id=None, include_suggestions=False,
        )
        return [f for f in r.findings if f.rule == "minor_data_reference"]

    # --- IN DPDPA cliff <18 ---
    def test_in_age_14_fires_high(self):
        f = self._fires("The student is aged 14 and her data is stored.", source="IN", dest="IN")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")
        self.assertIn("IN (<18)", f[0].reason)

    def test_in_age_17_still_fires_under_18_cliff(self):
        f = self._fires("Profile for 17-year-old user.", source="IN", dest="IN")
        self.assertTrue(any(fx.severity == "high" for fx in f))

    def test_in_age_19_does_not_fire(self):
        # 19 > 18 cliff → adult, no fire
        f = self._fires("User aged 19 has consented.", source="IN", dest="IN")
        self.assertEqual(len(f), 0)

    # --- EU GDPR cliff <16 ---
    def test_eu_age_12_fires(self):
        f = self._fires("Child profile age 12 with parental consent.", source="EU", dest="EU")
        self.assertTrue(len(f) >= 1)
        self.assertTrue(any(fx.severity == "high" for fx in f))

    def test_eu_age_17_does_not_fire(self):
        # 17 > 16 EU cliff → adult under GDPR Art 8
        f = self._fires("User aged 17 has consented.", source="EU", dest="EU")
        self.assertEqual(len(f), 0)

    # --- CN PIPL cliff <14 ---
    def test_cn_age_13_fires(self):
        f = self._fires("Minor aged 13 requires guardian consent.", source="CN", dest="CN")
        self.assertTrue(any("CN (<14)" in fx.reason for fx in f))

    def test_cn_age_15_does_not_fire(self):
        f = self._fires("User aged 15 has consented.", source="CN", dest="CN")
        self.assertEqual(len(f), 0)

    # --- US COPPA cliff <13 ---
    def test_us_age_11_fires(self):
        f = self._fires("Verifiable parental consent obtained for 11-year-old.", source="US", dest="US")
        self.assertTrue(len(f) >= 1)

    def test_us_age_14_does_not_fire_under_coppa(self):
        f = self._fires("User aged 14 has consented.", source="US", dest="US")
        self.assertEqual(len(f), 0)

    # --- school-grade markers ---
    def test_sg_primary_4_fires(self):
        f = self._fires("Primary 4 student roster attached.", source="SG", dest="SG")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")

    def test_uk_year_7_with_student_context(self):
        f = self._fires("Year 7 student attendance records.", source="UK", dest="UK")
        self.assertTrue(len(f) >= 1)

    def test_us_5th_grade_fires(self):
        f = self._fires("5th grade student profile updated.", source="US", dest="US")
        self.assertTrue(len(f) >= 1)

    def test_kindergarten_with_school_context(self):
        f = self._fires("Kindergarten enrolment list received.", source="SG", dest="SG")
        self.assertTrue(len(f) >= 1)

    # --- verifiable parental consent markers ---
    def test_vpc_marker(self):
        f = self._fires("Verifiable parental consent obtained.", source="US", dest="US")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")

    def test_guardian_consent_marker(self):
        f = self._fires("Guardian consent on file.", source="IN", dest="IN")
        self.assertEqual(len(f), 1)

    # --- minor lexicon with data marker ---
    def test_minor_personal_data(self):
        f = self._fires("Minor's personal data was processed.", source="SG", dest="SG")
        self.assertTrue(len(f) >= 1)

    def test_data_of_minors_fires(self):
        f = self._fires("Personal data of minors was collected.", source="EU", dest="EU")
        self.assertTrue(len(f) >= 1)

    def test_au_child_online_activity_fires(self):
        f = self._fires("Children's online activity is logged by the app.", source="AU", dest="AU")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")

    def test_au_age_assurance_for_online_service_users_fires(self):
        f = self._fires("Age assurance for online service users is being deployed.", source="AU", dest="AU")
        self.assertEqual(len(f), 1)

    def test_in_behavioural_monitoring_of_children_fires(self):
        f = self._fires("Behavioural monitoring of children is disabled pending review.", source="IN", dest="IN")
        self.assertEqual(len(f), 1)
        self.assertIn("IN (<18)", f[0].reason)

    def test_in_targeted_ads_to_children_fires(self):
        f = self._fires("Targeted advertisements directed at children were blocked.", source="IN", dest="IN")
        self.assertEqual(len(f), 1)

    # --- false-positive guards ---
    def test_18_plus_years_experience_does_not_fire(self):
        f = self._fires("Candidate with 18+ years of experience.", source="SG", dest="SG")
        self.assertEqual(len(f), 0)

    def test_year_n_of_contract_does_not_fire(self):
        f = self._fires("In Year 7 of the lease agreement, payments commence.", source="SG", dest="SG")
        self.assertEqual(len(f), 0)

    def test_year_n_of_term_does_not_fire(self):
        f = self._fires("Year 5 of the contract term begins next month.", source="SG", dest="SG")
        self.assertEqual(len(f), 0)

    def test_grade_a_rating_does_not_fire(self):
        # plain "Grade A" rating without school-context should not fire
        f = self._fires("Asset rated Grade A by the auditor.", source="SG", dest="SG")
        self.assertEqual(len(f), 0)

    def test_25_years_old_does_not_fire(self):
        f = self._fires("User aged 25 has consented.", source="EU", dest="EU")
        self.assertEqual(len(f), 0)

    def test_29_year_old_does_not_fire(self):
        f = self._fires("A 29-year-old marketing intern queried the IR page.", source="SG", dest="SG")
        self.assertEqual(len(f), 0)

    def test_generic_age_assurance_training_does_not_fire(self):
        f = self._fires("Age Assurance Framework training is scheduled for compliance staff.", source="AU", dest="AU")
        self.assertEqual(len(f), 0)

    # --- cross-jurisdiction routing ---
    def test_strictest_juris_wins(self):
        # source SG (cliff 18) + dest CN (cliff 14): age 16 → falls under SG only → high
        f = self._fires("Minor aged 16 requires consent.", source="SG", dest="CN")
        self.assertTrue(any("SG (<18)" in fx.reason for fx in f))

    # --- citation wiring ---
    def test_citation_includes_dpdpa_s9(self):
        from junas.review.citations import pii_rationale
        rationale = pii_rationale(rule="minor_data_reference", jurisdiction="IN", matched_text="aged 14")
        self.assertIn("DPDPA India 2023 s2(f) + s9", rationale)

    def test_citation_includes_coppa(self):
        from junas.review.citations import pii_rationale
        rationale = pii_rationale(rule="minor_data_reference", jurisdiction="US", matched_text="11-year-old")
        self.assertIn("COPPA", rationale)


if __name__ == "__main__":
    unittest.main()
