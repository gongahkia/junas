import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def squash(text: str) -> str:
    return " ".join(text.split())


class AdapterPackagingDocsTests(unittest.TestCase):
    def test_packaging_doc_separates_artifacts_from_backend_deployment(self):
        text = squash((ROOT / "docs" / "integrations" / "adapter-packaging.md").read_text(encoding="utf-8"))

        for token in (
            "Adapter Packaging",
            "Adapter packaging is separate from backend deployment",
            "Backend launch scripts start FastAPI only",
            "browser extension ZIPs",
            "CRXs",
            "Office manifests",
            "Office taskpane/runtime assets",
            "docs/deployment-hardening.md",
            "docs/deployment-customer-managed.md",
            "docs/deployment-local-only.md",
        ):
            self.assertIn(token, text)

    def test_packaging_doc_covers_browser_artifacts(self):
        text = squash((ROOT / "docs" / "integrations" / "adapter-packaging.md").read_text(encoding="utf-8"))

        for token in (
            "## Browser Extension",
            "integrations/browser_extension/",
            "./scripts/package_browser_extension.sh",
            "dist/browser-extension/junas-local-review.zip",
            "dist/browser-extension/junas-local-review.crx",
            "JUNAS_EXTENSION_SRC",
            "JUNAS_EXTENSION_OUT_DIR",
            "JUNAS_CHROME_EXTENSION_KEY",
            "JUNAS_CHROME_BIN",
            "Chrome Web Store",
            "Edge Add-ons",
            "enterprise extension policy",
            "Do not use `<all_urls>`",
        ):
            self.assertIn(token, text)

    def test_packaging_doc_covers_office_artifacts(self):
        text = squash((ROOT / "docs" / "integrations" / "adapter-packaging.md").read_text(encoding="utf-8"))

        for token in (
            "## Outlook Smart Alerts Add-In",
            "integrations/outlook_addin/",
            "scripts/render_outlook_manifest.py",
            "scripts/validate_outlook_manifest.py",
            "dist/outlook-addin/{profile}/manifest.xml",
            "taskpane.html",
            "commands.html",
            "launchevent.js",
            "OnMessageSend",
            'SendMode="SoftBlock"',
            "Microsoft 365 admin-managed deployment",
            "## Word Taskpane Add-In",
            "integrations/word_addin/manifest.xml",
            "https://localhost:3000",
            "ReadDocument",
            "No script in this repo renders Word manifests yet",
        ):
            self.assertIn(token, text)

    def test_docs_indexes_and_install_link_packaging_doc(self):
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        integrations_index = (ROOT / "docs" / "integrations" / "README.md").read_text(
            encoding="utf-8"
        )
        install = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")

        self.assertIn("integrations/adapter-packaging.md", docs_index)
        self.assertIn("adapter-packaging.md", integrations_index)
        self.assertIn("docs/integrations/adapter-packaging.md", install)


if __name__ == "__main__":
    unittest.main()
