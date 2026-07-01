import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def squash(text: str) -> str:
    return " ".join(text.split())


class DeploymentRollbackDocsTests(unittest.TestCase):
    def test_rollback_doc_covers_required_surfaces(self):
        text = squash((ROOT / "docs" / "deployment-rollback.md").read_text(encoding="utf-8"))

        for token in (
            "Uninstall And Rollback",
            "## Server Backend",
            "docker compose -f docker-compose.production.example.yml down",
            "scripts/preflight.py --deployment production --strict",
            "kubectl -n junas rollout undo deployment/junas",
            "kubectl -n junas scale deployment/junas --replicas=0",
            "## Local Daemon",
            "packaging/macos/uninstall.sh",
            "security delete-generic-password",
            "packaging/macos/update.sh",
            "## Outlook Add-In",
            "dist/outlook-addin/{profile}/manifest.xml",
            "OnMessageSend",
            "## Browser Extension",
            "Chrome Web Store",
            "Edge Add-ons",
            "ExtensionSettings",
            "## Word Add-In",
            "ReadDocument",
        ):
            self.assertIn(token, text)

    def test_rollback_doc_keeps_state_deletion_under_retention(self):
        text = squash((ROOT / "docs" / "deployment-rollback.md").read_text(encoding="utf-8"))

        for token in (
            "Rollback and uninstall are operational changes, not data-deletion shortcuts",
            "retention and legal-hold policy",
            "Do not delete `JUNAS_JOURNAL_DIR`, PVCs, SIEM indexes, audit packs, mapping stores, or subject indexes",
            "does not delete local tokens, sockets, or logs",
            "Do not remove backend journals or approval records",
            "Do not treat extension removal as deletion of backend telemetry, SIEM, or journal records",
            "Data disposition",
            "Credential action",
        ):
            self.assertIn(token, text)

    def test_docs_and_packaging_guides_link_rollback_doc(self):
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        install = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")
        packaging = (ROOT / "docs" / "integrations" / "adapter-packaging.md").read_text(
            encoding="utf-8"
        )

        for text in (docs_index, install, packaging):
            self.assertIn("deployment-rollback.md", text)


if __name__ == "__main__":
    unittest.main()
