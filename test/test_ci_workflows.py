import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class CiWorkflowTests(unittest.TestCase):
    def test_latency_slo_is_ci_wired_with_artifact_upload(self):
        workflow = ROOT / ".github" / "workflows" / "ci.yml"
        text = workflow.read_text(encoding="utf-8")

        self.assertIn("KAYPOH_RUN_LATENCY_SLO", text)
        self.assertIn("test.benchmarks.test_latency_slo", text)
        self.assertIn("scripts/check_latency_slo.py --write-report", text)
        self.assertIn("actions/upload-artifact", text)

    def test_live_latency_job_uses_http_mode(self):
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("uvicorn kaypoh.backend.main:app", text)
        self.assertIn("--base-url http://127.0.0.1:8131", text)
        self.assertIn("test/fixtures/latency-corpus/5k.txt", text)

    def test_staging_latency_job_uses_secret_base_url_and_artifacts(self):
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("Staging deployment latency", text)
        self.assertIn("secrets.KAYPOH_LATENCY_SLO_BASE_URL", text)
        self.assertIn("KAYPOH_LATENCY_SLO_BEARER_TOKEN", text)
        self.assertIn("staging-latency-reports", text)


if __name__ == "__main__":
    unittest.main()
