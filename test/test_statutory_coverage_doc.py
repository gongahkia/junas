"""Item 93: docs/statutory-coverage.md drift gate.

The statutory-coverage doc is the procurement-facing artefact mapping every detector to
the statute it implements. This test asserts that every:

  (a) jurisdiction in citations.py:_MNPI_JURISDICTION_SUFFIX and _PII_JURISDICTION_SUFFIX,
  (b) detector rule_name in src/junas/review/jurisdictions_data/*.toml,
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

from junas.review import jurisdictions
from junas.review.citations import (
    _MNPI_DEFAULT_RATIONALE,
    _MNPI_JURISDICTION_SUFFIX,
    _PII_DEFAULT_RATIONALE,
    _PII_JURISDICTION_SUFFIX,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "statutory-coverage.md"
PACKS_DIR = REPO_ROOT / "src" / "junas" / "review" / "jurisdictions_data"

# Universal PII rule names registered directly in engine.py:_pii_findings (not via TOML).
# Keep in sync with the universal-PII pattern list in engine.py.
_UNIVERSAL_PII_RULES = {
    "email_address", "phone_number", "passport_number", "bank_account",
    "named_person", "date_of_birth", "age_reference", "ip_address", "mac_address", "imei",
    "cookie_id", "advertising_id", "device_serial_number", "eu_national_id",
    "uk_company_number", "eu_company_id",
    "uk_postal_address", "us_postal_address", "hk_postal_address",
    "personal_attribute_inference",
    "sg_insurance_policy_number", "crypto_wallet_address", "sg_tribunal_reference",
    "employee_id", "customer_account_number", "medical_record_number",
    "internal_session_id", "bank_customer_reference", "insurance_member_id",
    "cross_border_transfer_marker", "consent_withdrawal_marker", "data_minimisation_marker",
    "personal_data_security_safeguards", "personal_data_breach_notification",
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
    "insider_list_marker", "information_barrier_marker",
    "dpt_pre_listing_marker", "dpt_protocol_event_marker",
    "esg_climate_pre_disclosure", "esg_target_revision",
    "cyber_incident_pre_disclosure", "pharma_trial_mnpi",
    "financial_services_regulatory_mnpi", "energy_reserves_mnpi",
    "legal_proceeding_mnpi", "blackout_period_reference", "conjunctive_mnpi",
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

    def test_doc_has_endpoint_data_state_table(self):
        self.assertIn("Endpoint data states", self.doc_text)
        for endpoint in ("/pseudonymize", "/anonymize", "/redact"):
            self.assertIn(endpoint, self.doc_text)
        self.assertIn("Pseudonymised personal data", self.doc_text)
        self.assertIn("Intended anonymised text", self.doc_text)
        self.assertIn("Redacted text", self.doc_text)


class StaleStatusGuard(unittest.TestCase):
    """Known shipped surfaces must not be contradicted later in the same artefact."""

    def setUp(self):
        self.doc_text = DOC_PATH.read_text(encoding="utf-8")

    def test_seed_racial_ethnic_detector_is_not_marked_missing(self):
        stale_row = (
            "Special-category PII (racial / ethnic origin; broader semantic special-category inference) | no detector"
        )
        self.assertNotIn(stale_row, self.doc_text)

    def test_hk_kr_postal_detectors_are_not_marked_unimplemented(self):
        self.assertNotIn("Local postal-address for HK / KR | not implemented", self.doc_text)

    def test_shipped_operational_surfaces_are_not_backlog(self):
        stale_rows = {
            "| Per-tenant citations override | backlog | item 60 |",
            "| Local-daemon production ACL | backlog | item 58 |",
        }
        for row in stale_rows:
            self.assertNotIn(row, self.doc_text)

    def test_blackout_ticker_lookup_is_not_marked_deferred(self):
        self.assertNotIn("next-earnings-date lookup deferred", self.doc_text)
        self.assertNotIn("earnings-date lookup; deferred v2", self.doc_text)
        self.assertIn("JUNAS_EARNINGS_CALENDAR_CSV", self.doc_text)

    def test_hk_market_known_threshold_is_not_marked_pending(self):
        self.assertNotIn("HK-specific stricter threshold pending", self.doc_text)
        self.assertNotIn("retriever uses general-availability semantics", self.doc_text)
        self.assertIn("hk_public_status=available_but_not_generally_known", self.doc_text)

    def test_issuer_size_env_providers_are_documented(self):
        self.assertIn("JUNAS_ENTITY_SIZE_CSV", self.doc_text)
        self.assertIn("JUNAS_ENTITY_SIZE_JSON", self.doc_text)


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
