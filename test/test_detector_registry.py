import unittest

from kaypoh.review.detectors import DetectorContext, DetectorRegistry
from kaypoh.review.engine import PreSendReviewEngine


class DetectorRegistryTests(unittest.TestCase):
    def test_run_preserves_registration_order_and_offsets(self):
        registry = DetectorRegistry()
        calls: list[tuple[str, int]] = []

        def first(ctx: DetectorContext, idx_start: int) -> list[tuple[str, int]]:
            calls.append((ctx.text, idx_start))
            return [("first", idx_start)]

        def second(ctx: DetectorContext, idx_start: int) -> list[tuple[str, int]]:
            calls.append(("second", idx_start))
            return [("second", idx_start), ("second", idx_start + 1)]

        registry.register(name="first", family="test", detect=first)
        registry.register(name="second", family="test", detect=second)
        result = registry.run(
            DetectorContext(text="doc", packs=(), jurisdiction="EU", legal_basis="basis"),
            idx_start=7,
        )

        self.assertEqual(calls, [("doc", 7), ("second", 8)])
        self.assertEqual(result, [("first", 7), ("second", 8), ("second", 9)])
        self.assertEqual(registry.names(), ("first", "second"))

    def test_duplicate_names_fail_fast(self):
        registry = DetectorRegistry()
        registry.register(name="first", family="test", detect=lambda _ctx, _idx: [])
        with self.assertRaises(ValueError):
            registry.register(name="first", family="test", detect=lambda _ctx, _idx: [])

    def test_non_list_detector_output_fails_fast(self):
        registry = DetectorRegistry()
        registry.register(name="bad", family="test", detect=lambda _ctx, _idx: ())  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            registry.run(DetectorContext(text="doc", packs=(), jurisdiction="EU", legal_basis="basis"))


class EngineDetectorRegistryWiringTests(unittest.TestCase):
    def test_engine_exposes_ordered_pii_registries(self):
        engine = PreSendReviewEngine()
        self.assertEqual(
            engine.pii_pre_named_registry.names(),
            ("core_identifier_fields", "address_signals", "us_driver_license", "sg_wedge_remainder"),
        )
        self.assertEqual(
            engine.pii_post_named_registry.names(),
            ("semantic_pii_fallback", "special_category_pii", "minor_data_reference"),
        )

    def test_registered_pii_families_remain_active(self):
        result = PreSendReviewEngine().review(
            text="DOB: 14/02/1988\nEthnicity: Han Chinese",
            source_jurisdiction="EU",
            destination_jurisdiction="EU",
            entity_id=None,
            include_suggestions=False,
        )
        rules = {finding.rule for finding in result.findings}
        self.assertIn("date_of_birth", rules)
        self.assertIn("racial_ethnic_origin", rules)


if __name__ == "__main__":
    unittest.main()
