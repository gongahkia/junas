import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from junas.configs import runtime


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
            layers = ["public_evidence"]
            """
        )

        with self.assertRaises(runtime.ConfigError) as ctx:
            runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertIn("config parse failure", str(ctx.exception))

    def test_unknown_archived_section_raises_config_error(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = []

            [mosaic]
            threshold = "many"
            """
        )

        with self.assertRaises(runtime.ConfigError) as ctx:
            runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertIn("unknown config sections", str(ctx.exception))
        self.assertIn("mosaic", str(ctx.exception))

    def test_cli_overrides_take_precedence_over_env_and_config(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = ["public_evidence"]
            """
        )

        with patch.dict(os.environ, {"PIPELINE_LAYERS": "public_evidence,llm_adjudicator"}, clear=False):
            settings = runtime.load_runtime_settings(
                cli_overrides={
                    "config_path": str(config_path),
                    "pipeline.layers": ["llm_adjudicator"],
                }
            )

        self.assertEqual(settings.pipeline.layers, ("llm_adjudicator",))

    def test_llm_helper_layers_are_valid_and_enable_matching_helpers(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = ["llm_defined_term_extractor", "llm_coverage_auditor"]
            """
        )

        settings = runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertEqual(
            settings.pipeline.layers,
            ("llm_defined_term_extractor", "llm_coverage_auditor"),
        )
        self.assertTrue(settings.llm_helpers.defined_terms_enabled)
        self.assertTrue(settings.llm_helpers.coverage_audit_enabled)

    def test_llm_helper_config_keys_can_enable_individual_helpers(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = []

            [llm_helpers]
            defined_terms_enabled = true
            coverage_audit_enabled = false
            """
        )

        settings = runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertTrue(settings.llm_helpers.enabled)
        self.assertTrue(settings.llm_helpers.defined_terms_enabled)
        self.assertFalse(settings.llm_helpers.coverage_audit_enabled)

    def test_remote_llm_defaults_to_structured_tokens_when_mode_unset(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = []

            [llm]
            enabled = true
            provider = "vllm"
            base_url = "https://llm.example.com/v1"
            allow_remote_base_url = true
            """
        )

        settings = runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertEqual(settings.llm.llm_input_mode, "structured_tokens")

    def test_azure_openai_requires_tenant_opt_in_and_api_version(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = []

            [llm]
            enabled = true
            provider = "azure_openai"
            base_url = "https://example.openai.azure.com"
            model = "gpt-5-2"
            allow_remote_base_url = true
            """
        )

        with self.assertRaises(runtime.ConfigError) as ctx:
            runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertIn("tenant_opt_in_azure_openai", str(ctx.exception))

    def test_azure_openai_accepts_explicit_gates(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = []

            [llm]
            enabled = true
            provider = "azure_openai"
            base_url = "https://example.openai.azure.com"
            model = "gpt-5-2"
            allow_remote_base_url = true
            tenant_opt_in_azure_openai = true
            azure_api_version = "2025-03-01-preview"
            """
        )

        settings = runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertEqual(settings.llm.provider, "azure_openai")
        self.assertTrue(settings.llm.tenant_opt_in_azure_openai)
        self.assertEqual(settings.llm.azure_api_version, "2025-03-01-preview")
        self.assertEqual(settings.llm.llm_input_mode, "structured_tokens")

    def test_remote_raw_text_requires_explicit_opt_in(self):
        config_path = self._write_config(
            """
            [pipeline]
            layers = []

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
            layers = []

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
            layers = []

            [llm]
            enabled = true
            provider = "vllm"
            base_url = "http://127.0.0.1:8001/v1"
            """
        )

        settings = runtime.load_runtime_settings(cli_overrides={"config_path": str(config_path)})

        self.assertEqual(settings.llm.llm_input_mode, "raw_text")


if __name__ == "__main__":
    unittest.main()
