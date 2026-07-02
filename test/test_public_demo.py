import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from junas.backend import main

DEMO_ENV = (
    "JUNAS_PUBLIC_DEMO_ENABLED",
    "JUNAS_PUBLIC_DEMO_BODY_MAX_BYTES",
    "JUNAS_PUBLIC_DEMO_TEXT_MAX_CHARS",
    "JUNAS_PUBLIC_DEMO_RATE_LIMIT",
    "JUNAS_PUBLIC_DEMO_RATE_LIMIT_WINDOW_SECONDS",
    "JUNAS_REVIEW_PERSIST",
)


class PublicDemoTests(unittest.TestCase):
    def setUp(self):
        self._env = {key: os.environ.get(key) for key in DEMO_ENV}
        for key in DEMO_ENV:
            os.environ.pop(key, None)
        main._state.pop("public_demo_rate_limit", None)

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        main._state.pop("public_demo_rate_limit", None)

    def _enable_demo(self):
        os.environ["JUNAS_PUBLIC_DEMO_ENABLED"] = "1"
        main._state.pop("public_demo_rate_limit", None)

    def test_public_demo_is_disabled_by_default(self):
        with TestClient(main.app) as client:
            self.assertEqual(client.get("/demo").status_code, 404)
            self.assertEqual(client.post("/demo/review", json={"text": "safe"}).status_code, 404)

    def test_public_demo_page_declares_deterministic_non_persistent_scope(self):
        self._enable_demo()
        with TestClient(main.app) as client:
            response = client.get("/demo")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        html = response.text
        for token in (
            "Junas deterministic demo",
            "Strict-profile demo",
            "No LLM, no public evidence, no persistence",
            "Use synthetic text only",
            "SG NRIC prompt",
            "M&amp;A MNPI email",
            "Clean internal note",
            "/demo/review",
            "Profile",
            "strict deterministic",
        ):
            self.assertIn(token, html)

    def test_public_demo_docs_describe_gates_and_limits(self):
        doc = (main.PROJECT_ROOT / "docs" / "public-demo.md").read_text(encoding="utf-8")
        index = (main.PROJECT_ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        for token in (
            "disabled by default",
            "JUNAS_PUBLIC_DEMO_ENABLED=1",
            "JUNAS_REVIEW_PERSIST=0",
            "PIPELINE_LAYERS=\"\"",
            "GET /demo",
            "POST /demo/review",
            "forces `review_profile=\"strict\"`",
            "fresh `PreSendReviewEngine()`",
            "bypasses review-session persistence",
            "JUNAS_PUBLIC_DEMO_BODY_MAX_BYTES",
            "JUNAS_PUBLIC_DEMO_TEXT_MAX_CHARS",
            "JUNAS_PUBLIC_DEMO_RATE_LIMIT",
            "synthetic, non-confidential text only",
            "does not include a live hosted URL",
        ):
            self.assertIn(token, doc)
        self.assertIn("public-demo.md", index)

    def test_public_demo_hosted_artifacts_use_local_sku_and_auth_gate(self):
        dockerfile = (main.PROJECT_ROOT / "Dockerfile.public-demo").read_text(encoding="utf-8")
        deploy_script = (main.PROJECT_ROOT / "scripts" / "deploy_hf_space.sh").read_text(encoding="utf-8")
        space_readme = (main.PROJECT_ROOT / "deploy" / "huggingface-space" / "README.md").read_text(
            encoding="utf-8"
        )
        doc = (main.PROJECT_ROOT / "docs" / "public-demo.md").read_text(encoding="utf-8")

        for token in (
            "JUNAS_PUBLIC_DEMO_ENABLED=1",
            "JUNAS_REVIEW_PERSIST=0",
            "JUNAS_PUBLIC_EVIDENCE_ENABLED=0",
            "JUNAS_LLM_ENABLED=0",
            "JUNAS_LLM_HELPERS_ENABLED=0",
            "uv sync --frozen --no-dev",
            "JUNAS_API_KEY=$(uv run python -c",
        ):
            self.assertIn(token, dockerfile)
        self.assertNotIn("--extra server", dockerfile)
        for token in (
            "--repo-type space",
            "--space-sdk docker",
            "Dockerfile.public-demo",
            "deploy/huggingface-space/README.md",
            "HF_TOKEN",
        ):
            self.assertIn(token, deploy_script)
        for token in ("sdk: docker", "app_port: 8000", "suggested_hardware: cpu-basic", "no review persistence"):
            self.assertIn(token, space_readme)
        for token in (
            "CPU Basic is listed as free",
            "sleep after 48 hours of inactivity",
            "Web check performed 2026-07-02",
            "Render Free web services are viable for FastAPI",
            "spin down after 15 minutes without inbound traffic",
            "Railway Serverless can sleep a service after more than 10 minutes",
            "return `502 Bad Gateway`",
            "does not include a live hosted URL",
        ):
            self.assertIn(token, doc)

    def test_hf_space_deploy_script_fails_fast_without_auth(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_hf = Path(tmp) / "hf"
            fake_hf.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = auth ] && [ \"$2\" = whoami ]; then echo 'Not logged in'; exit 0; fi\n"
                "echo unexpected hf call \"$@\" >&2\n"
                "exit 99\n",
                encoding="utf-8",
            )
            fake_hf.chmod(0o755)
            env = dict(os.environ)
            env.pop("HF_TOKEN", None)
            env["PATH"] = f"{tmp}:{env['PATH']}"

            result = subprocess.run(
                [str(main.PROJECT_ROOT / "scripts" / "deploy_hf_space.sh"), "gongahkia/junas-demo"],
                cwd=str(main.PROJECT_ROOT),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertEqual(result.returncode, 69, result)
        self.assertIn("hf auth required", result.stderr)

    def test_hf_space_deploy_script_stages_public_demo_payload_with_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "hf.log"
            fake_hf = Path(tmp) / "hf"
            fake_hf.write_text(
                "#!/bin/sh\n"
                "echo \"$@\" >> \"$HF_FAKE_LOG\"\n"
                "if [ \"$1\" = repo ] && [ \"$2\" = create ]; then exit 0; fi\n"
                "if [ \"$1\" = upload ]; then\n"
                "  test -f \"$3/Dockerfile\" || exit 11\n"
                "  test -f \"$3/README.md\" || exit 12\n"
                "  test -f \"$3/pyproject.toml\" || exit 13\n"
                "  test -f \"$3/uv.lock\" || exit 14\n"
                "  test -f \"$3/config.toml\" || exit 15\n"
                "  test -d \"$3/src/junas\" || exit 16\n"
                "  grep -q 'JUNAS_PUBLIC_DEMO_ENABLED=1' \"$3/Dockerfile\" || exit 17\n"
                "  grep -q 'sdk: docker' \"$3/README.md\" || exit 18\n"
                "  exit 0\n"
                "fi\n"
                "exit 99\n",
                encoding="utf-8",
            )
            fake_hf.chmod(0o755)
            env = dict(os.environ)
            env["HF_TOKEN"] = "test-token"
            env["HF_FAKE_LOG"] = str(log_path)
            env["PATH"] = f"{tmp}:{env['PATH']}"

            result = subprocess.run(
                [str(main.PROJECT_ROOT / "scripts" / "deploy_hf_space.sh"), "gongahkia/junas-demo"],
                cwd=str(main.PROJECT_ROOT),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            log = log_path.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result)
        self.assertIn("https://huggingface.co/spaces/gongahkia/junas-demo", result.stdout)
        self.assertIn("repo create gongahkia/junas-demo --repo-type space --space-sdk docker --exist-ok", log)
        self.assertIn("upload gongahkia/junas-demo", log)

    def test_public_demo_review_is_unauthenticated_strict_and_non_persistent(self):
        self._enable_demo()
        os.environ["JUNAS_REVIEW_PERSIST"] = "1"
        payload = {
            "text": (
                "Project Raven will acquire GlobalTech for USD 2.5 billion before announcement. "
                "Send Dr Jane Tan S1234567D the draft."
            ),
            "source_jurisdiction": "SG",
            "destination_jurisdiction": "US",
            "review_profile": "audit_grade",
        }
        with patch("junas.backend.main.start_review_session") as start_review_session:
            with TestClient(main.app) as client:
                response = client.post("/demo/review", json=payload)

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["review_profile"], "strict")
        self.assertEqual(body["document_type"], "genai_prompt")
        self.assertFalse(body["send_allowed"])
        self.assertEqual(body["policy_decision"]["decision"], "block")
        self.assertIsNone(body["public_evidence"])
        self.assertIsNone(body["llm_adjudication"])
        self.assertEqual(body["privacy_ledger"], [])
        self.assertTrue(any(finding["category"] == "PII" for finding in body["findings"]))
        self.assertTrue(any(finding["category"] == "MNPI" for finding in body["findings"]))
        start_review_session.assert_not_called()

    def test_public_demo_enforces_body_and_text_caps(self):
        self._enable_demo()
        os.environ["JUNAS_PUBLIC_DEMO_BODY_MAX_BYTES"] = "512"
        os.environ["JUNAS_PUBLIC_DEMO_TEXT_MAX_CHARS"] = "100"
        with TestClient(main.app) as client:
            body_response = client.post("/demo/review", json={"text": "x" * 1000})
            text_response = client.post("/demo/review", json={"text": "x" * 101})

        self.assertEqual(body_response.status_code, 413)
        self.assertEqual(text_response.status_code, 413)

    def test_public_demo_rate_limits_by_client(self):
        self._enable_demo()
        os.environ["JUNAS_PUBLIC_DEMO_RATE_LIMIT"] = "2"
        os.environ["JUNAS_PUBLIC_DEMO_RATE_LIMIT_WINDOW_SECONDS"] = "60"
        payload = {"text": "Internal lunch note.", "source_jurisdiction": "SG", "destination_jurisdiction": "SG"}
        with TestClient(main.app) as client:
            first = client.post("/demo/review", json=payload)
            second = client.post("/demo/review", json=payload)
            third = client.post("/demo/review", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(third.status_code, 429)


if __name__ == "__main__":
    unittest.main()
