import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def squash(text: str) -> str:
    return " ".join(text.split())


class CustomerManagedDeploymentDocsTests(unittest.TestCase):
    def test_doc_requires_customer_held_runtime_secrets(self):
        text = squash(
            (ROOT / "docs" / "deployment-customer-managed.md").read_text(encoding="utf-8")
        )

        for token in (
            "Customer-Managed Deployment Secret Custody",
            "customer-held",
            "customer KMS",
            "AWS Secrets Manager",
            "Azure Key Vault",
            "GCP Secret Manager",
            "HashiCorp Vault",
            "JUNAS_MAPPING_STORE_KEY",
            "JUNAS_JOURNAL_KEYS_FILE",
            "JUNAS_JOURNAL_KEY",
            "JUNAS_SUBJECT_INDEX_KEY",
            "JUNAS_TENANT_CREDENTIALS_JSON",
            "JUNAS_RETENTION_MANIFEST",
            "scripts/preflight.py --deployment production --strict",
            "scripts/check_retention_manifest.py --manifest",
            "scripts/verify_journal.py",
            "scripts/erase_subject.py --backfill --dry-run",
            "subject erasure",
            "retention manifest",
            "deploy/docker/",
            "deploy/kubernetes/",
        ):
            self.assertIn(token, text)

    def test_doc_states_missing_secret_failure_boundaries(self):
        text = squash(
            (ROOT / "docs" / "deployment-customer-managed.md").read_text(encoding="utf-8")
        )

        for token in (
            "persisted mapping files are not application-encrypted",
            "production strict preflight fails when persistence is enabled",
            "journal key rotation is not configured",
            "does not make the OS/filesystem layer append-only",
            "subject erasure cannot look up prior subject values by HMAC",
            "artifact retention and deletion controls are undeclared",
            "encrypted mappings unrecoverable",
        ):
            self.assertIn(token, text)

    def test_docs_index_and_hardening_link_customer_managed_doc(self):
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        hardening = (ROOT / "docs" / "deployment-hardening.md").read_text(encoding="utf-8")

        self.assertIn("deployment-customer-managed.md", docs_index)
        self.assertIn("docs/deployment-customer-managed.md", hardening)


if __name__ == "__main__":
    unittest.main()
