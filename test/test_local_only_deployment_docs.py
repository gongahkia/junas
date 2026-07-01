import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def squash(text: str) -> str:
    return " ".join(text.split())


class LocalOnlyDeploymentDocsTests(unittest.TestCase):
    def test_local_only_doc_states_packaged_defaults_and_available_local_features(self):
        text = squash((ROOT / "docs" / "deployment-local-only.md").read_text(encoding="utf-8"))

        for token in (
            "Local-Only Deployment Boundary",
            "JUNAS_HOST=127.0.0.1",
            "JUNAS_PORT=8765",
            'PIPELINE_LAYERS=""',
            "JUNAS_PUBLIC_EVIDENCE_ENABLED=0",
            "JUNAS_LLM_ENABLED=0",
            "JUNAS_REVIEW_PERSIST=1",
            "JUNAS_LOCAL_DAEMON_ACL_ENABLED=1",
            "Deterministic `/review`",
            "`/safe-rewrite`, `/redact`, `/redact-pii`, `/anonymize`, and `/documents/scrub`",
            "JUNAS_JOURNAL_KEY",
            "JUNAS_MAPPING_STORE_KEY",
            "JUNAS_SUBJECT_INDEX_KEY",
            "JUNAS_ALLOW_PLAINTEXT_MAPPINGS=0",
        ):
            self.assertIn(token, text)

    def test_local_only_doc_lists_unavailable_server_side_layers(self):
        text = squash((ROOT / "docs" / "deployment-local-only.md").read_text(encoding="utf-8"))

        for token in (
            "Unavailable Without Server-Side Optional Layers",
            "Public evidence retrieval",
            "Remote LLM adjudication",
            "Tenant auth and RBAC",
            "Central review queue",
            "SIEM and central telemetry",
            "Tenant-wide audit export",
            "DMS/server-side hooks",
            "Fleet policy and enforcement",
            "no external public-source lookup",
            "no LLM adjudicator",
            "No shared tenant identity plane",
            "No tenant-wide SIEM export",
            "No central audit-pack source",
            "the deployment is no longer local-only",
        ):
            self.assertIn(token, text)

    def test_docs_index_and_existing_guides_link_local_only_doc(self):
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        hardening = (ROOT / "docs" / "deployment-hardening.md").read_text(encoding="utf-8")
        install = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")

        for text in (docs_index, hardening, install):
            self.assertIn("deployment-local-only.md", text)


if __name__ == "__main__":
    unittest.main()
