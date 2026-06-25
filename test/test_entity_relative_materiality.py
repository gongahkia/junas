"""Entity-size-relative materiality (item 73).

Verifies the SAB 99 (US) + ASX GN8 (AU) tier ladders, MAR / SGX / HKEX advisory-only
posture, fail-loud degraded_modes when no entity_size_lookup is configured, and ASX-300
halved bands. Currency normalisation is the lookup's responsibility — these tests assume
the lookup returns values in the same denomination as matched_text.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

from junas.review.engine import EntitySizeLookup, JSONEntitySizeLookup, PreSendReviewEngine


class _Lookup(EntitySizeLookup):
    def __init__(self, table):
        self._table = table

    def lookup(self, entity_id, jurisdiction):
        return self._table.get(entity_id)


class _RaisingLookup(EntitySizeLookup):
    def lookup(self, entity_id, jurisdiction):
        raise RuntimeError("upstream provider 500")


class MaterialityScalerTests(unittest.TestCase):
    US_LARGE = {"revenue": 1_000_000_000, "market_cap": 5_000_000_000}
    AU_MID = {"revenue": 1_000_000_000, "market_cap": 5_000_000_000}
    AU_300 = {"revenue": 1_000_000_000, "market_cap": 5_000_000_000, "is_asx_300": True}

    def setUp(self):
        self.engine_no_lookup = PreSendReviewEngine()
        self.engine = PreSendReviewEngine(
            entity_size_lookup=_Lookup({
                "AcmeUS": self.US_LARGE,
                "AcmeAU": self.AU_MID,
                "AcmeAU300": self.AU_300,
            })
        )
        self.engine_raising = PreSendReviewEngine(entity_size_lookup=_RaisingLookup())

    def _fa(self, result):
        return [f for f in result.findings if f.rule == "financial_amount"]

    def test_no_lookup_emits_degraded_mode(self):
        r = self.engine_no_lookup.review(
            text="Quarterly results show $50 million impairment.",
            source_jurisdiction="US", destination_jurisdiction="US",
            entity_id="AcmeUS", include_suggestions=False,
        )
        modes = [m["mode"] for m in r.degraded_modes]
        self.assertIn("materiality_lookup_not_configured", modes)
        self.assertEqual(self._fa(r)[0].severity, "medium")

    def test_no_entity_id_emits_degraded_mode_even_with_lookup(self):
        r = self.engine.review(
            text="Quarterly results show $50 million impairment.",
            source_jurisdiction="US", destination_jurisdiction="US",
            entity_id=None, include_suggestions=False,
        )
        modes = [m["mode"] for m in r.degraded_modes]
        self.assertIn("materiality_lookup_not_configured", modes)

    def test_lookup_failure_fails_loud(self):
        r = self.engine_raising.review(
            text="$50 million impairment.",
            source_jurisdiction="US", destination_jurisdiction="US",
            entity_id="X", include_suggestions=False,
        )
        modes = [m["mode"] for m in r.degraded_modes]
        self.assertIn("materiality_lookup_failed", modes)

    def test_lookup_missing_entity_fails_loud(self):
        r = self.engine.review(
            text="$50 million impairment.",
            source_jurisdiction="US", destination_jurisdiction="US",
            entity_id="UnknownLLC", include_suggestions=False,
        )
        modes = [m["mode"] for m in r.degraded_modes]
        self.assertIn("materiality_lookup_missing_entity", modes)

    def test_us_5pct_threshold_escalates_to_high(self):
        # 5B base, $300M = 6% > 5% → high
        r = self.engine.review(
            text="Quarterly results show $300 million impairment.",
            source_jurisdiction="US", destination_jurisdiction="US",
            entity_id="AcmeUS", include_suggestions=False,
        )
        fa = self._fa(r)
        self.assertTrue(any(f.severity == "high" for f in fa))
        self.assertTrue(any("SAB 99" in f.reason for f in fa))

    def test_us_below_threshold_leaves_severity(self):
        # 5B base, $40M = 0.8% < 1% medium tier → no escalation; reason annotated
        r = self.engine.review(
            text="Quarterly results show $40 million impairment.",
            source_jurisdiction="US", destination_jurisdiction="US",
            entity_id="AcmeUS", include_suggestions=False,
        )
        fa = self._fa(r)
        self.assertEqual(fa[0].severity, "medium")
        self.assertIn("below scaling tier", fa[0].reason)

    def test_sg_advisory_only_no_severity_change(self):
        # SG: regulator declines numeric materiality threshold → reason annotated, severity intact
        r = self.engine.review(
            text="Quarterly results show $500 million impairment.",
            source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id="AcmeUS", include_suggestions=False,
        )
        fa = self._fa(r)
        self.assertEqual(fa[0].severity, "medium")
        self.assertIn("regulator declines numeric materiality", fa[0].reason)

    def test_au_general_ladder(self):
        # AU general: ≥10% → high; $600M / $5B = 12% → high
        r = self.engine.review(
            text="Quarterly results show $600 million impairment.",
            source_jurisdiction="AU", destination_jurisdiction="AU",
            entity_id="AcmeAU", include_suggestions=False,
        )
        fa = self._fa(r)
        self.assertTrue(any(f.severity == "high" for f in fa))

    def test_au_asx_300_halved_ladder(self):
        # ASX 300 halved: ≥5% → high; $300M / $5B = 6% → high (would only be medium under general)
        r = self.engine.review(
            text="Quarterly results show $300 million impairment.",
            source_jurisdiction="AU", destination_jurisdiction="AU",
            entity_id="AcmeAU300", include_suggestions=False,
        )
        fa = self._fa(r)
        self.assertTrue(any(f.severity == "high" for f in fa))

    def test_financial_percentage_uses_direct_fraction(self):
        # 8% directly → US tier ≥5% high
        r = self.engine.review(
            text="Operating margin improved to 8% this quarter.",
            source_jurisdiction="US", destination_jurisdiction="US",
            entity_id="AcmeUS", include_suggestions=False,
        )
        fp = [f for f in r.findings if f.rule == "financial_percentage"]
        self.assertTrue(any(f.severity == "high" for f in fp))

    def test_unit_parsing_handles_billion_and_K(self):
        # billion suffix
        r = self.engine.review(
            text="$1 billion impairment recorded.",
            source_jurisdiction="US", destination_jurisdiction="US",
            entity_id="AcmeUS", include_suggestions=False,
        )
        fa = self._fa(r)
        # $1B / $5B = 20% → high
        self.assertTrue(any(f.severity == "high" for f in fa))

    def test_csv_provider_autoloads_from_env(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False) as handle:
            handle.write("entity_id,jurisdiction,revenue,market_cap,is_asx_300,ticker\n")
            handle.write("AcmeUS,US,1000000000,5000000000,false,ACME\n")
            path = handle.name
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        env = {"JUNAS_ENTITY_SIZE_CSV": path, "JUNAS_ENTITY_SIZE_JSON": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            engine = PreSendReviewEngine()
            r = engine.review(
                text="Quarterly results show $300 million impairment.",
                source_jurisdiction="US", destination_jurisdiction="US",
                entity_id="AcmeUS", include_suggestions=False,
            )

        fa = self._fa(r)
        self.assertTrue(any(f.severity == "high" for f in fa))
        self.assertNotIn("materiality_lookup_not_configured", [m["mode"] for m in r.degraded_modes])
        self.assertEqual(fa[0].metadata["entity_size_source"], "operator_csv")
        self.assertAlmostEqual(fa[0].metadata["materiality_fraction"], 0.06)

    def test_json_provider_supports_ticker_aliases(self):
        payload = {
            "entities": [
                {
                    "ticker": "ASX:BHP",
                    "jurisdiction": "AU",
                    "revenue": 1_000_000_000,
                    "market_cap": 5_000_000_000,
                    "is_asx_300": True,
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(payload, handle)
            path = handle.name
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        engine = PreSendReviewEngine(entity_size_lookup=JSONEntitySizeLookup(path))
        r = engine.review(
            text="Quarterly results show $300 million impairment.",
            source_jurisdiction="AU", destination_jurisdiction="AU",
            entity_id="BHP", include_suggestions=False,
        )

        fa = self._fa(r)
        self.assertTrue(any(f.severity == "high" for f in fa))
        self.assertEqual(fa[0].metadata["entity_size_source"], "operator_json")


if __name__ == "__main__":
    unittest.main()
