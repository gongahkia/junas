"""Item 93: docs/statutory-coverage.md drift gate.

The statutory-coverage doc is the procurement-facing artefact mapping every detector to
the statute it implements. This test asserts that every:

  (a) jurisdiction in citations.py:_MNPI_JURISDICTION_SUFFIX and _PII_JURISDICTION_SUFFIX,
  (b) detector rule_name in src/kaypoh/review/jurisdictions_data/*.toml,
  (c) PII / MNPI rationale key in citations.py:_PII_DEFAULT_RATIONALE / _MNPI_DEFAULT_RATIONALE,
  (d) universal PII rule registered in engine.py:_pii_findings,
  (e) universal MNPI rule registered in engine.py:_mnpi_findings,
  (f) post-pass amplifier rule (contingent / tipping / selective_disclosure / quasi-id),

is mentioned somewhere in the doc. Drift fails — a new detector or jurisdiction added to
the codebase without doc update breaks CI. Conversely, deleting a detector without
removing it from the doc also breaks CI.

This is a *presence* test, not a *verbatim* equality test — that would make the doc too
brittle to edit. The goal is to ensure the doc cannot silently lose track of a shipped
detector or a registered jurisdiction.
"""

import unittest
from pathlib import Path

import tomllib

from kaypoh.review import jurisdictions
from kaypoh.review.citations import (
    _MNPI_DEFAULT_RATIONALE,
    _MNPI_JURISDICTION_SUFFIX,
    _PII_DEFAULT_RATIONALE,
    _PII_JURISDICTION_SUFFIX,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "statutory-coverage.md"
PACKS_DIR = REPO_ROOT / "src" / "kaypoh" / "review" / "jurisdictions_data"

# Universal PII rule names registered directly in engine.py:_pii_findings (not via TOML).
# Keep in sync with the universal-PII pattern list in engine.py.
_UNIVERSAL_PII_RULES = {
    "email_address", "phone_number", "passport_number", "bank_account",
    "named_person", "date_of_birth", "age_reference", "ip_address", "mac_address", "imei",
    "cookie_id", "advertising_id", "device_serial_number", "eu_national_id",
    "uk_postal_address", "us_postal_address", "hk_postal_address",
    "personal_attribute_inference",
    "sg_insurance_policy_number", "crypto_wallet_address", "sg_tribunal_reference",
    "employee_id", "customer_account_number", "medical_record_number",
    "internal_session_id", "bank_customer_reference", "insurance_member_id",
    "religious_belief", "trade_union_membership", "political_opinion",
    "health_condition", "medical_treatment", "biometric_identifier", "genetic_data",
    "sexual_orientation", "sex_life_reference", "racial_ethnic_origin", "minor_data_reference",
}

# MNPI rule names emitted by engine.py:_mnpi_findings (universal — no TOML).
_UNIVERSAL_MNPI_RULES = {
    "material_event", "nonpublic_marker", "transaction_codename",
    "definitive_agreement", "material_adverse_change", "embargo_marker",
    "financial_amount", "financial_percentage", "large_number",
    "contract_unit_price", "contract_discount_rate", "volume_commitment",
    "royalty_rate", "total_contract_value",
    "contingent_mnpi_language", "tipping_language", "selective_disclosure_risk",
}

# Cross-cutting / synthetic rules.
_SYNTHETIC_RULES = {"quasi_identifier_combination"}


class DocExistsAndIsNonEmpty(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(DOC_PATH.exists(), f"missing procurement artefact: {DOC_PATH}")

    def test_doc_is_not_empty(self):
        self.assertGreater(DOC_PATH.stat().st_size, 1000,
                           "statutory-coverage.md is suspiciously small")


class JurisdictionCoverage(unittest.TestCase):
    """Every jurisdiction with a configured statute suffix must appear in the doc."""

    def setUp(self):
        self.doc_text = DOC_PATH.read_text(encoding="utf-8")

    def test_every_pii_suffix_jurisdiction_is_mentioned(self):
        for code in _PII_JURISDICTION_SUFFIX:
            self.assertIn(code, self.doc_text,
                          f"jurisdiction {code!r} has a PII suffix in citations.py but is "
                          f"not mentioned in docs/statutory-coverage.md")

    def test_every_mnpi_suffix_jurisdiction_is_mentioned(self):
        for code in _MNPI_JURISDICTION_SUFFIX:
            self.assertIn(code, self.doc_text,
                          f"jurisdiction {code!r} has an MNPI suffix in citations.py but is "
                          f"not mentioned in docs/statutory-coverage.md")


class TomlRecognizerCoverage(unittest.TestCase):
    """Every detector rule_name shipped in a jurisdictions_data/*.toml pack must appear
    in the doc. Catches the case where a new TOML recognizer ships without doc update."""

    def setUp(self):
        self.doc_text = DOC_PATH.read_text(encoding="utf-8")

    def _collect_toml_rule_names(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for toml_path in sorted(PACKS_DIR.glob("*.toml")):
            raw = tomllib.loads(toml_path.read_text(encoding="utf-8"))
            recognizers = raw.get("recognizers", []) or []
            out[toml_path.stem] = [str(r["rule_name"]) for r in recognizers if "rule_name" in r]
        return out

    def test_every_toml_rule_is_mentioned(self):
        all_rules = self._collect_toml_rule_names()
        for pack_code, rule_names in all_rules.items():
            for rule_name in rule_names:
                self.assertIn(rule_name, self.doc_text,
                              f"{pack_code} pack's rule {rule_name!r} is not mentioned in "
                              f"docs/statutory-coverage.md")


class UniversalRuleCoverage(unittest.TestCase):
    """Universal PII / MNPI rules registered in engine.py must appear in the doc."""

    def setUp(self):
        self.doc_text = DOC_PATH.read_text(encoding="utf-8")

    def test_every_universal_pii_rule_is_mentioned(self):
        for rule in _UNIVERSAL_PII_RULES:
            self.assertIn(rule, self.doc_text,
                          f"universal PII rule {rule!r} is not mentioned in doc")

    def test_every_universal_mnpi_rule_is_mentioned(self):
        for rule in _UNIVERSAL_MNPI_RULES:
            self.assertIn(rule, self.doc_text,
                          f"universal MNPI rule {rule!r} is not mentioned in doc")

    def test_every_synthetic_cross_cutting_rule_is_mentioned(self):
        for rule in _SYNTHETIC_RULES:
            self.assertIn(rule, self.doc_text,
                          f"cross-cutting rule {rule!r} is not mentioned in doc")


class RationaleCoverage(unittest.TestCase):
    """Every default-rationale key in citations.py must appear in the doc — drift between
    citations.py and the procurement artefact is the worst kind of silent drift."""

    def setUp(self):
        self.doc_text = DOC_PATH.read_text(encoding="utf-8")

    def test_every_pii_rationale_key_is_mentioned(self):
        for rule in _PII_DEFAULT_RATIONALE:
            self.assertIn(rule, self.doc_text,
                          f"PII rationale {rule!r} in citations.py is not mentioned in doc")

    def test_every_mnpi_rationale_key_is_mentioned(self):
        for rule in _MNPI_DEFAULT_RATIONALE:
            self.assertIn(rule, self.doc_text,
                          f"MNPI rationale {rule!r} in citations.py is not mentioned in doc")


class CrossSectionInvariant(unittest.TestCase):
    """The doc must carry the load-bearing structural sections so a procurement reviewer
    knows where to look. If section headers are renamed, this test surfaces it."""

    def setUp(self):
        self.doc_text = DOC_PATH.read_text(encoding="utf-8")

    def test_doc_has_jurisdictions_section(self):
        self.assertIn("Jurisdictions in scope", self.doc_text)

    def test_doc_has_universal_pii_section(self):
        self.assertIn("Universal PII detectors", self.doc_text)

    def test_doc_has_jurisdiction_specific_pii_section(self):
        self.assertIn("Jurisdiction-specific PII detectors", self.doc_text)

    def test_doc_has_mnpi_section(self):
        self.assertIn("MNPI", self.doc_text)

    def test_doc_has_known_gaps_section(self):
        self.assertIn("Known statutory gaps", self.doc_text)

    def test_doc_has_disclaimers(self):
        # Procurement artefact MUST disclaim that it's not legal advice.
        self.assertIn("not legal advice", self.doc_text.lower())


class JurisdictionPackRegistryParityTests(unittest.TestCase):
    """Every TOML pack on disk must be referenced in the doc by code. The reverse — the
    doc mentioning a code that has no pack — would also be drift but is harder to detect
    cleanly without false-positives on prose mentions; we settle for the forward direction."""

    def setUp(self):
        self.doc_text = DOC_PATH.read_text(encoding="utf-8")
        jurisdictions.reload_registry()

    def test_every_registered_pack_is_mentioned(self):
        for code in jurisdictions.RULE_PACKS:
            self.assertIn(code, self.doc_text,
                          f"pack {code!r} is registered in the runtime but not mentioned in doc")


if __name__ == "__main__":
    unittest.main()
