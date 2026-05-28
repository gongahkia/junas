import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


def load_preflight_module():
    path = ROOT / "scripts" / "preflight.py"
    spec = importlib.util.spec_from_file_location("test_preflight_module", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load preflight module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_preflight_module()

    def _settings(self):
        return SimpleNamespace(
            config_path=ROOT / "config.toml",
            pipeline=SimpleNamespace(layers=()),
            public_evidence=SimpleNamespace(enabled=False, provider="none"),
            llm=SimpleNamespace(enabled=False, provider="none"),
        )

    def _run_preflight(self, argv: list[str], env: dict[str, str] | None = None) -> int:
        with mock.patch.object(sys, "argv", ["preflight.py", *argv]):
            with mock.patch.dict(os.environ, env or {}, clear=False):
                with mock.patch.object(self.mod, "load_runtime_settings", return_value=self._settings()):
                    with mock.patch.object(self.mod, "_check_spacy_model", return_value=(True, "spacy ok")):
                        with mock.patch.object(self.mod, "_check_optional_import", return_value=(True, "optional ok")):
                            return self.mod.main()

    def test_production_strict_fails_when_dev_auth_enabled(self):
        exit_code = self._run_preflight(
            ["--strict", "--deployment", "production"],
            {"KAYPOH_DEV_AUTH": "1"},
        )

        self.assertEqual(exit_code, 1)

    def test_local_strict_allows_dev_auth(self):
        exit_code = self._run_preflight(
            ["--strict", "--deployment", "local"],
            {"KAYPOH_DEV_AUTH": "1"},
        )

        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
