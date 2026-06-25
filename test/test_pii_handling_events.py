"""Items 109 + 110 + 111 plus DPDP 2025 hooks: PII-handling-event markers.

Five PII-category rules ship at fixed `medium` severity:

- 109 `cross_border_transfer_marker` — `transfer outside Singapore`, `SCC executed`,
       `adequacy decision`, `CAC security assessment`, `ASEAN MCCs`, `APEC CBPR`,
       `binding corporate rules`, `Schrems II`, `data export to`.
- 110 `consent_withdrawal_marker` — `withdraw consent`, `DSAR`, `right to erasure`,
       `right to be forgotten`, `do not sell`, `data deletion request`, `objection to
       processing`, `retention period expired`.
- 111 `data_minimisation_marker` — `data minimisation`, `purpose limitation`,
       `limited to what is necessary`, `over-collection`, `excessive data collection`,
       `Minimum Necessary Standard`.
- DPDP 2025 `personal_data_security_safeguards` — reasonable security safeguards,
       personal-data access controls, logs/monitoring/review.
- DPDP 2025 `personal_data_breach_notification` — personal data breach and affected
       Data Principal notification/intimation.

All five reuse `_is_negated_context` via the `_PII_NEGATION_GUARDED` frozenset.
No MNPI co-occurrence amplifier — these fire at fixed medium standalone.
"""

import unittest

from junas.review.citations import pii_rationale
from junas.review.engine import PreSendReviewEngine


class _ReviewHelper(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _findings(self, text: str, document_type: str = "memo",
                  source_jurisdiction: str = "SG", destination_jurisdiction: str = "SG"):
        return self.engine.review(
            text=text,
            source_jurisdiction=source_jurisdiction,
            destination_jurisdiction=destination_jurisdiction,
            entity_id=None,
            include_suggestions=False,
            document_type=document_type,
            review_profile="strict",
        ).findings

    def _by_rule(self, findings, rule: str):
        return [f for f in findings if f.rule == rule]


# ----- Item 109: cross-border transfer markers ------------------------------------

class CrossBorderRecallTests(_ReviewHelper):
    def test_transfer_outside_singapore(self):
        self.assertTrue(self._by_rule(
            self._findings("Personal data will be transferred outside Singapore for processing."),
            "cross_border_transfer_marker"))

    def test_transfer_outside_eea(self):
        self.assertTrue(self._by_rule(
            self._findings("The vendor sits outside the EEA, so transfer outside the EEA rules apply."),
            "cross_border_transfer_marker", destination_jurisdiction="EU")
            if False else self._by_rule(
                self._findings("The vendor sits outside the EEA, so transfer outside the EEA rules apply.",
                               destination_jurisdiction="EU"),
                "cross_border_transfer_marker"))

    def test_third_country_transfer(self):
        self.assertTrue(self._by_rule(
            self._findings("Counsel reviewed the third country transfer documentation.",
                           destination_jurisdiction="EU"),
            "cross_border_transfer_marker"))

    def test_scc_executed(self):
        self.assertTrue(self._by_rule(
            self._findings("EU SCCs executed with the controller in February.",
                           destination_jurisdiction="EU"),
            "cross_border_transfer_marker"))

    def test_standard_contractual_clauses(self):
        self.assertTrue(self._by_rule(
            self._findings("We rely on the standard contractual clauses module 2.",
                           destination_jurisdiction="EU"),
            "cross_border_transfer_marker"))

    def test_uk_idta(self):
        self.assertTrue(self._by_rule(
            self._findings("UK IDTA appended to the master service agreement.",
                           destination_jurisdiction="UK"),
            "cross_border_transfer_marker"))

    def test_adequacy_decision(self):
        self.assertTrue(self._by_rule(
            self._findings("Relying on the adequacy decision for transfers to Korea.",
                           destination_jurisdiction="EU"),
            "cross_border_transfer_marker"))

    def test_cac_security_assessment(self):
        self.assertTrue(self._by_rule(
            self._findings("Drafting the CAC security assessment application for the PRC transfer."),
            "cross_border_transfer_marker"))

    def test_cac_standard_contract(self):
        self.assertTrue(self._by_rule(
            self._findings("We will submit the CAC standard contract filing this quarter."),
            "cross_border_transfer_marker"))

    def test_asean_mccs(self):
        self.assertTrue(self._by_rule(
            self._findings("Adopting ASEAN MCCs across the regional entities."),
            "cross_border_transfer_marker"))

    def test_apec_cbpr(self):
        self.assertTrue(self._by_rule(
            self._findings("Vendor maintains APEC CBPR certification."),
            "cross_border_transfer_marker"))

    def test_binding_corporate_rules(self):
        self.assertTrue(self._by_rule(
            self._findings("Group-wide binding corporate rules approved by the lead supervisory authority."),
            "cross_border_transfer_marker"))

    def test_schrems_ii(self):
        self.assertTrue(self._by_rule(
            self._findings("Schrems II reliance disclosed in the transfer impact assessment.",
                           destination_jurisdiction="EU"),
            "cross_border_transfer_marker"))

    def test_personal_data_export(self):
        self.assertTrue(self._by_rule(
            self._findings("This is a personal data export to the US under EU SCCs."),
            "cross_border_transfer_marker"))

    def test_data_export_to_country(self):
        self.assertTrue(self._by_rule(
            self._findings("The data export to Japan must be logged in the transfer register."),
            "cross_border_transfer_marker"))


class CrossBorderPrecisionTests(_ReviewHelper):
    def test_negated_transfer_outside(self):
        # Negation must be within 15 chars of match start (per _NEGATION_LOOKBACK).
        self.assertFalse(self._by_rule(
            self._findings("Data is not transferred outside Singapore at this stage."),
            "cross_border_transfer_marker"))

    def test_negated_scc(self):
        self.assertFalse(self._by_rule(
            self._findings("Without any standard contractual clauses in place, transfers are paused."),
            "cross_border_transfer_marker"))

    def test_data_export_tooling_does_not_fire(self):
        # `data\s+export\s+to\s+` requires whitespace after "to" — "tooling" has no
        # whitespace after the "to" substring, so the regex correctly doesn't fire.
        self.assertFalse(self._by_rule(
            self._findings("Our data export tooling is unrelated to GDPR."),
            "cross_border_transfer_marker"))


# ----- Item 110: consent withdrawal / DSR markers ---------------------------------

class ConsentWithdrawalRecallTests(_ReviewHelper):
    def test_withdraw_consent(self):
        self.assertTrue(self._by_rule(
            self._findings("The subject opted to withdraw consent for marketing communications."),
            "consent_withdrawal_marker"))

    def test_consent_has_been_withdrawn(self):
        self.assertTrue(self._by_rule(
            self._findings("Consent has been withdrawn for the profiling activity."),
            "consent_withdrawal_marker"))

    def test_dsar(self):
        self.assertTrue(self._by_rule(
            self._findings("We received a DSAR last Friday."),
            "consent_withdrawal_marker"))

    def test_data_subject_access_request(self):
        self.assertTrue(self._by_rule(
            self._findings("Counsel is responding to the data subject access request."),
            "consent_withdrawal_marker"))

    def test_right_to_erasure(self):
        self.assertTrue(self._by_rule(
            self._findings("The user invoked the right to erasure under Article 17."),
            "consent_withdrawal_marker"))

    def test_erasure_request(self):
        self.assertTrue(self._by_rule(
            self._findings("Processing the erasure request from EU customer 4291."),
            "consent_withdrawal_marker"))

    def test_right_to_be_forgotten(self):
        self.assertTrue(self._by_rule(
            self._findings("Court ruling on the right to be forgotten took effect last month."),
            "consent_withdrawal_marker"))

    def test_right_to_delete(self):
        self.assertTrue(self._by_rule(
            self._findings("California user exercised the right to delete under CPRA.",
                           destination_jurisdiction="US"),
            "consent_withdrawal_marker"))

    def test_do_not_sell(self):
        self.assertTrue(self._by_rule(
            self._findings("Honour the do not sell my personal information request promptly.",
                           destination_jurisdiction="US"),
            "consent_withdrawal_marker"))

    def test_data_deletion_request(self):
        self.assertTrue(self._by_rule(
            self._findings("Engineering received a data deletion request via the privacy portal."),
            "consent_withdrawal_marker"))

    def test_delete_my_personal_data(self):
        self.assertTrue(self._by_rule(
            self._findings("Subject email: please delete my personal data from your systems."),
            "consent_withdrawal_marker"))

    def test_objection_to_processing(self):
        self.assertTrue(self._by_rule(
            self._findings("Lodging an objection to processing for direct marketing.",
                           destination_jurisdiction="EU"),
            "consent_withdrawal_marker"))

    def test_rectification_request(self):
        self.assertTrue(self._by_rule(
            self._findings("Pending rectification request — address correction needed.",
                           destination_jurisdiction="EU"),
            "consent_withdrawal_marker"))

    def test_retention_period_expired(self):
        self.assertTrue(self._by_rule(
            self._findings("Retention period has expired; schedule purge for next month."),
            "consent_withdrawal_marker"))


class ConsentWithdrawalPrecisionTests(_ReviewHelper):
    def test_negated_withdrawal(self):
        self.assertFalse(self._by_rule(
            self._findings("The subject did not withdraw consent for analytics."),
            "consent_withdrawal_marker"))

    def test_negated_dsar(self):
        self.assertFalse(self._by_rule(
            self._findings("No DSAR was received during the audit period."),
            "consent_withdrawal_marker"))

    def test_negated_erasure(self):
        self.assertFalse(self._by_rule(
            self._findings("There is no erasure request pending for this tenant."),
            "consent_withdrawal_marker"))


# ----- Item 111: data minimisation markers ----------------------------------------

class DataMinimisationRecallTests(_ReviewHelper):
    def test_data_minimisation_principle(self):
        self.assertTrue(self._by_rule(
            self._findings("Compliance reviewed the form against the data minimisation principle.",
                           destination_jurisdiction="EU"),
            "data_minimisation_marker"))

    def test_data_minimization_us_spelling(self):
        self.assertTrue(self._by_rule(
            self._findings("Engineering applied data minimization to the signup flow."),
            "data_minimisation_marker"))

    def test_purpose_limitation(self):
        self.assertTrue(self._by_rule(
            self._findings("Vendor data sharing was scoped under purpose limitation.",
                           destination_jurisdiction="EU"),
            "data_minimisation_marker"))

    def test_adequate_relevant_limited(self):
        self.assertTrue(self._by_rule(
            self._findings("Field collection is adequate, relevant and limited to the stated purpose.",
                           destination_jurisdiction="EU"),
            "data_minimisation_marker"))

    def test_limited_to_what_is_necessary(self):
        self.assertTrue(self._by_rule(
            self._findings("Fields are limited to what is necessary for KYC.",
                           destination_jurisdiction="EU"),
            "data_minimisation_marker"))

    def test_collecting_excessive_data(self):
        self.assertTrue(self._by_rule(
            self._findings("The vendor is collecting excessive personal data on signup."),
            "data_minimisation_marker"))

    def test_over_collection(self):
        self.assertTrue(self._by_rule(
            self._findings("Audit findings flag over-collection by the marketing pixel."),
            "data_minimisation_marker"))

    def test_excessive_data_collection(self):
        self.assertTrue(self._by_rule(
            self._findings("Excessive data collection was flagged in the DPIA."),
            "data_minimisation_marker"))

    def test_minimum_necessary_standard(self):
        self.assertTrue(self._by_rule(
            self._findings("HIPAA Minimum Necessary Standard applies to the patient export.",
                           destination_jurisdiction="US"),
            "data_minimisation_marker"))


class DataMinimisationPrecisionTests(_ReviewHelper):
    def test_negated_minimisation(self):
        self.assertFalse(self._by_rule(
            self._findings("No data minimisation review has been undertaken this cycle.",
                           destination_jurisdiction="EU"),
            "data_minimisation_marker"))

    def test_negated_over_collection(self):
        self.assertFalse(self._by_rule(
            self._findings("There is no over-collection by the new endpoint."),
            "data_minimisation_marker"))


# ----- India DPDP Rules 2025 security / breach hooks -------------------------------

class DPDP2025SecurityRecallTests(_ReviewHelper):
    def test_reasonable_security_safeguards(self):
        self.assertTrue(self._by_rule(
            self._findings("India plan: implement reasonable security safeguards for the dataset.",
                           destination_jurisdiction="IN"),
            "personal_data_security_safeguards"))

    def test_personal_data_access_logs(self):
        self.assertTrue(self._by_rule(
            self._findings("Logs and monitoring review for personal data access must be retained.",
                           destination_jurisdiction="IN"),
            "personal_data_security_safeguards"))

    def test_personal_data_breach(self):
        self.assertTrue(self._by_rule(
            self._findings("A personal data breach may require board and user updates.",
                           destination_jurisdiction="IN"),
            "personal_data_breach_notification"))

    def test_data_principal_breach_notification(self):
        self.assertTrue(self._by_rule(
            self._findings("Notify each affected Data Principal without delay.",
                           destination_jurisdiction="IN"),
            "personal_data_breach_notification"))


class DPDP2025PrecisionTests(_ReviewHelper):
    def test_negated_personal_data_breach(self):
        self.assertFalse(self._by_rule(
            self._findings("No personal data breach occurred after the failover.",
                           destination_jurisdiction="IN"),
            "personal_data_breach_notification"))

    def test_generic_security_review_does_not_fire(self):
        self.assertFalse(self._by_rule(
            self._findings("Security review of the office access badges is pending.",
                           destination_jurisdiction="IN"),
            "personal_data_security_safeguards"))


# ----- Severity is fixed medium (no co-occurrence amplifier) ----------------------

class SeverityIsFixedMediumTests(_ReviewHelper):
    """Items 109/110/111 do NOT use the MNPI co-occurrence amplifier; they fire at
    fixed medium severity regardless of adjacent substrate."""

    def test_cross_border_alone_is_medium(self):
        f = self._by_rule(
            self._findings("Standard contractual clauses executed last week.",
                           destination_jurisdiction="EU"),
            "cross_border_transfer_marker")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium")

    def test_cross_border_adjacent_to_codename_stays_medium(self):
        # Unlike MNPI rules (95/96/97/112/113/114/115), PII handling-event rules do not
        # amplify when adjacent to a transaction codename. Reviewer judgment closes the loop.
        f = self._by_rule(
            self._findings("Project Sapphire: personal data export to the US under EU SCCs."),
            "cross_border_transfer_marker")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium",
                         "v1 ships fixed-medium; no amplifier (see plan §Out of scope)")

    def test_consent_withdrawal_alone_is_medium(self):
        f = self._by_rule(
            self._findings("The data subject access request requires response by Friday."),
            "consent_withdrawal_marker")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium")

    def test_data_minimisation_alone_is_medium(self):
        f = self._by_rule(
            self._findings("Compliance reviewed the form against the data minimisation principle.",
                           destination_jurisdiction="EU"),
            "data_minimisation_marker")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium")

    def test_dpdp_breach_alone_is_medium(self):
        f = self._by_rule(
            self._findings("A personal data breach notification must be prepared.",
                           destination_jurisdiction="IN"),
            "personal_data_breach_notification")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium")


# ----- Citations -------------------------------------------------------------------

class CitationTests(unittest.TestCase):
    def test_cross_border_rationale_carries_pdpa_s26(self):
        text = pii_rationale(
            rule="cross_border_transfer_marker",
            jurisdiction="SG",
            matched_text="transfer outside Singapore",
        )
        self.assertIn("PDPA s26", text)
        self.assertIn("Personal Data Protection Act", text)

    def test_cross_border_rationale_carries_gdpr_chapter_v(self):
        text = pii_rationale(
            rule="cross_border_transfer_marker",
            jurisdiction="EU",
            matched_text="EU SCCs",
        )
        self.assertIn("GDPR Chapter V", text)
        self.assertIn("GDPR Article 4", text)

    def test_cross_border_rationale_carries_pipl_art_38(self):
        text = pii_rationale(
            rule="cross_border_transfer_marker",
            jurisdiction="SG",
            matched_text="CAC security assessment",
        )
        self.assertIn("PIPL Art 38", text)

    def test_consent_withdrawal_rationale_carries_gdpr_art_17(self):
        text = pii_rationale(
            rule="consent_withdrawal_marker",
            jurisdiction="EU",
            matched_text="right to erasure",
        )
        self.assertIn("Art 7(3)", text)
        self.assertIn("Art 17", text)

    def test_consent_withdrawal_rationale_carries_ccpa(self):
        text = pii_rationale(
            rule="consent_withdrawal_marker",
            jurisdiction="US",
            matched_text="do not sell my personal information",
        )
        self.assertIn("CCPA/CPRA", text)
        self.assertIn("1798.120", text)

    def test_data_minimisation_rationale_carries_gdpr_art_5(self):
        text = pii_rationale(
            rule="data_minimisation_marker",
            jurisdiction="EU",
            matched_text="data minimisation principle",
        )
        self.assertIn("Art 5(1)(c)", text)
        self.assertIn("adequate, relevant and limited", text)

    def test_data_minimisation_rationale_carries_hipaa(self):
        text = pii_rationale(
            rule="data_minimisation_marker",
            jurisdiction="US",
            matched_text="Minimum Necessary Standard",
        )
        self.assertIn("HIPAA Minimum Necessary", text)
        self.assertIn("164.502", text)

    def test_dpdp_security_rationale_carries_rule_6(self):
        text = pii_rationale(
            rule="personal_data_security_safeguards",
            jurisdiction="IN",
            matched_text="reasonable security safeguards",
        )
        self.assertIn("DPDP Rules 2025 rule 6", text)

    def test_dpdp_breach_rationale_carries_rule_7(self):
        text = pii_rationale(
            rule="personal_data_breach_notification",
            jurisdiction="IN",
            matched_text="personal data breach",
        )
        self.assertIn("DPDP Rules 2025 rule 7", text)


if __name__ == "__main__":
    unittest.main()
