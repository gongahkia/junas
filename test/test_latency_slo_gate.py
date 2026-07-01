import importlib.util
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

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
        self.assertEqual(config["policy_decision_p95_budget_ms"], 25.0)
        self.assertEqual(
            [(case.key, case.budget_ms, case.policy_decision_budget_ms) for case in cases],
            [
                ("review.strict", 500.0, 25.0),
                ("review.audit_grade", 3000.0, 25.0),
                ("anonymize.strict", 800.0, 25.0),
                ("anonymize.audit_grade", 4000.0, 25.0),
            ],
        )

    def test_payloads_target_review_and_anonymize_surfaces(self):
        case = self.mod.LatencyCase(
            surface="review",
            profile="audit_grade",
            budget_ms=3000.0,
            fixture_path=ROOT / "test" / "fixtures" / "latency-corpus" / "1k.txt",
            policy_decision_budget_ms=25.0,
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
            policy_decision_budget_ms=25.0,
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
                    "policy_decision_p95_ms": 2.0,
                    "policy_decision_budget_ms": 25.0,
                    "passed": True,
                },
                {
                    "case": "anonymize.strict",
                    "fixture_bytes": 9000,
                    "p50_ms": 900.0,
                    "p95_ms": 901.0,
                    "budget_ms": 800.0,
                    "policy_decision_p95_ms": 26.0,
                    "policy_decision_budget_ms": 25.0,
                    "passed": False,
                },
            ]
        )
        self.assertIn("review.strict", summary)
        self.assertIn("policy_p95", summary)
        self.assertIn("policy_budget", summary)
        self.assertIn("PASS", summary)
        self.assertIn("anonymize.strict", summary)
        self.assertIn("FAIL", summary)

    def test_resolve_fixture_accepts_absolute_override(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            fixture = Path(tmp_dir) / "sample.txt"
            fixture.write_text("sample text", encoding="utf-8")
            config = {
                "default_fixture": "does/not/matter.txt",
                "policy_decision_p95_budget_ms": 25.0,
                "budgets_ms": {"review.strict": 500.0},
            }

            self.assertEqual(self.mod.resolve_fixture(config, str(fixture)), fixture.resolve())

    def test_live_http_gate_records_mode_and_api_key(self):
        class Handler(BaseHTTPRequestHandler):
            paths: list[str] = []
            api_keys: list[str] = []
            authorizations: list[str] = []

            def do_POST(self):
                size = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(size).decode("utf-8"))
                self.__class__.paths.append(self.path)
                self.__class__.api_keys.append(self.headers.get("X-API-Key", ""))
                self.__class__.authorizations.append(self.headers.get("Authorization", ""))
                body = json.dumps(
                    {
                        "received_profile": payload.get("review_profile"),
                        "timings_ms": {"total": 12.5, "policy_decision_ms": 1.25},
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                return

        with tempfile.TemporaryDirectory() as tmp_dir:
            fixture = Path(tmp_dir) / "sample.txt"
            fixture.write_text("sample text", encoding="utf-8")
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                case = self.mod.LatencyCase(
                    surface="review",
                    profile="strict",
                    budget_ms=500.0,
                    fixture_path=fixture,
                    policy_decision_budget_ms=25.0,
                )
                results = self.mod.run_live_http_gate(
                    cases=[case],
                    warmups=0,
                    repetitions=2,
                    base_url=base_url,
                    api_key="test-key",
                    bearer_token="bearer-test",
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(results[0]["mode"], "live_http")
        self.assertEqual(results[0]["base_url"], base_url)
        self.assertEqual(results[0]["mean_server_total_ms"], 12.5)
        self.assertEqual(results[0]["mean_policy_decision_ms"], 1.25)
        self.assertEqual(results[0]["policy_decision_p95_ms"], 1.25)
        self.assertTrue(results[0]["policy_decision_passed"])
        self.assertEqual(Handler.paths, ["/review", "/review"])
        self.assertEqual(Handler.api_keys, ["test-key", "test-key"])
        self.assertEqual(Handler.authorizations, ["Bearer bearer-test", "Bearer bearer-test"])

    def test_in_process_gate_records_policy_decision_overhead(self):
        fixture = ROOT / "test" / "fixtures" / "latency-corpus" / "1k.txt"
        case = self.mod.LatencyCase(
            surface="review",
            profile="strict",
            budget_ms=500.0,
            fixture_path=fixture,
            policy_decision_budget_ms=25.0,
        )

        results = self.mod.run_gate(cases=[case], warmups=0, repetitions=1)

        self.assertEqual(results[0]["mode"], "in_process")
        self.assertIsNotNone(results[0]["mean_policy_decision_ms"])
        self.assertIsNotNone(results[0]["policy_decision_p95_ms"])
        self.assertLessEqual(results[0]["policy_decision_p95_ms"], 25.0)
        self.assertTrue(results[0]["policy_decision_passed"])

    def test_live_base_url_can_come_from_environment(self):
        with mock.patch.dict(os.environ, {"JUNAS_LATENCY_SLO_BASE_URL": "https://staging.example"}, clear=False):
            self.assertEqual(self.mod.resolve_live_base_url(None), "https://staging.example")

        self.assertEqual(self.mod.resolve_live_base_url("http://127.0.0.1:8131"), "http://127.0.0.1:8131")


if __name__ == "__main__":
    unittest.main()
