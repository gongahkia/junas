"""SEA jurisdiction packs (MY/ID/TH/PH/VN) ship local-ID recognizers via TOML and
emit statute-cited rationales. These tests cover:

1. All five SEA packs load with their declared recognizers.
2. Each recognizer fires on a canonical sample.
3. Rationales chain the jurisdiction-specific statute reference.
4. The SEA corpus gate passes against its locked baseline.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path

from kaypoh.review import jurisdictions
from kaypoh.review.citations import pii_rationale
from kaypoh.review.engine import PreSendReviewEngine

REPO_ROOT = Path(__file__).resolve().parent.parent


class SeaPackLoadTests(unittest.TestCase):
    def test_all_five_sea_packs_load(self):
        jurisdictions.reload_registry()
        for code in ("MY", "ID", "TH", "PH", "VN"):
            self.assertIn(code, jurisdictions.RULE_PACKS, f"{code} pack missing")

    def test_each_sea_pack_carries_at_least_one_recognizer(self):
        jurisdictions.reload_registry()
        for code in ("MY", "ID", "TH", "PH", "VN"):
            pack = jurisdictions.RULE_PACKS[code]
            self.assertTrue(pack.recognizers, f"{code}: expected ≥1 recognizer, got 0")

    def test_alias_normalisation_works(self):
        jurisdictions.reload_registry()
        for alias, expected in [
            ("MALAYSIA", "MY"), ("INDONESIA", "ID"), ("THAILAND", "TH"),
            ("PHILIPPINES", "PH"), ("VIETNAM", "VN"),
        ]:
            self.assertEqual(jurisdictions.normalize_jurisdiction(alias), expected)


class SeaRecognizerFiringTests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _review(self, text: str, code: str):
        return self.engine.review(
            text=text, source_jurisdiction=code, destination_jurisdiction=code,
            entity_id=None, include_suggestions=False, document_type="generic",
        )

    def test_mykad_fires_on_dashed_format(self):
        r = self._review("Mr Ahmad's MyKad is 880415-10-5432.", "MY")
        rules = {f.rule for f in r.findings}
        self.assertIn("my_mykad", rules)

    def test_nik_fires_on_16_digits(self):
        r = self._review("NIK 3174050101900012 on file.", "ID")
        self.assertIn("id_nik", {f.rule for f in r.findings})

    def test_thai_id_fires_on_dashed_format(self):
        r = self._review("National ID 1-2345-67890-12-1 attached.", "TH")
        self.assertIn("th_national_id", {f.rule for f in r.findings})

    def test_thai_id_rejects_invalid_checksum_and_juristic_prefix(self):
        r = self._review(
            "Bait IDs: 1-2345-67890-12-3 and corporate tax ID 0-9999-12345-66-7.",
            "TH",
        )
        self.assertNotIn("th_national_id", {f.rule for f in r.findings})

    def test_philsys_and_tin_fire(self):
        r = self._review("PhilSys 1234-5678-9012 / TIN 123-456-789-000.", "PH")
        rules = {f.rule for f in r.findings}
        self.assertIn("ph_philsys", rules)
        self.assertIn("ph_tin", rules)

    def test_cccd_requires_prefix_anchor(self):
        # CCCD recognizer is prefix-anchored: a bare 12-digit run should NOT fire.
        r = self._review("Order number 001202012345 confirmed.", "VN")
        self.assertNotIn("vn_cccd", {f.rule for f in r.findings})
        # With the prefix, it should fire and the matched_text is only the 12-digit span.
        r2 = self._review("CCCD: 001202012345 issued in HN.", "VN")
        cccd = [f for f in r2.findings if f.rule == "vn_cccd"]
        self.assertEqual(len(cccd), 1)
        self.assertEqual(cccd[0].matched_text, "001202012345")


class SeaRationaleTests(unittest.TestCase):
    def test_mykad_rationale_cites_malaysia_pdpa(self):
        text = pii_rationale(rule="my_mykad", jurisdiction="MY", matched_text="880415-10-5432")
        self.assertIn("Malaysia", text)
        self.assertIn("Personal Data Protection Act 2010", text)

    def test_cross_jurisdiction_pii_chains_both_statutes(self):
        text = pii_rationale(rule="id_nik", jurisdiction="ID+SG")
        self.assertIn("UU PDP", text)
        self.assertIn("Personal Data Protection Act 2012", text)  # SG suffix


class SeaCorpusGateTests(unittest.TestCase):
    def test_sea_corpus_gate_passes(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "recall_gate.py"),
                "--corpus", str(REPO_ROOT / "test" / "fixtures" / "legal-corpus-sea"),
            ],
            capture_output=True, text=True, env=env, cwd=REPO_ROOT,
        )
        self.assertEqual(
            result.returncode, 0,
            msg=f"SEA gate failed: stdout={result.stdout}\nstderr={result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
