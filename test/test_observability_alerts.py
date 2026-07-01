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
    spec = importlib.util.spec_from_file_location("test_observability_preflight_module", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load preflight module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ObservabilityAlertsTests(unittest.TestCase):
    def test_prometheus_alert_pack_covers_required_failure_modes(self):
        text = (ROOT / "deploy" / "prometheus" / "junas-alerts.yml").read_text(encoding="utf-8")

        for token in (
            "JunasBackendHighErrorRate",
            "JunasPolicyConfigValidationFailure",
            "JunasExternalHelperFailure",
            "JunasAdapterAuthFailureSpike",
            "JunasLocalDaemonPairingAnomalies",
            "junas_http_requests_total",
            'junas_preflight_check_status{check="policy_config"}',
            "junas_dependency_configured",
            "junas_dependency_healthy",
            'endpoint=~"/local/pairing/.*"',
        ):
            self.assertIn(token, text)
        self.assertNotIn("matched_text", text)

    def test_docs_index_links_alert_runbook(self):
        text = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("observability-alerts.md", text)


class PreflightMetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_preflight_module()

    def _production_settings(self):
        return SimpleNamespace(
            config_path=ROOT / "config.toml",
            pipeline=SimpleNamespace(layers=()),
            api=SimpleNamespace(
                api_key="api-secret",
                allowed_origins=("https://junas.example.com",),
                max_request_bytes=10 * 1024 * 1024,
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

    def _run_preflight(self, argv: list[str], env: dict[str, str]) -> int:
        base_env = {
            "JUNAS_REVIEW_PERSIST": "0",
            "JUNAS_API_KEY": "",
            "JUNAS_POLICY_CONFIG": "",
            "JUNAS_POLICY_CONFIG_PATH": "",
            "JUNAS_DEV_AUTH": "",
        }
        base_env.update(env)
        with mock.patch.object(sys, "argv", ["preflight.py", *argv]):
            with mock.patch.dict(os.environ, base_env, clear=False):
                with mock.patch.object(self.mod, "load_runtime_settings", return_value=self._production_settings()):
                    with mock.patch.object(self.mod, "_check_spacy_model", return_value=(True, "spacy ok")):
                        with mock.patch.object(self.mod, "_check_optional_import", return_value=(True, "optional ok")):
                            with mock.patch.object(
                                self.mod,
                                "_retention_manifest_configured",
                                return_value=(True, "retention manifest configured"),
                            ):
                                return self.mod.main()

    def test_preflight_writes_policy_config_metric_for_alerts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            policy_file = self._write_policy_config(tmp_dir)
            output = Path(tmp_dir) / "preflight.prom"
            exit_code = self._run_preflight(
                [
                    "--strict",
                    "--deployment",
                    "production",
                    "--prometheus-output",
                    str(output),
                ],
                {
                    "JUNAS_API_KEY": "api-secret",
                    "JUNAS_POLICY_CONFIG": str(policy_file),
                },
            )

            self.assertEqual(exit_code, 0)
            metrics = output.read_text(encoding="utf-8")

        self.assertIn("# TYPE junas_preflight_check_status gauge", metrics)
        self.assertIn('junas_preflight_check_status{check="policy_config"} 1', metrics)
        self.assertIn('junas_preflight_check_status{check="production_auth"} 1', metrics)


if __name__ == "__main__":
    unittest.main()
