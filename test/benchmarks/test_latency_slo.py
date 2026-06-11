import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_latency_slo_module():
    path = ROOT / "scripts" / "check_latency_slo.py"
    spec = importlib.util.spec_from_file_location("test_benchmark_latency_slo_module", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load latency SLO module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(
    os.environ.get("KAYPOH_RUN_LATENCY_SLO") == "1",
    "set KAYPOH_RUN_LATENCY_SLO=1 to run the opt-in latency SLO gate",
)
class LatencySloBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_latency_slo_module()

    def test_item56_p95_latency_budgets(self):
        config = self.mod.load_budget_config(self.mod.DEFAULT_BUDGET_FILE)
        fixture = self.mod.resolve_fixture(config, os.environ.get("KAYPOH_LATENCY_SLO_FIXTURE"))
        warmups = int(os.environ.get("KAYPOH_LATENCY_SLO_WARMUPS", config.get("default_warmups", 1)))
        repetitions = int(
            os.environ.get("KAYPOH_LATENCY_SLO_REPETITIONS", config.get("default_repetitions", 5))
        )
        cases = self.mod.build_cases(
            config=config,
            fixture_path=fixture,
            surfaces=list(self.mod.VALID_SURFACES),
            profiles=list(self.mod.VALID_PROFILES),
        )

        results = self.mod.run_gate(cases=cases, warmups=warmups, repetitions=repetitions)
        failures = [item for item in results if not item["passed"]]
        self.assertEqual(
            failures,
            [],
            msg="latency SLO failures:\n"
            + self.mod.render_summary(results)
            + "\n"
            + json.dumps(results, indent=2),
        )


if __name__ == "__main__":
    unittest.main()
