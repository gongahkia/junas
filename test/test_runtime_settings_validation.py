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


if __name__ == "__main__":
    unittest.main()
