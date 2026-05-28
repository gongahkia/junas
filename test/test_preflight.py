import importlib.util
import os
import sys
import tempfile
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
            api=SimpleNamespace(api_key=""),
            tenancy=SimpleNamespace(enabled=False),
            public_evidence=SimpleNamespace(enabled=False, provider="none"),
            llm=SimpleNamespace(enabled=False, provider="none"),
        )

    def _run_preflight(
        self,
        argv: list[str],
        env: dict[str, str] | None = None,
        *,
        settings: SimpleNamespace | None = None,
        retention: tuple[bool, str] = (True, "retention manifest configured"),
    ) -> int:
        base_env = {
            "KAYPOH_REVIEW_PERSIST": "0",
            "KAYPOH_API_KEY": "",
            "KAYPOH_MAPPING_STORE_KEY": "",
            "KAYPOH_SUBJECT_INDEX_KEY": "",
            "KAYPOH_JOURNAL_KEYS_FILE": "",
            "KAYPOH_DEV_AUTH": "",
        }
        if env:
            base_env.update(env)
        with mock.patch.object(sys, "argv", ["preflight.py", *argv]):
            with mock.patch.dict(os.environ, base_env, clear=False):
                with mock.patch.object(self.mod, "load_runtime_settings", return_value=settings or self._settings()):
                    with mock.patch.object(self.mod, "_check_spacy_model", return_value=(True, "spacy ok")):
                        with mock.patch.object(self.mod, "_check_optional_import", return_value=(True, "optional ok")):
                            with mock.patch.object(self.mod, "_retention_manifest_configured", return_value=retention):
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

    def test_production_strict_fails_when_persistence_missing_hardening_keys(self):
        exit_code = self._run_preflight(
            ["--strict", "--deployment", "production"],
            {
                "KAYPOH_REVIEW_PERSIST": "1",
                "KAYPOH_API_KEY": "api-secret",
                "KAYPOH_MAPPING_STORE_KEY": "",
                "KAYPOH_SUBJECT_INDEX_KEY": "",
                "KAYPOH_JOURNAL_KEYS_FILE": "",
            },
            settings=SimpleNamespace(
                config_path=ROOT / "config.toml",
                pipeline=SimpleNamespace(layers=()),
                api=SimpleNamespace(api_key="api-secret"),
                tenancy=SimpleNamespace(enabled=False),
                public_evidence=SimpleNamespace(enabled=False, provider="none"),
                llm=SimpleNamespace(enabled=False, provider="none"),
            ),
        )

        self.assertEqual(exit_code, 1)

    def test_production_strict_passes_with_persistence_hardening_keys(self):
        from cryptography.fernet import Fernet

        with tempfile.TemporaryDirectory() as tmp_dir:
            key_file = Path(tmp_dir) / "journal_keys.toml"
            key_file.write_text(
                'active = "v2"\n\n[keys.v2]\nsecret = "journal-secret-v2"\n',
                encoding="utf-8",
            )
            exit_code = self._run_preflight(
                ["--strict", "--deployment", "production"],
                {
                    "KAYPOH_REVIEW_PERSIST": "1",
                    "KAYPOH_API_KEY": "api-secret",
                    "KAYPOH_MAPPING_STORE_KEY": Fernet.generate_key().decode("ascii"),
                    "KAYPOH_SUBJECT_INDEX_KEY": "subject-index-secret",
                    "KAYPOH_JOURNAL_KEYS_FILE": str(key_file),
                },
                settings=SimpleNamespace(
                    config_path=ROOT / "config.toml",
                    pipeline=SimpleNamespace(layers=()),
                    api=SimpleNamespace(api_key="api-secret"),
                    tenancy=SimpleNamespace(enabled=False),
                    public_evidence=SimpleNamespace(enabled=False, provider="none"),
                    llm=SimpleNamespace(enabled=False, provider="none"),
                ),
            )

        self.assertEqual(exit_code, 0)

    def test_production_strict_fails_without_api_or_tenant_auth(self):
        exit_code = self._run_preflight(["--strict", "--deployment", "production"])

        self.assertEqual(exit_code, 1)

    def test_production_strict_fails_when_retention_manifest_incomplete(self):
        exit_code = self._run_preflight(
            ["--strict", "--deployment", "production"],
            {"KAYPOH_API_KEY": "api-secret"},
            settings=SimpleNamespace(
                config_path=ROOT / "config.toml",
                pipeline=SimpleNamespace(layers=()),
                api=SimpleNamespace(api_key="api-secret"),
                tenancy=SimpleNamespace(enabled=False),
                public_evidence=SimpleNamespace(enabled=False, provider="none"),
                llm=SimpleNamespace(enabled=False, provider="none"),
            ),
            retention=(False, "retention manifest incomplete (logs)"),
        )

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
