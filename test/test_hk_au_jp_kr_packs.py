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
