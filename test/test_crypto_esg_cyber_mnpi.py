"""Items 112 + 113 + 114: crypto / ESG / cyber-incident MNPI markers.

Five rules ship under the items-95/96/97/115 co-occurrence-amplifier pattern:

- 112 `dpt_pre_listing_marker` — token-launch / TGE / airdrop / unlock / exchange-listing /
       Wells-notice / enforcement-action.
- 112 `dpt_protocol_event_marker` — hard fork / governance proposal / validator slashing /
       staking-rewards / treasury rebalancing / multi-sig movement.
- 113 `esg_climate_pre_disclosure` — Scope 1/2/3 / tCO2e / science-based target / transition
       plan / value-chain emissions / climate-related disclosure.
- 113 `esg_target_revision` — revise/restate emissions or targets / change baseline year /
       limited or reasonable assurance / qualified opinion on sustainability.
- 114 `cyber_incident_pre_disclosure` — materiality determination / ransomware /
       data exfiltration / lateral movement / 8-K Item 1.05 filing language.

All ship at severity `low` standalone and amplify to `medium` when within ±200 chars of a
deal substrate. Negation guard reused.
"""

import unittest

from kaypoh.review.citations import mnpi_rationale
from kaypoh.review.engine import PreSendReviewEngine


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


# ----- Item 112: crypto / digital-asset --------------------------------------------

class DPTPreListingRecallTests(_ReviewHelper):
    def test_mainnet_launch(self):
        self.assertTrue(self._by_rule(
            self._findings("Mainnet launch is scheduled for next week."),
            "dpt_pre_listing_marker"))

    def test_token_generation_event(self):
        self.assertTrue(self._by_rule(
            self._findings("The token generation event will be on 1 June."),
            "dpt_pre_listing_marker"))

    def test_tge_case_locked(self):
        self.assertTrue(self._by_rule(
            self._findings("TGE timing is under discussion."),
            "dpt_pre_listing_marker"))

    def test_lowercase_tge_does_not_fire(self):
        # "tge" lowercase shouldn't trigger — `(?-i:TGE)` requires uppercase.
        self.assertFalse(self._by_rule(
            self._findings("Voltage drops at the bridge tge boundary."),
            "dpt_pre_listing_marker"))

    def test_airdrop_schedule(self):
        self.assertTrue(self._by_rule(
            self._findings("Airdrop schedule has been finalised internally."),
            "dpt_pre_listing_marker"))

    def test_exchange_listing_decision(self):
        self.assertTrue(self._by_rule(
            self._findings("The exchange listing decision is pending compliance review."),
            "dpt_pre_listing_marker"))

    def test_listed_on_binance(self):
        self.assertTrue(self._by_rule(
            self._findings("Confidential: we will be listed on Binance next quarter."),
            "dpt_pre_listing_marker"))

    def test_wells_notice(self):
        self.assertTrue(self._by_rule(
            self._findings("Counsel received a Wells notice this morning."),
            "dpt_pre_listing_marker"))

    def test_delisting_decision(self):
        self.assertTrue(self._by_rule(
            self._findings("The delisting decision was communicated by the exchange."),
            "dpt_pre_listing_marker"))


class DPTProtocolEventRecallTests(_ReviewHelper):
    def test_hard_fork(self):
        self.assertTrue(self._by_rule(
            self._findings("A hard fork is planned for block 21,000,000."),
            "dpt_protocol_event_marker"))

    def test_governance_proposal(self):
        self.assertTrue(self._by_rule(
            self._findings("Governance proposal GIP-42 will be tabled internally first."),
            "dpt_protocol_event_marker"))

    def test_validator_slashing(self):
        self.assertTrue(self._by_rule(
            self._findings("Validator slashing parameters are being reviewed."),
            "dpt_protocol_event_marker"))

    def test_staking_rewards_adjustment(self):
        self.assertTrue(self._by_rule(
            self._findings("A staking-rewards adjustment is under consideration."),
            "dpt_protocol_event_marker"))

    def test_multi_sig_movement(self):
        self.assertTrue(self._by_rule(
            self._findings("A multi-sig transfer of treasury funds is being prepared."),
            "dpt_protocol_event_marker"))


class DPTPrecisionTests(_ReviewHelper):
    def test_negated_token_event(self):
        self.assertFalse(self._by_rule(
            self._findings("No mainnet launch is planned for this quarter."),
            "dpt_pre_listing_marker"))

    def test_negated_hard_fork(self):
        self.assertFalse(self._by_rule(
            self._findings("There is no hard fork planned in the roadmap."),
            "dpt_protocol_event_marker"))


# ----- Item 113: ESG / sustainability ----------------------------------------------

class ESGClimateRecallTests(_ReviewHelper):
    def test_scope_1(self):
        self.assertTrue(self._by_rule(
            self._findings("Scope 1 emissions for FY2025 will be disclosed in March."),
            "esg_climate_pre_disclosure"))

    def test_scope_3_category(self):
        self.assertTrue(self._by_rule(
            self._findings("Scope 3 category breakdown is being finalised internally."),
            "esg_climate_pre_disclosure"))

    def test_tco2e_unit(self):
        self.assertTrue(self._by_rule(
            self._findings("The figure exceeds 45,000 tCO2e for the period."),
            "esg_climate_pre_disclosure"))

    def test_science_based_target(self):
        self.assertTrue(self._by_rule(
            self._findings("The board is reviewing the science-based target submission."),
            "esg_climate_pre_disclosure"))

    def test_transition_plan(self):
        self.assertTrue(self._by_rule(
            self._findings("Our transition plan will be released in Q4."),
            "esg_climate_pre_disclosure"))

    def test_lowercase_scope_does_not_fire(self):
        # `Scope 1/2/3` is case-locked. Lowercase "scope" is generic English.
        self.assertFalse(self._by_rule(
            self._findings("The audit scope 1 was insufficient for the review."),
            "esg_climate_pre_disclosure"))


class ESGTargetRevisionRecallTests(_ReviewHelper):
    def test_revise_downward_targets(self):
        self.assertTrue(self._by_rule(
            self._findings("We may revise downward our 2030 emissions targets next month."),
            "esg_target_revision"))

    def test_restate_prior_year_scope(self):
        self.assertTrue(self._by_rule(
            self._findings("Counsel recommends we restate prior-year Scope 2 figures."),
            "esg_target_revision"))

    def test_change_baseline_year(self):
        self.assertTrue(self._by_rule(
            self._findings("Management proposes to change the baseline year to 2019."),
            "esg_target_revision"))

    def test_limited_assurance_opinion(self):
        self.assertTrue(self._by_rule(
            self._findings("The auditor issued a limited assurance opinion on sustainability."),
            "esg_target_revision"))

    def test_qualified_opinion_on_sustainability(self):
        self.assertTrue(self._by_rule(
            self._findings("Expect a qualified opinion on sustainability for FY2025."),
            "esg_target_revision"))


class ESGPrecisionTests(_ReviewHelper):
    def test_negated_target_revision(self):
        self.assertFalse(self._by_rule(
            self._findings("There is no plan to revise downward our emissions targets."),
            "esg_target_revision"))


# ----- Item 114: cyber-incident pre-disclosure -------------------------------------

class CyberIncidentRecallTests(_ReviewHelper):
    def test_materiality_determination(self):
        self.assertTrue(self._by_rule(
            self._findings("Counsel is preparing a materiality determination memo."),
            "cyber_incident_pre_disclosure"))

    def test_we_have_determined_material(self):
        self.assertTrue(self._by_rule(
            self._findings("We have determined that this incident is material."),
            "cyber_incident_pre_disclosure"))

    def test_ransomware_affecting(self):
        self.assertTrue(self._by_rule(
            self._findings("Ransomware affecting the EU billing cluster was confirmed."),
            "cyber_incident_pre_disclosure"))

    def test_data_exfiltration_confirmed(self):
        self.assertTrue(self._by_rule(
            self._findings("Data exfiltration confirmed by the IR vendor."),
            "cyber_incident_pre_disclosure"))

    def test_unauthorised_access_to_production(self):
        self.assertTrue(self._by_rule(
            self._findings("Unauthorised access to production database detected at 03:42 UTC."),
            "cyber_incident_pre_disclosure"))

    def test_lateral_movement(self):
        self.assertTrue(self._by_rule(
            self._findings("Lateral movement observed across the DMZ subnet."),
            "cyber_incident_pre_disclosure"))

    def test_8k_item_1_05_filing(self):
        self.assertTrue(self._by_rule(
            self._findings("Drafting the 8-K Item 1.05 filing now."),
            "cyber_incident_pre_disclosure"))

    def test_4_business_day_timer(self):
        self.assertTrue(self._by_rule(
            self._findings("The 4-business-day timer started at materiality determination."),
            "cyber_incident_pre_disclosure"))


class CyberIncidentPrecisionTests(_ReviewHelper):
    def test_negated_ransomware(self):
        self.assertFalse(self._by_rule(
            self._findings("No ransomware affecting any customer environments."),
            "cyber_incident_pre_disclosure"))

    def test_negated_exfiltration(self):
        self.assertFalse(self._by_rule(
            self._findings("There is no data exfiltration confirmed at this stage."),
            "cyber_incident_pre_disclosure"))


# ----- Co-occurrence amplifier (all 5 rules) ---------------------------------------

class CoOccurrenceAmplifierTests(_ReviewHelper):
    def test_dpt_pre_listing_alone_stays_low(self):
        f = self._by_rule(
            self._findings("Mainnet launch coordination call at 3pm."),
            "dpt_pre_listing_marker")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "low")

    def test_dpt_pre_listing_adjacent_to_codename_amplifies(self):
        f = self._by_rule(
            self._findings("Project Aurora mainnet launch is targeted for Q3."),
            "dpt_pre_listing_marker")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium")

    def test_dpt_protocol_event_adjacent_to_definitive_agreement_amplifies(self):
        f = self._by_rule(
            self._findings("The SPA contemplates a hard fork before closing."),
            "dpt_protocol_event_marker")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium")

    def test_esg_climate_alone_stays_low(self):
        f = self._by_rule(
            self._findings("Scope 1 reporting deadline is end of June."),
            "esg_climate_pre_disclosure")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "low")

    def test_esg_climate_adjacent_to_embargo_amplifies(self):
        f = self._by_rule(
            self._findings("Embargoed until 10am SGT: Scope 3 numbers for FY2025."),
            "esg_climate_pre_disclosure")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium")

    def test_esg_target_revision_adjacent_to_mac_amplifies(self):
        f = self._by_rule(
            self._findings("Given the material adverse change, we will restate prior-year Scope 2 figures."),
            "esg_target_revision")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium")

    def test_cyber_alone_stays_low(self):
        f = self._by_rule(
            self._findings("IR vendor confirmed ransomware affecting the staging environment."),
            "cyber_incident_pre_disclosure")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "low")

    def test_cyber_adjacent_to_codename_amplifies(self):
        f = self._by_rule(
            self._findings("Project Halberd: ransomware affecting the production cluster confirmed."),
            "cyber_incident_pre_disclosure")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium")

    def test_cyber_far_from_substrate_stays_low(self):
        padding = ". ".join(["Quarterly summary continues"] * 30) + ". "
        text = "Project Halberd announced. " + padding + "Ransomware affecting our network."
        f = self._by_rule(self._findings(text), "cyber_incident_pre_disclosure")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "low")


# ----- Citations -------------------------------------------------------------------

class CitationTests(unittest.TestCase):
    def test_dpt_pre_listing_rationale_carries_mas_psn02(self):
        text = mnpi_rationale(
            rule="dpt_pre_listing_marker",
            jurisdiction="SG",
            severity="medium",
            matched_text="mainnet launch",
        )
        self.assertIn("MAS Notice PSN02", text)
        self.assertIn("Payment Services Act", text)

    def test_dpt_protocol_rationale_carries_mica(self):
        text = mnpi_rationale(
            rule="dpt_protocol_event_marker",
            jurisdiction="EU",
            severity="medium",
            matched_text="hard fork",
        )
        self.assertIn("MiCA", text)

    def test_esg_climate_rationale_carries_sgx_711(self):
        text = mnpi_rationale(
            rule="esg_climate_pre_disclosure",
            jurisdiction="SG",
            severity="medium",
            matched_text="Scope 3 emissions",
        )
        self.assertIn("711A/711B", text)
        self.assertIn("IFRS S2", text)

    def test_esg_target_revision_rationale_carries_csrd(self):
        text = mnpi_rationale(
            rule="esg_target_revision",
            jurisdiction="EU",
            severity="medium",
            matched_text="restate prior-year Scope 2",
        )
        self.assertIn("CSRD", text)

    def test_cyber_incident_rationale_carries_8k_item_1_05(self):
        text = mnpi_rationale(
            rule="cyber_incident_pre_disclosure",
            jurisdiction="US",
            severity="medium",
            matched_text="materiality determination",
        )
        self.assertIn("8-K Item 1.05", text)
        self.assertIn("4-business-day", text)

    def test_cyber_incident_rationale_carries_mas_trm(self):
        text = mnpi_rationale(
            rule="cyber_incident_pre_disclosure",
            jurisdiction="SG",
            severity="medium",
            matched_text="materiality determination",
        )
        self.assertIn("MAS TRM", text)


if __name__ == "__main__":
    unittest.main()
