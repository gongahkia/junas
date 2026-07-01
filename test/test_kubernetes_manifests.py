import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
K8S = ROOT / "deploy" / "kubernetes"


class KubernetesManifestTests(unittest.TestCase):
    def test_reference_manifests_exist(self):
        for name in (
            "README.md",
            "namespace.yaml",
            "configmap.yaml",
            "secret.example.yaml",
            "pvc.yaml",
            "deployment.yaml",
            "service.yaml",
            "ingress.example.yaml",
        ):
            with self.subTest(name=name):
                self.assertTrue((K8S / name).exists())

    def test_deployment_preserves_production_controls(self):
        text = (K8S / "deployment.yaml").read_text(encoding="utf-8")

        for token in (
            "scripts/preflight.py --deployment production --strict",
            "--no-access-log",
            "JUNAS_TENANCY_ENABLED",
            "JUNAS_TENANT_CREDENTIALS_JSON",
            "secretKeyRef",
            "JUNAS_POLICY_CONFIG",
            "JUNAS_JOURNAL_KEYS_FILE",
            "JUNAS_MAPPING_STORE_KEY",
            "JUNAS_SUBJECT_INDEX_KEY",
            "JUNAS_RETENTION_MANIFEST",
            "JUNAS_ALLOW_PLAINTEXT_MAPPINGS",
            "JUNAS_DEV_AUTH",
            "persistentVolumeClaim",
            "readOnlyRootFilesystem: true",
            'json.load(sys.stdin).get("ready") is True',
        ):
            self.assertIn(token, text)

    def test_config_and_secret_examples_are_placeholders(self):
        config = (K8S / "configmap.yaml").read_text(encoding="utf-8")
        secret = (K8S / "secret.example.yaml").read_text(encoding="utf-8")

        self.assertIn('policy_id = "kubernetes-production-example"', config)
        self.assertIn('"schema_version": "junas.retention_manifest.v1"', config)
        self.assertIn("replace-api-key", secret)
        self.assertIn("replace-with-fernet-key", secret)
        self.assertIn("replace-with-customer-held-journal-hmac-secret", secret)

    def test_docs_link_kubernetes_reference(self):
        text = (ROOT / "docs" / "deployment-hardening.md").read_text(encoding="utf-8")

        self.assertIn("deploy/kubernetes/", text)
        self.assertIn("Kubernetes reference manifests", text)


if __name__ == "__main__":
    unittest.main()
