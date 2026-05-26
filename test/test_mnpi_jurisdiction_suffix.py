"""Item 94: MNPI jurisdiction-suffix wiring audit.

For every MNPI rule × every in-scope destination jurisdiction, the suggestion rationale
returned by engine.review(include_suggestions=True) must carry the statute suffix from
citations.py:_MNPI_JURISDICTION_SUFFIX. The suffix is the statute-cited reference that
makes the artefact forwardable to internal audit; if the wiring drops it for any rule,
the procurement-grade defensibility claim collapses for that rule.

This audit also covers the contingent_mnpi_language and tipping_language rules added by
items 95+96, plus cross-jurisdiction routing (source=SG, destination=US) which must carry
BOTH statute suffixes.
"""

import unittest

from kaypoh.review.citations import _MNPI_JURISDICTION_SUFFIX, mnpi_rationale
from kaypoh.review.engine import PreSendReviewEngine


# canonical minimal text that triggers each MNPI rule. Each is intentionally simple so we
# can isolate the rule and confirm the suffix lands on its suggestion, without other rules
# competing for the same finding-id slot.
_RULE_FIXTURES: dict[str, str] = {
    "material_event": "There will be an acquisition of TargetCo next month.",
    "nonpublic_marker": "This material is strictly confidential — do not distribute.",
    "transaction_codename": "Project Sapphire is the codename in use internally.",
    "definitive_agreement": "Counsel circulated the Share Purchase Agreement on Tuesday.",
    "material_adverse_change": "The MAC clause threshold was breached during diligence.",
    "embargo_marker": "Embargoed until the signing date of 15 October.",
    "financial_amount": "Total consideration of SGD 250 million was agreed.",
    "financial_percentage": "Margin expansion of 25% is forecast.",
    "large_number": "Portfolio holds 50,000,000 shares of the issuer.",
    "contingent_mnpi_language": "The transaction is subject to board approval before announcement.",
    "tipping_language": "Please share with the analyst team before close of business.",
}

# all in-scope destination jurisdictions (matches the §Jurisdiction Coverage table).
_DESTINATION_JURISDICTIONS = ["SG", "US", "UK", "EU", "MY", "ID", "TH", "PH", "VN", "HK", "AU", "JP", "KR"]


class MnpiSuffixCatalogueTests(unittest.TestCase):
    """Coverage check on citations.py: every in-scope juris must define a MNPI suffix."""

    def test_every_destination_jurisdiction_has_mnpi_suffix(self):
        for code in _DESTINATION_JURISDICTIONS:
            self.assertIn(code, _MNPI_JURISDICTION_SUFFIX,
                          f"{code}: no MNPI suffix in citations.py:_MNPI_JURISDICTION_SUFFIX")
            self.assertTrue(_MNPI_JURISDICTION_SUFFIX[code].strip(),
                            f"{code}: MNPI suffix is empty")


class MnpiRationaleSuffixTests(unittest.TestCase):
    """Direct test of citations.py:mnpi_rationale(): the suffix must be appended for every
    in-scope (rule × jurisdiction) pair. Catches suffix-dictionary drift independently of
    the engine plumbing."""

    def test_every_rule_carries_juris_suffix_directly(self):
        for rule in _RULE_FIXTURES:
            for juris in _DESTINATION_JURISDICTIONS:
                rationale = mnpi_rationale(
                    rule=rule, jurisdiction=juris,
                    severity="medium", matched_text="x",
                )
                expected = _MNPI_JURISDICTION_SUFFIX[juris]
                self.assertIn(expected, rationale,
                              f"{rule!r} × {juris}: suffix {expected!r} missing from rationale: {rationale!r}")


class EnginePipelineSuffixTests(unittest.TestCase):
    """End-to-end test: engine.review(include_suggestions=True) must carry the suffix all
    the way through finding → suggestion.rationale for every (rule × destination)."""

    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _suggestion_rationales_for_rule(self, text: str, source: str, destination: str, rule: str) -> list[str]:
        result = self.engine.review(
            text=text,
            source_jurisdiction=source,
            destination_jurisdiction=destination,
            entity_id=None,
            include_suggestions=True,
            document_type="generic",
            review_profile="strict",
        )
        # match findings to suggestions via finding_id.
        finding_ids = {f.id for f in result.findings if f.rule == rule}
        return [s.rationale for s in result.suggestions if s.finding_id in finding_ids]

    def test_each_rule_x_destination_carries_suffix_end_to_end(self):
        for rule, text in _RULE_FIXTURES.items():
            for juris in _DESTINATION_JURISDICTIONS:
                rationales = self._suggestion_rationales_for_rule(
                    text=text, source=juris, destination=juris, rule=rule,
                )
                self.assertTrue(rationales,
                                f"{rule!r} × {juris}: no suggestion rationale was generated "
                                f"(rule may not have fired on the fixture)")
                expected = _MNPI_JURISDICTION_SUFFIX[juris]
                for r in rationales:
                    self.assertIn(expected, r,
                                  f"{rule!r} × {juris}: suffix {expected!r} missing from "
                                  f"suggestion.rationale: {r!r}")

    def test_cross_jurisdiction_carries_both_suffixes(self):
        # source=SG, destination=US must include both SG SFA suffix AND US Reg FD suffix.
        # _pack_scope joins with "+" and citations.py splits on "+" when looking up suffixes.
        for rule, text in _RULE_FIXTURES.items():
            rationales = self._suggestion_rationales_for_rule(
                text=text, source="SG", destination="US", rule=rule,
            )
            self.assertTrue(rationales, f"{rule!r}: no suggestion generated for SG→US")
            sg_suffix = _MNPI_JURISDICTION_SUFFIX["SG"]
            us_suffix = _MNPI_JURISDICTION_SUFFIX["US"]
            for r in rationales:
                self.assertIn(sg_suffix, r, f"{rule!r} SG→US: SG suffix missing: {r!r}")
                self.assertIn(us_suffix, r, f"{rule!r} SG→US: US suffix missing: {r!r}")

    def test_amplified_contingent_finding_keeps_suffix(self):
        # Item 95: contingent_mnpi_language fires at low standalone, escalates to medium when
        # adjacent to a deal substrate. The escalated finding still has to carry the suffix —
        # severity escalation must not nuke the citation.
        text = "Project Sapphire is under consideration by the board."
        rationales = self._suggestion_rationales_for_rule(
            text=text, source="SG", destination="SG", rule="contingent_mnpi_language",
        )
        self.assertTrue(rationales)
        sg_suffix = _MNPI_JURISDICTION_SUFFIX["SG"]
        for r in rationales:
            self.assertIn(sg_suffix, r,
                          f"amplified contingent finding dropped suffix: {r!r}")

    def test_amplified_tipping_finding_keeps_suffix(self):
        # Item 96: same invariant for tipping_language.
        text = "Closing date 15 October. Please share with the analyst team before then."
        rationales = self._suggestion_rationales_for_rule(
            text=text, source="SG", destination="SG", rule="tipping_language",
        )
        self.assertTrue(rationales)
        sg_suffix = _MNPI_JURISDICTION_SUFFIX["SG"]
        for r in rationales:
            self.assertIn(sg_suffix, r,
                          f"amplified tipping finding dropped suffix: {r!r}")


class OverrideHookStillRespected(unittest.TestCase):
    """When KAYPOH_CITATIONS_OVERRIDE substitutes a rule's rationale, the override fully
    replaces the built-in base + suffix (per citations.py contract). Confirm the audit
    above does not break that override path."""

    def test_override_replaces_base_and_suffix(self):
        import os
        import tempfile
        from pathlib import Path

        from kaypoh.review import citations

        with tempfile.TemporaryDirectory() as td:
            override_path = Path(td) / "overrides.toml"
            override_path.write_text(
                '[mnpi.transaction_codename]\n'
                'SG = "Internal Trading Policy §7 — Deal codenames"\n',
                encoding="utf-8",
            )
            citations._CITATIONS_OVERRIDE_CACHE.clear()
            prev = os.environ.get("KAYPOH_CITATIONS_OVERRIDE")
            try:
                os.environ["KAYPOH_CITATIONS_OVERRIDE"] = str(override_path)
                rationale = mnpi_rationale(
                    rule="transaction_codename", jurisdiction="SG",
                    severity="medium", matched_text="Project X",
                )
                self.assertIn("Internal Trading Policy", rationale)
                # the SG suffix should NOT appear when the override has substituted the base.
                self.assertNotIn(_MNPI_JURISDICTION_SUFFIX["SG"], rationale)
            finally:
                if prev is None:
                    os.environ.pop("KAYPOH_CITATIONS_OVERRIDE", None)
                else:
                    os.environ["KAYPOH_CITATIONS_OVERRIDE"] = prev
                citations._CITATIONS_OVERRIDE_CACHE.clear()


if __name__ == "__main__":
    unittest.main()
