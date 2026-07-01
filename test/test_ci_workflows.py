import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class CiWorkflowTests(unittest.TestCase):
    def test_ci_splits_core_policy_adapter_packaging_docs_and_benchmark_jobs(self):
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        for token in (
            "core-backend-tests:",
            "name: Core backend tests",
            "policy-tests:",
            "name: Policy tests",
            "adapter-smoke-tests:",
            "name: Adapter smoke tests",
            "packaging-tests:",
            "name: Packaging tests",
            "docs-link-tests:",
            "name: Docs link tests",
            "benchmark-gates:",
            "name: Benchmark gates",
        ):
            self.assertIn(token, text)

        for test_path in (
            "test/test_review_endpoints.py",
            "test/test_policy_engine.py",
            "test/test_adapter_smoke.py",
            "test/test_packaging_scripts.py",
            "test/test_docs_links.py",
            "test/test_latency_slo_gate.py",
        ):
            self.assertIn(test_path, text)

        self.assertNotIn("name: Unit tests", text)
        self.assertNotIn('python -m unittest discover -s test -p "test_*.py"', text)

    def test_latency_slo_is_ci_wired_with_artifact_upload(self):
        workflow = ROOT / ".github" / "workflows" / "ci.yml"
        text = workflow.read_text(encoding="utf-8")

        self.assertIn("JUNAS_RUN_LATENCY_SLO", text)
        self.assertIn("test/benchmarks/test_latency_slo.py", text)
        self.assertIn("scripts/check_latency_slo.py --write-report", text)
        self.assertIn("benchmark-gate-reports", text)
        self.assertIn("actions/upload-artifact", text)

    def test_live_latency_job_uses_http_mode(self):
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("uvicorn junas.backend.main:app", text)
        self.assertIn("--base-url http://127.0.0.1:8131", text)
        self.assertIn("test/fixtures/latency-corpus/5k.txt", text)

    def test_docker_smoke_builds_and_hits_ready_and_review(self):
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("Docker smoke", text)
        self.assertIn("docker build -t junas:ci .", text)
        self.assertIn("docker run -d --name junas-ci", text)
        self.assertIn("http://127.0.0.1:8010/ready", text)
        self.assertIn("http://127.0.0.1:8010/review", text)
        self.assertIn("docker logs junas-ci", text)

    def test_staging_latency_job_uses_secret_base_url_and_artifacts(self):
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("Staging deployment latency", text)
        self.assertIn("secrets.JUNAS_LATENCY_SLO_BASE_URL", text)
        self.assertIn("JUNAS_LATENCY_SLO_BEARER_TOKEN", text)
        self.assertIn("staging-latency-reports", text)

    def test_promoted_lock_freshness_check_is_ci_wired(self):
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("Promoted lock freshness", text)
        self.assertIn("fetch-depth: 0", text)
        self.assertIn("scripts/check_promoted_lock_freshness.py --base-ref", text)
        self.assertIn("github.event.pull_request.base.sha", text)
        self.assertIn("github.event.before", text)

    def test_false_negative_risk_gate_is_ci_wired(self):
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("False-negative risk gate", text)
        self.assertIn("Check locked-corpus false-negative risk", text)
        self.assertIn("scripts/check_false_negative_risk.py --base-ref", text)
        self.assertIn("uv run python -m spacy download en_core_web_sm", text)
        self.assertIn("fetch-depth: 0", text)

    def test_precision_risk_gate_is_ci_wired(self):
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("Precision risk gate", text)
        self.assertIn("Check detector precision risk", text)
        self.assertIn("scripts/check_precision_risk.py --base-ref", text)
        self.assertIn("uv run python -m spacy download en_core_web_sm", text)
        self.assertIn("fetch-depth: 0", text)


if __name__ == "__main__":
    unittest.main()
