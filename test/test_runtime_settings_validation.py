import json
import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from kaypoh.configs import runtime


class RuntimeSettingsValidationTests(unittest.TestCase):
    def _write_config(self, content: str) -> Path:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        path = Path(tempdir.name) / "config.toml"
        path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
        return path

    def test_invalid_toml_raises_config_error(self):
        config_path = self._write_config(
            """
            [pipeline
            layers = ["model1"]
            """
        )

        with self.assertRaises(runtime.ConfigError) as ctx:
            runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertIn("config parse failure", str(ctx.exception))

    def test_invalid_type_raises_config_error(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = ["model1"]

            [mosaic]
            threshold = "many"
            """
        )

        with self.assertRaises(runtime.ConfigError) as ctx:
            runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertIn("invalid integer for mosaic.threshold", str(ctx.exception))

    def test_cli_overrides_take_precedence_over_env_and_config(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = ["lexicon"]
            """
        )

        with patch.dict(os.environ, {"PIPELINE_LAYERS": "model1,model2"}, clear=False):
            settings = runtime.load_runtime_settings(
                cli_overrides={
                    "config_path": str(config_path),
                    "pipeline.layers": ["model2"],
                }
            )

        self.assertEqual(settings.pipeline.layers, ("model2",))

    def test_remote_llm_defaults_to_structured_tokens_when_mode_unset(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = ["lexicon"]

            [llm]
            enabled = true
            provider = "vllm"
            base_url = "https://llm.example.com/v1"
            allow_remote_base_url = true
            """
        )

        settings = runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertEqual(settings.llm.llm_input_mode, "structured_tokens")

    def test_remote_raw_text_requires_explicit_opt_in(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = ["lexicon"]

            [llm]
            enabled = true
            provider = "vllm"
            base_url = "https://llm.example.com/v1"
            allow_remote_base_url = true
            llm_input_mode = "raw_text"
            """
        )

        with self.assertRaises(runtime.ConfigError) as ctx:
            runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertIn("allow_remote_raw_text", str(ctx.exception))

    def test_remote_raw_text_accepted_with_explicit_opt_in(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = ["lexicon"]

            [llm]
            enabled = true
            provider = "vllm"
            base_url = "https://llm.example.com/v1"
            allow_remote_base_url = true
            allow_remote_raw_text = true
            llm_input_mode = "raw_text"
            """
        )

        settings = runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertEqual(settings.llm.llm_input_mode, "raw_text")
        self.assertTrue(settings.llm.allow_remote_raw_text)

    def test_local_raw_text_still_default(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = ["lexicon"]

            [llm]
            enabled = true
            provider = "vllm"
            base_url = "http://127.0.0.1:8001/v1"
            """
        )

        settings = runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertEqual(settings.llm.llm_input_mode, "raw_text")

    def test_siem_settings_load_from_config(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = ["lexicon"]

            [siem]
            enabled = true
            sink = "stdout"
            syslog_address = "udp://127.0.0.1:5514"
            facility = "local5"
            app_name = "kaypoh-test"
            """
        )

        settings = runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertTrue(settings.siem.enabled)
        self.assertEqual(settings.siem.sink, "stdout")
        self.assertEqual(settings.siem.syslog_address, "udp://127.0.0.1:5514")
        self.assertEqual(settings.siem.facility, "local5")
        self.assertEqual(settings.siem.app_name, "kaypoh-test")

    def test_invalid_siem_sink_raises_config_error(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = ["lexicon"]

            [siem]
            enabled = true
            sink = "file"
            """
        )

        with self.assertRaises(runtime.ConfigError) as ctx:
            runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertIn("siem.sink", str(ctx.exception))

    def test_tenancy_settings_load_api_key_registry(self):
        credentials_json = json.dumps(
            {
                "tenant-a-key": {
                    "tenant_id": "tenant-a",
                    "subject": "svc-a",
                    "roles": ["reviewer", "auditor"],
                }
            },
            separators=(",", ":"),
        )
        config_path = self._write_config(
            f"""
            [pipeline]
            layers = ["lexicon"]

            [tenancy]
            enabled = true
            auth_modes = ["api_key"]
            tenant_credentials_json = {credentials_json!r}
            """
        )

        settings = runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertTrue(settings.tenancy.enabled)
        self.assertEqual(settings.tenancy.auth_modes, ("api_key",))
        self.assertEqual(len(settings.tenancy.tenant_credentials), 1)
        credential = settings.tenancy.tenant_credentials[0]
        self.assertEqual(credential.tenant_id, "tenant-a")
        self.assertEqual(credential.subject, "svc-a")
        self.assertEqual(credential.roles, ("reviewer", "auditor"))

    def test_tenancy_enabled_requires_jwt_validation_material(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = ["lexicon"]

            [tenancy]
            enabled = true
            auth_modes = ["jwt"]
            """
        )

        with self.assertRaises(runtime.ConfigError) as ctx:
            runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertIn("jwt_hs256_secret or tenancy.jwt_jwks_url", str(ctx.exception))

    def test_document_ingest_settings_load_from_config(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = ["lexicon"]

            [document_ingest]
            fail_closed = true
            min_pdf_text_chars = 64
            min_pdf_chars_per_page = 32
            max_empty_pdf_page_ratio = 0.5
            reject_image_only_pdf = false
            """
        )

        settings = runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertTrue(settings.document_ingest.fail_closed)
        self.assertEqual(settings.document_ingest.min_pdf_text_chars, 64)
        self.assertEqual(settings.document_ingest.min_pdf_chars_per_page, 32)
        self.assertEqual(settings.document_ingest.max_empty_pdf_page_ratio, 0.5)
        self.assertFalse(settings.document_ingest.reject_image_only_pdf)


if __name__ == "__main__":
    unittest.main()
