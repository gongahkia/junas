"""KAYPOH_CITATIONS_OVERRIDE lets customers substitute internal policy citations without
forking the engine. The override is consulted before the built-in lookup."""

import os
import tempfile
import unittest
from pathlib import Path

from kaypoh.review import citations


class CitationsOverrideTests(unittest.TestCase):
    def setUp(self):
        self._orig_env = os.environ.get("KAYPOH_CITATIONS_OVERRIDE")
        self._orig_dir = os.environ.get("KAYPOH_CITATIONS_OVERRIDE_DIR")
        citations._CITATIONS_OVERRIDE_CACHE.clear()

    def tearDown(self):
        if self._orig_env is None:
            os.environ.pop("KAYPOH_CITATIONS_OVERRIDE", None)
        else:
            os.environ["KAYPOH_CITATIONS_OVERRIDE"] = self._orig_env
        if self._orig_dir is None:
            os.environ.pop("KAYPOH_CITATIONS_OVERRIDE_DIR", None)
        else:
            os.environ["KAYPOH_CITATIONS_OVERRIDE_DIR"] = self._orig_dir
        citations._CITATIONS_OVERRIDE_CACHE.clear()

    def test_override_substitutes_pii_citation_for_matching_jurisdiction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "citations.toml"
            path.write_text(
                "[pii.sg_nric_fin]\n"
                'SG = "Internal Compliance Manual §4.2 — NRIC handling"\n',
                encoding="utf-8",
            )
            os.environ["KAYPOH_CITATIONS_OVERRIDE"] = str(path)
            text = citations.pii_rationale(rule="sg_nric_fin", jurisdiction="SG", matched_text="S1234567D")
            self.assertIn("Internal Compliance Manual §4.2", text)
            self.assertNotIn("PDPA s13", text)
            self.assertTrue(text.startswith('"S1234567D" detected → '))

    def test_override_falls_back_to_builtin_when_jurisdiction_does_not_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "citations.toml"
            path.write_text(
                "[pii.sg_nric_fin]\n"
                'SG = "Internal SG-only override"\n',
                encoding="utf-8",
            )
            os.environ["KAYPOH_CITATIONS_OVERRIDE"] = str(path)
            text = citations.pii_rationale(rule="sg_nric_fin", jurisdiction="US")
            self.assertNotIn("Internal SG-only override", text)
            self.assertIn("PDPA", text)

    def test_override_default_key_applies_when_no_per_jurisdiction_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "citations.toml"
            path.write_text(
                "[mnpi.transaction_codename]\n"
                'default = "Internal Trading Policy §7 — Deal codenames"\n',
                encoding="utf-8",
            )
            os.environ["KAYPOH_CITATIONS_OVERRIDE"] = str(path)
            text = citations.mnpi_rationale(
                rule="transaction_codename", jurisdiction="SG+US", severity="high", matched_text="Project Atlas"
            )
            self.assertIn("Internal Trading Policy §7", text)

    def test_override_respects_low_severity_softener(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "citations.toml"
            path.write_text(
                "[mnpi.material_event]\n"
                'SG = "Internal Trading Policy §3"\n',
                encoding="utf-8",
            )
            os.environ["KAYPOH_CITATIONS_OVERRIDE"] = str(path)
            text = citations.mnpi_rationale(rule="material_event", jurisdiction="SG", severity="low")
            self.assertIn("Internal Trading Policy §3", text)
            self.assertIn("appears public", text)

    def test_missing_configured_override_file_fails_closed(self):
        os.environ["KAYPOH_CITATIONS_OVERRIDE"] = "/no/such/path.toml"
        with self.assertRaises(citations.CitationOverrideError):
            citations.pii_rationale(rule="sg_nric_fin", jurisdiction="SG")

    def test_tenant_override_does_not_leak_to_other_tenant(self):
        with tempfile.TemporaryDirectory() as tmp:
            override_dir = Path(tmp)
            (override_dir / "tenant-a.toml").write_text(
                "[pii.sg_nric_fin]\n"
                'SG = "Tenant A Policy §1"\n',
                encoding="utf-8",
            )
            os.environ["KAYPOH_CITATIONS_OVERRIDE_DIR"] = str(override_dir)

            tenant_a = citations.pii_rationale(
                rule="sg_nric_fin",
                jurisdiction="SG",
                tenant_id="tenant-a",
            )
            tenant_b = citations.pii_rationale(
                rule="sg_nric_fin",
                jurisdiction="SG",
                tenant_id="tenant-b",
            )

            self.assertIn("Tenant A Policy", tenant_a)
            self.assertIn("PDPA", tenant_b)
            self.assertNotIn("Tenant A Policy", tenant_b)

    def test_malformed_tenant_override_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            override_dir = Path(tmp)
            (override_dir / "tenant-a.toml").write_text("[pii.sg_nric_fin\n", encoding="utf-8")
            os.environ["KAYPOH_CITATIONS_OVERRIDE_DIR"] = str(override_dir)

            with self.assertRaises(citations.CitationOverrideError):
                citations.pii_rationale(rule="sg_nric_fin", jurisdiction="SG", tenant_id="tenant-a")


if __name__ == "__main__":
    unittest.main()
