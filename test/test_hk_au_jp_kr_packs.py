"""HK/AU/JP/KR jurisdiction packs.

Mirrors the SEA pack discipline: packs must load, local-ID recognizers must fire on
canonical samples, checksum validators must reject bad identifiers, statute suffixes
must be present, and the seed corpus must pass its recall/precision lock.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path

from kaypoh.review import jurisdictions
from kaypoh.review.citations import mnpi_rationale, pii_rationale
from kaypoh.review.engine import PreSendReviewEngine

REPO_ROOT = Path(__file__).resolve().parent.parent


class HkAuJpKrPackLoadTests(unittest.TestCase):
    def test_all_four_packs_load(self):
        jurisdictions.reload_registry()
        for code in ("HK", "AU", "JP", "KR"):
            self.assertIn(code, jurisdictions.RULE_PACKS, f"{code} pack missing")

    def test_each_pack_carries_recognizers(self):
        jurisdictions.reload_registry()
        for code in ("HK", "AU", "JP", "KR"):
            self.assertTrue(jurisdictions.RULE_PACKS[code].recognizers, f"{code}: no recognizers")

    def test_alias_normalisation_works(self):
        jurisdictions.reload_registry()
        for alias, expected in [
            ("HONG KONG", "HK"),
            ("AUSTRALIA", "AU"),
            ("JAPAN", "JP"),
            ("SOUTH KOREA", "KR"),
        ]:
            self.assertEqual(jurisdictions.normalize_jurisdiction(alias), expected)


class HkAuJpKrRecognizerTests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _rules(self, text: str, code: str) -> set[str]:
        result = self.engine.review(
            text=text,
            source_jurisdiction=code,
            destination_jurisdiction=code,
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
        )
        return {finding.rule for finding in result.findings}

    def test_hk_hkid_and_cr_number_fire(self):
        rules = self._rules("HKID is A123456(3). CR No. 1234567.", "HK")
        self.assertIn("hk_hkid", rules)
        self.assertIn("hk_cr_no", rules)

    def test_au_tfn_abn_acn_fire(self):
        rules = self._rules("TFN 123 456 782; ABN 51 824 753 556; ACN 004 085 616.", "AU")
        self.assertIn("au_tfn", rules)
        self.assertIn("au_abn", rules)
        self.assertIn("au_acn", rules)

    def test_au_postal_address_is_case_sensitive_for_act(self):
        self.assertIn("au_postal_address", self._rules("123 George St, Sydney NSW 2000.", "AU"))
        self.assertNotIn("au_postal_address", self._rules("Corporations Act 2001 applies.", "AU"))

    def test_jp_my_number_and_corporate_number_fire(self):
        rules = self._rules("Individual Number 123456789018; Corporate Number 8700110005901.", "JP")
        self.assertIn("jp_my_number", rules)
        self.assertIn("jp_corporate_number", rules)

    def test_kr_rrn_and_business_registration_fire(self):
        rules = self._rules(
            "Resident Registration Number 900101-1234568; Business Registration Number 220-81-62517.",
            "KR",
        )
        self.assertIn("kr_rrn", rules)
        self.assertIn("kr_business_registration", rules)

    def test_kr_rrn_shorthand_and_kr_brn_fire(self):
        rules = self._rules("resident-number 860512-2345675; KR-BRN 214-85-90321.", "KR")
        self.assertIn("kr_rrn", rules)
        self.assertIn("kr_business_registration", rules)

    def test_checksum_validators_reject_bad_values(self):
        samples = [
            ("HKID A123456(7)", "HK", "hk_hkid"),
            ("TFN 123 456 789", "AU", "au_tfn"),
            ("ABN 51 824 753 557", "AU", "au_abn"),
            ("ACN 004 085 617", "AU", "au_acn"),
            ("My Number 123456789019", "JP", "jp_my_number"),
            ("Corporate Number 8700110005902", "JP", "jp_corporate_number"),
            ("RRN 900101-1234567", "KR", "kr_rrn"),
            ("Business Registration Number 220-81-62518", "KR", "kr_business_registration"),
        ]
        for text, code, rule in samples:
            with self.subTest(rule=rule):
                self.assertNotIn(rule, self._rules(text, code))

    def test_hk_public_stale_deal_terms_do_not_fire_as_definitive_agreements(self):
        text = (
            "Public/stale transaction context: as announced on 15 March, Seabright signed "
            "a non-binding MoU to explore a green steel JV; no binding commercial terms "
            "have been agreed. As disclosed, the definitive Share Purchase Agreement was "
            "executed in 2024; no annexes to the SPA will be reproduced."
        )
        self.assertNotIn("definitive_agreement", self._rules(text, "HK"))

    def test_hk_negated_nonpublic_marker_examples_do_not_fire(self):
        text = (
            "For SFO inside information purposes, drafts must avoid undisclosed assumptions; "
            "no non-public analyst notes will be attached and do not summarise non-public consultations."
        )
        self.assertNotIn("nonpublic_marker", self._rules(text, "HK"))

    def test_hk_stage_b_public_hotline_and_closed_dsar_do_not_fire(self):
        samples = [
            ("The general Public Enquiry Hotline listed on an old brochure (8000 0000) is not in service.", "phone_number"),
            ("Public Enquiry Hotline (non-transactional): 1000 1000.", "phone_number"),
            ("No data subject access request (DSAR) was received or needed in relation to this event.", "consent_withdrawal_marker"),
        ]
        for text, rule in samples:
            with self.subTest(rule=rule, text=text):
                self.assertNotIn(rule, self._rules(text, "HK"))

    def test_hk_stage_b_generic_mnpi_spa_and_negated_mac_do_not_fire(self):
        samples = [
            (
                "References to insider, MNPI, or price sensitive in this notice reflect generic "
                "risk categories and do not indicate we hold any non-public deal terms.",
                "nonpublic_marker",
            ),
            (
                "This notice does not constitute a profit forecast and does not vary any SPA MAC clause.",
                "definitive_agreement",
            ),
            (
                "Nothing in this notice constitutes, or shall be deemed to constitute, a Material Adverse Change.",
                "material_adverse_change",
            ),
            (
                "This workflow expressly negates inference of a material adverse change from retention entries.",
                "material_adverse_change",
            ),
        ]
        for text, rule in samples:
            with self.subTest(rule=rule, text=text):
                self.assertNotIn(rule, self._rules(text, "HK"))

    def test_jp_public_helplines_do_not_fire_as_phone_numbers(self):
        text = (
            "Public helplines for general guidance: FSA Inquiry 03-0000-0000; "
            "TSE Listing Support 0570-000-000."
        )
        self.assertNotIn("phone_number", self._rules(text, "JP"))

    def test_jp_negated_material_and_definitional_nonpublic_do_not_fire(self):
        text = (
            "The draft SPA's material adverse change clause is not triggered. "
            "No undisclosed material facts remain; references to undisclosed in the policy annex "
            "are definitional only."
        )
        rules = self._rules(text, "JP")
        self.assertNotIn("material_adverse_change", rules)
        self.assertNotIn("nonpublic_marker", rules)

    def test_jp_educational_insider_lists_do_not_fire(self):
        text = (
            "Educational note: the monthly webinar on cyber hygiene, insider lists, and climate "
            "reporting is purely instructional and uses generic case studies."
        )
        self.assertNotIn("insider_list_marker", self._rules(text, "JP"))

    def test_kr_negated_term_sheet_and_public_stale_percentage_do_not_fire(self):
        text = (
            "Illustrative marketing text only; no executed term sheet exists. "
            "Public-source reference: last year's article reported sector margins at 11%; "
            "this is public and stale, not MNPI."
        )
        rules = self._rules(text, "KR")
        self.assertNotIn("definitive_agreement", rules)
        self.assertNotIn("financial_percentage", rules)

    def test_private_projection_percentage_survives_later_public_source_clause(self):
        text = (
            "Investor relations draft: if consummated, expected EPS accretion c. 6.2% in FY2027; "
            "back-up Q&A references only public-source materials."
        )
        self.assertIn("financial_percentage", self._rules(text, "SG"))

    def test_au_public_contact_channels_and_negated_mac_do_not_fire(self):
        text = (
            "Public queries to 1300 555 555 (switchboard) or media@example.com.au; "
            "regulatory liaison via listings@asx.example.au or reception +61 2 8123 4400. "
            "This memo does not include any MAC-like clause or material adverse change trigger."
        )
        rules = self._rules(text, "AU")
        self.assertNotIn("phone_number", rules)
        self.assertNotIn("email_address", rules)
        self.assertNotIn("material_adverse_change", rules)

    def test_au_stage_b_role_mailbox_generic_mnpi_and_negated_mac_bait_do_not_fire(self):
        samples = [
            (
                "Do not use the email format firstname.lastname@redgumrenewables.com.au as "
                "a live contact. Vendor contact (role only): servicedesk@botanycloud.example; "
                "employee notifications via hr-notify@redgumrenewables.com.au.",
                "email_address",
            ),
            (
                "The vendor issue is not expected to constitute a material adverse change.",
                "material_adverse_change",
            ),
            (
                '"MNPI" means information not generally available for policy training only.',
                "nonpublic_marker",
            ),
            (
                'The term "insider list" and references to MNPI are generic and describe controls.',
                "insider_list_marker",
            ),
            (
                "The vendor MSA is not a definitive agreement for any acquisition.",
                "definitive_agreement",
            ),
            (
                "This event does not constitute, and is not reasonably likely to constitute, "
                "a material adverse change.",
                "material_adverse_change",
            ),
        ]
        for text, rule in samples:
            with self.subTest(rule=rule, text=text):
                self.assertNotIn(rule, self._rules(text, "AU"))


class HkAuJpKrRationaleTests(unittest.TestCase):
    def test_pii_rationales_cite_local_statutes(self):
        self.assertIn("PDPO", pii_rationale(rule="hk_hkid", jurisdiction="HK", matched_text="A123456(3)"))
        self.assertIn("Privacy Act 1988", pii_rationale(rule="au_tfn", jurisdiction="AU"))
        self.assertIn("APPI", pii_rationale(rule="jp_my_number", jurisdiction="JP"))
        self.assertIn("PIPA", pii_rationale(rule="kr_rrn", jurisdiction="KR"))

    def test_mnpi_rationales_cite_local_statutes(self):
        for code, expected in [
            ("HK", "Securities and Futures Ordinance"),
            ("AU", "Corporations Act 2001"),
            ("JP", "Financial Instruments and Exchange Act"),
            ("KR", "Financial Investment Services and Capital Markets Act"),
        ]:
            with self.subTest(code=code):
                text = mnpi_rationale(
                    rule="transaction_codename",
                    jurisdiction=code,
                    severity="high",
                    matched_text="Project Atlas",
                )
                self.assertIn(expected, text)


class HkAuJpKrCorpusGateTests(unittest.TestCase):
    def test_hk_au_jp_kr_corpus_gate_passes(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "recall_gate.py"),
                "--corpus",
                str(REPO_ROOT / "test" / "fixtures" / "legal-corpus-hk-au-jp-kr"),
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=REPO_ROOT,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"HK/AU/JP/KR gate failed: stdout={result.stdout}\nstderr={result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
