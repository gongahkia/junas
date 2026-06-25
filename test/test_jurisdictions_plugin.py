"""Customers can drop a `*.toml` into JUNAS_JURISDICTION_PACKS_DIR to add or override packs."""

import os
import tempfile
import unittest
from pathlib import Path

from junas.review import jurisdictions


class JurisdictionsPluginTests(unittest.TestCase):
    def setUp(self):
        self._orig_env = os.environ.get("JUNAS_JURISDICTION_PACKS_DIR")

    def tearDown(self):
        if self._orig_env is None:
            os.environ.pop("JUNAS_JURISDICTION_PACKS_DIR", None)
        else:
            os.environ["JUNAS_JURISDICTION_PACKS_DIR"] = self._orig_env
        jurisdictions.reload_registry()

    def test_builtin_packs_load_from_toml(self):
        jurisdictions.reload_registry()
        self.assertIn("SG", jurisdictions.RULE_PACKS)
        self.assertIn("US", jurisdictions.RULE_PACKS)
        self.assertEqual(jurisdictions.JURISDICTION_ALIASES.get("SINGAPORE"), "SG")

    def test_customer_pack_dir_registers_new_jurisdiction(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack_path = Path(tmp) / "MY.toml"
            pack_path.write_text(
                'code = "MY"\n'
                'label = "Malaysia"\n'
                'pii_rules = ["MY_PDPA_PERSONAL_DATA"]\n'
                'mnpi_rules = ["MY_SC_INSIDE_INFORMATION"]\n'
                'references = ["Malaysia Personal Data Protection Act 2010"]\n'
                'aliases = ["MY", "MALAYSIA"]\n',
                encoding="utf-8",
            )
            os.environ["JUNAS_JURISDICTION_PACKS_DIR"] = str(tmp)
            jurisdictions.reload_registry()
            self.assertIn("MY", jurisdictions.RULE_PACKS)
            packs = jurisdictions.resolve_rule_packs("MY", "MY")
            self.assertEqual(packs[0].label, "Malaysia")
            self.assertEqual(packs[0].pii_rules, ("MY_PDPA_PERSONAL_DATA",))

    def test_customer_pack_overrides_builtin_with_same_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack_path = Path(tmp) / "SG.toml"
            pack_path.write_text(
                'code = "SG"\n'
                'label = "Singapore (internal compliance pack)"\n'
                'pii_rules = ["INTERNAL_SG_PII_POLICY"]\n'
                'mnpi_rules = ["INTERNAL_SG_MNPI_POLICY"]\n'
                'references = ["Internal Compliance Manual 2026 §4.2"]\n'
                'aliases = ["SG"]\n',
                encoding="utf-8",
            )
            os.environ["JUNAS_JURISDICTION_PACKS_DIR"] = str(tmp)
            jurisdictions.reload_registry()
            pack = jurisdictions.RULE_PACKS["SG"]
            self.assertEqual(pack.label, "Singapore (internal compliance pack)")
            self.assertEqual(pack.pii_rules, ("INTERNAL_SG_PII_POLICY",))

    def test_malformed_customer_pack_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack_path = Path(tmp) / "broken.toml"
            pack_path.write_text("this is not valid toml [\n", encoding="utf-8")
            os.environ["JUNAS_JURISDICTION_PACKS_DIR"] = str(tmp)
            jurisdictions.reload_registry()
            # built-in SG still loads even if a customer pack is malformed.
            self.assertIn("SG", jurisdictions.RULE_PACKS)


if __name__ == "__main__":
    unittest.main()
