import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_latency_slo_module():
    path = ROOT / "scripts" / "check_latency_slo.py"
    spec = importlib.util.spec_from_file_location("test_latency_slo_gate_module", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load latency SLO module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LatencySloGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_latency_slo_module()

    def test_percentile_interpolates_p95(self):
        self.assertEqual(self.mod.percentile([], 0.95), 0.0)
        self.assertEqual(self.mod.percentile([12.3456], 0.95), 12.346)
        self.assertEqual(self.mod.percentile([10.0, 20.0, 30.0, 40.0, 50.0], 0.95), 48.0)

    def test_default_budget_file_defines_four_item56_cases(self):
        config = self.mod.load_budget_config(self.mod.DEFAULT_BUDGET_FILE)
        fixture = self.mod.resolve_fixture(config, None)
        cases = self.mod.build_cases(
            config=config,
            fixture_path=fixture,
            surfaces=list(self.mod.VALID_SURFACES),
            profiles=list(self.mod.VALID_PROFILES),
        )

        self.assertLessEqual(fixture.stat().st_size, 10_000)
        self.assertEqual(
            [(case.key, case.budget_ms) for case in cases],
            [
                ("review.strict", 500.0),
                ("review.audit_grade", 3000.0),
                ("anonymize.strict", 800.0),
                ("anonymize.audit_grade", 4000.0),
            ],
        )

    def test_payloads_target_review_and_anonymize_surfaces(self):
        case = self.mod.LatencyCase(
            surface="review",
            profile="audit_grade",
            budget_ms=3000.0,
            fixture_path=ROOT / "test" / "fixtures" / "latency-corpus" / "1k.txt",
        )
        payload = self.mod._payload_for_case(case, "Memo text")
        self.assertEqual(payload["review_profile"], "audit_grade")
        self.assertEqual(payload["source_jurisdiction"], "SG")
        self.assertFalse(payload["include_suggestions"])
        self.assertNotIn("include_mnpi_scalars", payload)

        anonymize_case = self.mod.LatencyCase(
            surface="anonymize",
            profile="strict",
            budget_ms=800.0,
            fixture_path=case.fixture_path,
        )
        anonymize_payload = self.mod._payload_for_case(anonymize_case, "Memo text")
        self.assertTrue(anonymize_payload["include_mnpi_scalars"])

    def test_render_summary_marks_pass_and_fail(self):
        summary = self.mod.render_summary(
            [
                {
                    "case": "review.strict",
                    "fixture_bytes": 9000,
                    "p50_ms": 10.0,
                    "p95_ms": 20.0,
                    "budget_ms": 500.0,
                    "passed": True,
                },
                {
                    "case": "anonymize.strict",
                    "fixture_bytes": 9000,
                    "p50_ms": 900.0,
                    "p95_ms": 901.0,
                    "budget_ms": 800.0,
                    "passed": False,
                },
            ]
        )
        self.assertIn("review.strict", summary)
        self.assertIn("PASS", summary)
        self.assertIn("anonymize.strict", summary)
        self.assertIn("FAIL", summary)

    def test_resolve_fixture_accepts_absolute_override(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            fixture = Path(tmp_dir) / "sample.txt"
            fixture.write_text("sample text", encoding="utf-8")
            config = {"default_fixture": "does/not/matter.txt", "budgets_ms": {"review.strict": 500.0}}

            self.assertEqual(self.mod.resolve_fixture(config, str(fixture)), fixture.resolve())


if __name__ == "__main__":
    unittest.main()
