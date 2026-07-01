import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from junas.policy import load_policy_profile


def load_retention_checker():
    path = ROOT / "scripts" / "check_retention_manifest.py"
    spec = importlib.util.spec_from_file_location("test_docker_retention_checker", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load retention checker from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DockerProductionExampleTests(unittest.TestCase):
    def test_compose_example_enables_required_production_controls(self):
        text = (ROOT / "docker-compose.production.example.yml").read_text(encoding="utf-8")

        for token in (
            'JUNAS_DEPLOYMENT_MODE: production',
            'JUNAS_TENANCY_ENABLED: "1"',
            "JUNAS_TENANT_CREDENTIALS_JSON",
            "JUNAS_POLICY_CONFIG: /etc/junas/policy.toml",
            'JUNAS_REVIEW_PERSIST: "1"',
            "JUNAS_JOURNAL_KEYS_FILE: /etc/junas/journal-keys.toml",
            "JUNAS_MAPPING_STORE_KEY",
            "JUNAS_SUBJECT_INDEX_KEY",
            "JUNAS_RETENTION_MANIFEST: /etc/junas/retention_manifest.json",
            'JUNAS_ALLOW_PLAINTEXT_MAPPINGS: "0"',
            'JUNAS_DEV_AUTH: "0"',
            "python scripts/preflight.py --deployment production --strict",
            "--no-access-log",
            'json.load(sys.stdin).get(\\"ready\\") is True',
        ):
            self.assertIn(token, text)

    def test_dockerfile_copies_preflight_retention_dependency(self):
        text = (ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertRegex(text, re.compile(r"COPY scripts/preflight.py scripts/check_retention_manifest.py"))

    def test_sample_policy_and_retention_manifest_validate(self):
        policy = ROOT / "deploy" / "docker" / "policy.production.example.toml"
        profile = load_policy_profile(policy, production=True)
        self.assertEqual(profile.policy_id, "docker-production-example")

        checker = load_retention_checker()
        manifest = ROOT / "deploy" / "docker" / "retention_manifest.example.json"
        payload = checker.check_manifest(manifest)
        self.assertTrue(payload["ok"], json.dumps(payload, indent=2))

    def test_docs_link_production_compose_example(self):
        docs = (ROOT / "docs" / "deployment-hardening.md").read_text(encoding="utf-8")
        install = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for text in (docs, install, readme):
            self.assertIn("docker-compose.production.example.yml", text)


if __name__ == "__main__":
    unittest.main()
