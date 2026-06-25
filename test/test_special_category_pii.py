"""Special-category PII v1 seed (item 98): religion / trade-union / political.

Strict context anchors keep precision survivable. False-positive corpus covers proper-name
colliders ("Christian Dior", "Hindu Kush"), place-name colliders ("Trade Union Square",
"Union Pacific"), and legal/court usage ("the opposition argued", "ruling party of the
contract"). Per-category opt-out via JUNAS_SPECIAL_CATEGORY_DISABLE.
"""

import os
import unittest

from junas.review.engine import PreSendReviewEngine


class _BaseSpecialCategoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _findings_for(self, text, rule, source="SG", dest="SG"):
        r = self.engine.review(
            text=text, source_jurisdiction=source, destination_jurisdiction=dest,
            entity_id=None, include_suggestions=False,
        )
        return [f for f in r.findings if f.rule == rule]


class ReligiousBeliefTests(_BaseSpecialCategoryTests):
    def test_devout_muslim_with_honorific(self):
        f = self._findings_for("Dr Jane Tan is a devout Muslim.", "religious_belief")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")

    def test_attends_mosque(self):
        self.assertEqual(len(self._findings_for("He attends the mosque every Friday.", "religious_belief")), 1)

    def test_attends_temple(self):
        self.assertEqual(len(self._findings_for("She worships at the temple.", "religious_belief")), 1)

    def test_member_of_buddhist_community(self):
        self.assertEqual(
            len(self._findings_for("Members of the Buddhist community gathered.", "religious_belief")), 1
        )

    def test_explicit_faith_assignment(self):
        self.assertEqual(len(self._findings_for("Religion: Hindu", "religious_belief")), 1)

    def test_christian_dior_does_not_fire(self):
        self.assertEqual(len(self._findings_for("Christian Dior limited edition bag.", "religious_belief")), 0)

    def test_hindu_kush_geography_does_not_fire(self):
        self.assertEqual(len(self._findings_for("The Hindu Kush mountains border Afghanistan.", "religious_belief")), 0)

    def test_buddhist_art_history_does_not_fire(self):
        self.assertEqual(len(self._findings_for("Buddhist art history paper submitted.", "religious_belief")), 0)

    def test_atheist_with_marker(self):
        self.assertEqual(len(self._findings_for("Mr Tan identifies as atheist.", "religious_belief")), 1)


class TradeUnionMembershipTests(_BaseSpecialCategoryTests):
    def test_joined_ntuc(self):
        f = self._findings_for("Mr Tan joined the NTUC last year.", "trade_union_membership")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")

    def test_member_of_trade_union(self):
        self.assertEqual(len(self._findings_for("She is a member of the trade union.", "trade_union_membership")), 1)

    def test_shop_steward_role(self):
        self.assertEqual(len(self._findings_for("Acting as shop steward for the unit.", "trade_union_membership")), 1)

    def test_collective_bargaining_agreement(self):
        self.assertEqual(
            len(self._findings_for("Collective bargaining agreement signed.", "trade_union_membership")), 1
        )

    def test_picket_line(self):
        self.assertEqual(len(self._findings_for("Workers crossed the picket line.", "trade_union_membership")), 1)

    def test_trade_union_square_does_not_fire(self):
        self.assertEqual(
            len(self._findings_for("Meeting at Trade Union Square at 9am.", "trade_union_membership")), 0
        )

    def test_union_pacific_railway_does_not_fire(self):
        self.assertEqual(
            len(self._findings_for("Union Pacific Railway annual report.", "trade_union_membership")), 0
        )

    def test_afl_premiership_does_not_fire(self):
        self.assertEqual(
            len(self._findings_for("AFL Premiership winners announced.", "trade_union_membership")), 0
        )


class PoliticalOpinionTests(_BaseSpecialCategoryTests):
    def test_member_of_pap(self):
        f = self._findings_for("Ms Lee is a member of the PAP.", "political_opinion")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")

    def test_donated_to_party(self):
        self.assertEqual(
            len(
                self._findings_for(
                    "She donated to the Democratic Party.", "political_opinion", source="US", dest="US"
                )
            ),
            1,
        )

    def test_voted_for_party(self):
        self.assertEqual(
            len(
                self._findings_for(
                    "He voted for Labour in the last election.", "political_opinion", source="UK", dest="UK"
                )
            ),
            1,
        )

    def test_party_affiliation_explicit(self):
        self.assertEqual(
            len(self._findings_for("Party affiliation: BJP", "political_opinion", source="IN", dest="IN")), 1
        )

    def test_the_opposition_argued_court_usage_does_not_fire(self):
        # "the opposition argued" without party-name suffix should not fire
        self.assertEqual(
            len(
                self._findings_for(
                    "The opposition argued in court yesterday.", "political_opinion", source="UK", dest="UK"
                )
            ),
            0,
        )

    def test_independent_counsel_does_not_fire(self):
        # "Independent counsel" — adjective usage, not party affiliation
        self.assertEqual(
            len(self._findings_for("Independent counsel filed a report.", "political_opinion", source="US", dest="US")),
            0,
        )


class RacialEthnicOriginTests(_BaseSpecialCategoryTests):
    def test_explicit_ethnicity_field(self):
        f = self._findings_for("Ethnicity: Han Chinese.", "racial_ethnic_origin")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")

    def test_named_subject_ethnic_origin(self):
        self.assertEqual(len(self._findings_for("Ms Lee is ethnically Malay.", "racial_ethnic_origin")), 1)

    def test_mandarin_ethnicity_field(self):
        self.assertEqual(len(self._findings_for("民族: 维吾尔族.", "racial_ethnic_origin", source="CN", dest="CN")), 1)

    def test_arabic_ethnicity_field(self):
        self.assertEqual(
            len(self._findings_for("الأصل العرقي: عربي.", "racial_ethnic_origin", source="AE", dest="AE")),
            1,
        )

    def test_bait_contexts_do_not_fire(self):
        for text in [
            "The race to sign the SPA continues.",
            "Black-letter law memo attached.",
            "The Asian option pricing model was reviewed.",
            "We do not collect ethnicity data in this process.",
        ]:
            with self.subTest(text=text):
                self.assertEqual(len(self._findings_for(text, "racial_ethnic_origin")), 0)


class HealthConditionTests(_BaseSpecialCategoryTests):
    def test_diagnosed_condition_with_honorific(self):
        f = self._findings_for("Ms Lee was diagnosed with type 2 diabetes.", "health_condition")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")

    def test_explicit_diagnosis_field(self):
        self.assertEqual(len(self._findings_for("Diagnosis: chronic kidney disease.", "health_condition")), 1)

    def test_hiv_positive(self):
        self.assertEqual(len(self._findings_for("Mr Tan tested positive for HIV.", "health_condition")), 1)

    def test_icd_code_requires_medical_anchor(self):
        self.assertEqual(len(self._findings_for("Diagnosis code: E11.9", "health_condition")), 1)
        self.assertEqual(
            len(self._findings_for("The file reference is E11.9 in the bundle.", "health_condition")),
            0,
        )

    def test_generic_wellness_context_does_not_fire(self):
        self.assertEqual(
            len(self._findings_for("The wellness seminar mentioned diabetes prevention.", "health_condition")),
            0,
        )

    def test_cancer_charity_context_does_not_fire(self):
        self.assertEqual(len(self._findings_for("The company donated to a cancer charity.", "health_condition")), 0)

    def test_mandarin_and_arabic_health_fields_fire(self):
        self.assertEqual(len(self._findings_for("诊断: 糖尿病.", "health_condition", source="CN", dest="CN")), 1)
        self.assertEqual(len(self._findings_for("التشخيص: السكري.", "health_condition", source="AE", dest="AE")), 1)


class MultilingualSpecialCategoryExpansionTests(_BaseSpecialCategoryTests):
    def test_mandarin_trade_union_political_treatment_sexual_fields_fire(self):
        samples = [
            ("工会会员: 张伟.", "trade_union_membership"),
            ("政治观点: 支持民主党.", "political_opinion"),
            ("用药: 二甲双胍.", "medical_treatment"),
            ("性取向: 双性恋.", "sexual_orientation"),
            ("性生活: 已披露避孕使用.", "sex_life_reference"),
        ]
        for text, rule in samples:
            with self.subTest(rule=rule):
                self.assertEqual(len(self._findings_for(text, rule, source="CN", dest="CN")), 1)

    def test_arabic_trade_union_political_treatment_sexual_fields_fire(self):
        samples = [
            ("عضو نقابة: نعم.", "trade_union_membership"),
            ("الانتماء السياسي: عضو حزب.", "political_opinion"),
            ("العلاج: إنسولين.", "medical_treatment"),
            ("الميول الجنسية: مثلي.", "sexual_orientation"),
            ("التاريخ الجنسي: تم الإفصاح عنه.", "sex_life_reference"),
        ]
        for text, rule in samples:
            with self.subTest(rule=rule):
                self.assertEqual(len(self._findings_for(text, rule, source="AE", dest="AE")), 1)

    def test_japanese_and_korean_sensitive_pi_fields_fire(self):
        samples = [
            ("労働組合員: 山田太郎.", "trade_union_membership", "JP"),
            ("支持政党: 労働党.", "political_opinion", "JP"),
            ("診断: 糖尿病.", "health_condition", "JP"),
            ("服薬: インスリン.", "medical_treatment", "JP"),
            ("遺伝子検査結果: BRCA1 陽性.", "genetic_data", "JP"),
            ("性的指向: 同性愛.", "sexual_orientation", "JP"),
            ("노동조합원: 김민수.", "trade_union_membership", "KR"),
            ("정당 소속: 녹색당.", "political_opinion", "KR"),
            ("진단: 당뇨병.", "health_condition", "KR"),
            ("복용약: 인슐린.", "medical_treatment", "KR"),
            ("유전자 검사 결과: BRCA2 양성.", "genetic_data", "KR"),
            ("성적 지향: 동성애.", "sexual_orientation", "KR"),
        ]
        for text, rule, jurisdiction in samples:
            with self.subTest(text=text, rule=rule):
                self.assertEqual(len(self._findings_for(text, rule, source=jurisdiction, dest=jurisdiction)), 1)

    def test_multilingual_category_labels_without_values_do_not_fire(self):
        samples = [
            ("政治观点:", "political_opinion", "CN"),
            ("性取向:", "sexual_orientation", "CN"),
            ("الميول الجنسية:", "sexual_orientation", "AE"),
            ("التاريخ الجنسي:", "sex_life_reference", "AE"),
            ("支持政党:", "political_opinion", "JP"),
            ("성적 지향:", "sexual_orientation", "KR"),
        ]
        for text, rule, jurisdiction in samples:
            with self.subTest(text=text):
                self.assertEqual(len(self._findings_for(text, rule, source=jurisdiction, dest=jurisdiction)), 0)


class MedicalTreatmentTests(_BaseSpecialCategoryTests):
    def test_prescribed_medication_with_honorific(self):
        f = self._findings_for("Mr Lim is prescribed metformin.", "medical_treatment")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")

    def test_explicit_medication_field(self):
        self.assertEqual(len(self._findings_for("Medication: sertraline.", "medical_treatment")), 1)

    def test_procedure_treatment_marker(self):
        self.assertEqual(len(self._findings_for("The patient was scheduled for chemotherapy.", "medical_treatment")), 1)

    def test_unanchored_drug_market_context_does_not_fire(self):
        self.assertEqual(len(self._findings_for("The metformin market study was circulated.", "medical_treatment")), 0)

    def test_general_surgery_metaphor_does_not_fire(self):
        self.assertEqual(
            len(self._findings_for("The restructuring required financial surgery.", "medical_treatment")),
            0,
        )


class BiometricIdentifierTests(_BaseSpecialCategoryTests):
    def test_biometric_template(self):
        f = self._findings_for("Biometric template: fingerprint hash.", "biometric_identifier")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")

    def test_biometric_authentication_phrase_alone_does_not_fire(self):
        self.assertEqual(
            len(self._findings_for("The phrase biometric authentication appears in the security standard.",
                                   "biometric_identifier")),
            0,
        )

    def test_biometric_authentication_with_specific_template_still_fires(self):
        self.assertEqual(
            len(self._findings_for("Biometric authentication: fingerprint template.", "biometric_identifier")),
            1,
        )

    def test_voiceprint(self):
        self.assertEqual(len(self._findings_for("The access log stores a voiceprint.", "biometric_identifier")), 1)

    def test_facial_recognition_template(self):
        self.assertEqual(
            len(self._findings_for("Facial recognition template match succeeded.", "biometric_identifier")),
            1,
        )

    def test_passport_photo_without_recognition_does_not_fire(self):
        self.assertEqual(len(self._findings_for("The passport photo was attached.", "biometric_identifier")), 0)

    def test_fingerprint_metaphor_does_not_fire(self):
        self.assertEqual(
            len(self._findings_for("The deal has a unique market fingerprint.", "biometric_identifier")),
            0,
        )

    def test_mandarin_and_arabic_biometric_fields_fire(self):
        self.assertEqual(
            len(self._findings_for("生物识别模板: 指纹.", "biometric_identifier", source="CN", dest="CN")),
            1,
        )
        self.assertEqual(len(self._findings_for("قالب بصمة.", "biometric_identifier", source="AE", dest="AE")), 1)


class GeneticDataTests(_BaseSpecialCategoryTests):
    def test_genetic_test_result(self):
        f = self._findings_for("Genetic test result: BRCA1 positive.", "genetic_data")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")

    def test_dna_profile(self):
        self.assertEqual(len(self._findings_for("The file includes a DNA profile.", "genetic_data")), 1)

    def test_pathogenic_variant(self):
        self.assertEqual(len(self._findings_for("Pathogenic variant noted in the report.", "genetic_data")), 1)

    def test_dna_metaphor_does_not_fire(self):
        self.assertEqual(len(self._findings_for("Customer obsession is in the company's DNA.", "genetic_data")), 0)

    def test_brca_without_result_context_does_not_fire(self):
        self.assertEqual(len(self._findings_for("BRCA Holdings signed the term sheet.", "genetic_data")), 0)

    def test_mandarin_and_arabic_genetic_fields_fire(self):
        self.assertEqual(
            len(self._findings_for("基因检测结果: BRCA1 阳性.", "genetic_data", source="CN", dest="CN")),
            1,
        )
        self.assertEqual(
            len(self._findings_for("نتيجة الاختبار الجيني: BRCA1 إيجابي.", "genetic_data", source="AE", dest="AE")),
            1,
        )


class SexualOrientationTests(_BaseSpecialCategoryTests):
    def test_explicit_orientation_field(self):
        f = self._findings_for("Sexual orientation: bisexual.", "sexual_orientation")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")

    def test_named_subject_orientation(self):
        self.assertEqual(len(self._findings_for("Ms Lee identifies as lesbian.", "sexual_orientation")), 1)

    def test_same_sex_partner_with_named_subject(self):
        self.assertEqual(len(self._findings_for("Mr Tan disclosed a same-sex spouse.", "sexual_orientation")), 1)

    def test_orientation_week_does_not_fire(self):
        self.assertEqual(len(self._findings_for("Orientation week starts on Monday.", "sexual_orientation")), 0)

    def test_policy_debate_without_subject_does_not_fire(self):
        self.assertEqual(
            len(self._findings_for("The memo discusses same-sex marriage policy.", "sexual_orientation")),
            0,
        )


class SexLifeReferenceTests(_BaseSpecialCategoryTests):
    def test_explicit_sexual_history_field(self):
        f = self._findings_for("Sexual history: disclosed to clinic intake nurse.", "sex_life_reference")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")

    def test_named_subject_sexual_activity(self):
        self.assertEqual(len(self._findings_for("Ms Lee reported sexual activity.", "sex_life_reference")), 1)

    def test_sti_status_field(self):
        self.assertEqual(
            len(self._findings_for("STI status: pending laboratory confirmation.", "sex_life_reference")),
            1,
        )

    def test_unrelated_sex_word_does_not_fire(self):
        self.assertEqual(
            len(self._findings_for("Sex-disaggregated statistics were reviewed.", "sex_life_reference")),
            0,
        )

    def test_activity_without_sexual_context_does_not_fire(self):
        self.assertEqual(len(self._findings_for("Ms Lee reported increased activity.", "sex_life_reference")), 0)


class OptOutTests(_BaseSpecialCategoryTests):
    def tearDown(self):
        os.environ.pop("JUNAS_SPECIAL_CATEGORY_DISABLE", None)

    def test_disable_religion(self):
        os.environ["JUNAS_SPECIAL_CATEGORY_DISABLE"] = "religion"
        self.assertEqual(len(self._findings_for("Dr Jane Tan is a devout Muslim.", "religious_belief")), 0)

    def test_disable_union(self):
        os.environ["JUNAS_SPECIAL_CATEGORY_DISABLE"] = "union"
        self.assertEqual(len(self._findings_for("Mr Tan joined the NTUC.", "trade_union_membership")), 0)

    def test_disable_political(self):
        os.environ["JUNAS_SPECIAL_CATEGORY_DISABLE"] = "political"
        self.assertEqual(len(self._findings_for("Ms Lee is a member of the PAP.", "political_opinion")), 0)

    def test_disable_multiple(self):
        os.environ["JUNAS_SPECIAL_CATEGORY_DISABLE"] = "religion,union,political"
        text = "Dr Tan is a devout Muslim, joined the NTUC, and is a member of the PAP."
        for rule in ("religious_belief", "trade_union_membership", "political_opinion"):
            self.assertEqual(len(self._findings_for(text, rule)), 0, f"expected {rule} disabled")

    def test_disable_health(self):
        os.environ["JUNAS_SPECIAL_CATEGORY_DISABLE"] = "health"
        text = "Ms Lee was diagnosed with type 2 diabetes. Medication: metformin."
        for rule in ("health_condition", "medical_treatment"):
            self.assertEqual(len(self._findings_for(text, rule)), 0, f"expected {rule} disabled")

    def test_disable_biometric_and_genetic(self):
        os.environ["JUNAS_SPECIAL_CATEGORY_DISABLE"] = "biometric,genetic"
        text = "Biometric template: fingerprint hash. Genetic test result: BRCA1 positive."
        for rule in ("biometric_identifier", "genetic_data"):
            self.assertEqual(len(self._findings_for(text, rule)), 0, f"expected {rule} disabled")

    def test_disable_sexual_categories(self):
        os.environ["JUNAS_SPECIAL_CATEGORY_DISABLE"] = "sexual"
        text = "Sexual orientation: bisexual. Sexual history: disclosed to clinic intake nurse."
        for rule in ("sexual_orientation", "sex_life_reference"):
            self.assertEqual(len(self._findings_for(text, rule)), 0, f"expected {rule} disabled")

    def test_disable_racial_ethnic_origin(self):
        os.environ["JUNAS_SPECIAL_CATEGORY_DISABLE"] = "ethnicity"
        self.assertEqual(len(self._findings_for("Ethnicity: Han Chinese.", "racial_ethnic_origin")), 0)


class CitationsTests(_BaseSpecialCategoryTests):
    def test_religion_citation_includes_gdpr_art_9(self):
        from junas.review.citations import pii_rationale
        rationale = pii_rationale(rule="religious_belief", jurisdiction="EU", matched_text="Muslim")
        self.assertIn("Art 9", rationale)

    def test_union_citation_includes_pipa_art_23(self):
        from junas.review.citations import pii_rationale
        rationale = pii_rationale(rule="trade_union_membership", jurisdiction="KR", matched_text="NTUC")
        self.assertIn("PIPA Korea Art 23", rationale)

    def test_political_citation_includes_lgpd(self):
        from junas.review.citations import pii_rationale
        rationale = pii_rationale(rule="political_opinion", jurisdiction="EU", matched_text="PAP")
        self.assertIn("LGPD", rationale)

    def test_racial_ethnic_citation_includes_gdpr_art_9(self):
        from junas.review.citations import pii_rationale
        rationale = pii_rationale(rule="racial_ethnic_origin", jurisdiction="EU", matched_text="Han Chinese")
        self.assertIn("GDPR Art 9", rationale)

    def test_health_citation_includes_gdpr_and_hipaa(self):
        from junas.review.citations import pii_rationale
        rationale = pii_rationale(rule="health_condition", jurisdiction="EU", matched_text="diabetes")
        self.assertIn("GDPR Art 9", rationale)
        self.assertIn("HIPAA", rationale)

    def test_treatment_citation_includes_pdpc_healthcare(self):
        from junas.review.citations import pii_rationale
        rationale = pii_rationale(rule="medical_treatment", jurisdiction="SG", matched_text="metformin")
        self.assertIn("Healthcare Sector Advisory", rationale)

    def test_biometric_citation_includes_recital_51(self):
        from junas.review.citations import pii_rationale
        rationale = pii_rationale(rule="biometric_identifier", jurisdiction="EU", matched_text="fingerprint hash")
        self.assertIn("Recital 51", rationale)

    def test_genetic_citation_includes_gdpr_art_9(self):
        from junas.review.citations import pii_rationale
        rationale = pii_rationale(rule="genetic_data", jurisdiction="EU", matched_text="BRCA1 positive")
        self.assertIn("GDPR Art 9", rationale)

    def test_orientation_citation_includes_gdpr_art_9(self):
        from junas.review.citations import pii_rationale
        rationale = pii_rationale(rule="sexual_orientation", jurisdiction="EU", matched_text="bisexual")
        self.assertIn("GDPR Art 9", rationale)

    def test_sex_life_citation_includes_gdpr_art_9(self):
        from junas.review.citations import pii_rationale
        rationale = pii_rationale(rule="sex_life_reference", jurisdiction="EU", matched_text="Sexual history")
        self.assertIn("GDPR Art 9", rationale)


if __name__ == "__main__":
    unittest.main()
