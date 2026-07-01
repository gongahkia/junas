import importlib.util
import os
import subprocess
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
            api=SimpleNamespace(
                api_key="",
                allowed_origins=("https://junas.example.com",),
                max_request_bytes=10 * 1024 * 1024,
            ),
            tenancy=SimpleNamespace(enabled=False, tenant_credentials=()),
            public_evidence=SimpleNamespace(enabled=False, provider="none"),
            llm=SimpleNamespace(enabled=False, provider="none"),
            privacy=SimpleNamespace(external_query_policy="sanitized_only"),
            image_scan=SimpleNamespace(provider="none"),
        )

    def _production_settings(self, *, api_key: str = "api-secret", origins=None, max_request_bytes=None):
        return SimpleNamespace(
            config_path=ROOT / "config.toml",
            pipeline=SimpleNamespace(layers=()),
            api=SimpleNamespace(
                api_key=api_key,
                allowed_origins=origins or ("https://junas.example.com",),
                max_request_bytes=max_request_bytes or 10 * 1024 * 1024,
            ),
            tenancy=SimpleNamespace(enabled=False, tenant_credentials=()),
            public_evidence=SimpleNamespace(enabled=False, provider="none"),
            llm=SimpleNamespace(enabled=False, provider="none"),
            privacy=SimpleNamespace(external_query_policy="sanitized_only"),
            image_scan=SimpleNamespace(provider="none"),
        )

    def _write_policy_config(self, tmp_dir: str) -> Path:
        policy_file = Path(tmp_dir) / "policy.toml"
        policy_file.write_text(
            '[policy]\npolicy_id = "production-test"\npolicy_version = "2026-07-01"\n',
            encoding="utf-8",
        )
        return policy_file

    def _run_preflight(
        self,
        argv: list[str],
        env: dict[str, str] | None = None,
        *,
        settings: SimpleNamespace | None = None,
        retention: tuple[bool, str] = (True, "retention manifest configured"),
    ) -> int:
        base_env = {
            "JUNAS_REVIEW_PERSIST": "0",
            "JUNAS_API_KEY": "",
            "JUNAS_MAPPING_STORE_KEY": "",
            "JUNAS_SUBJECT_INDEX_KEY": "",
            "JUNAS_JOURNAL_KEYS_FILE": "",
            "JUNAS_DEV_AUTH": "",
            "JUNAS_POLICY_CONFIG": "",
            "JUNAS_POLICY_CONFIG_PATH": "",
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
            {"JUNAS_DEV_AUTH": "1"},
        )

        self.assertEqual(exit_code, 1)

    def test_local_strict_allows_dev_auth(self):
        exit_code = self._run_preflight(
            ["--strict", "--deployment", "local"],
            {"JUNAS_DEV_AUTH": "1"},
        )

        self.assertEqual(exit_code, 0)

    def test_production_strict_fails_when_persistence_missing_hardening_keys(self):
        exit_code = self._run_preflight(
            ["--strict", "--deployment", "production"],
            {
                "JUNAS_REVIEW_PERSIST": "1",
                "JUNAS_API_KEY": "api-secret",
                "JUNAS_MAPPING_STORE_KEY": "",
                "JUNAS_SUBJECT_INDEX_KEY": "",
                "JUNAS_JOURNAL_KEYS_FILE": "",
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
            policy_file = self._write_policy_config(tmp_dir)
            exit_code = self._run_preflight(
                ["--strict", "--deployment", "production"],
                {
                    "JUNAS_REVIEW_PERSIST": "1",
                    "JUNAS_API_KEY": "api-secret",
                    "JUNAS_MAPPING_STORE_KEY": Fernet.generate_key().decode("ascii"),
                    "JUNAS_SUBJECT_INDEX_KEY": "subject-index-secret",
                    "JUNAS_JOURNAL_KEYS_FILE": str(key_file),
                    "JUNAS_POLICY_CONFIG": str(policy_file),
                },
                settings=self._production_settings(),
            )

        self.assertEqual(exit_code, 0)

    def test_production_strict_fails_without_api_or_tenant_auth(self):
        exit_code = self._run_preflight(["--strict", "--deployment", "production"])

        self.assertEqual(exit_code, 1)

    def test_production_strict_fails_when_retention_manifest_incomplete(self):
        exit_code = self._run_preflight(
            ["--strict", "--deployment", "production"],
            {"JUNAS_API_KEY": "api-secret"},
            settings=self._production_settings(),
            retention=(False, "retention manifest incomplete (logs)"),
        )

        self.assertEqual(exit_code, 1)

    def test_production_strict_fails_without_policy_config(self):
        exit_code = self._run_preflight(
            ["--strict", "--deployment", "production"],
            {"JUNAS_API_KEY": "api-secret"},
            settings=self._production_settings(),
        )

        self.assertEqual(exit_code, 1)

    def test_production_strict_fails_with_unsafe_cors_origin(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            policy_file = self._write_policy_config(tmp_dir)
            exit_code = self._run_preflight(
                ["--strict", "--deployment", "production"],
                {
                    "JUNAS_API_KEY": "api-secret",
                    "JUNAS_POLICY_CONFIG": str(policy_file),
                },
                settings=self._production_settings(origins=("http://localhost",)),
            )

        self.assertEqual(exit_code, 1)

    def test_production_strict_fails_with_oversized_body_cap(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            policy_file = self._write_policy_config(tmp_dir)
            exit_code = self._run_preflight(
                ["--strict", "--deployment", "production"],
                {
                    "JUNAS_API_KEY": "api-secret",
                    "JUNAS_POLICY_CONFIG": str(policy_file),
                },
                settings=self._production_settings(max_request_bytes=50 * 1024 * 1024),
            )

        self.assertEqual(exit_code, 1)

    def test_production_preflight_command_defaults_to_strict_production(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "preflight_production.py")],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("deployment: production", result.stdout)


if __name__ == "__main__":
    unittest.main()
