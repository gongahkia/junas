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


if __name__ == "__main__":
    unittest.main()
