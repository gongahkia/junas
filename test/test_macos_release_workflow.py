from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class MacosReleaseWorkflowTests(unittest.TestCase):
    def test_release_workflow_imports_cert_notarizes_verifies_and_uploads(self):
        workflow = (ROOT / ".github" / "workflows" / "release-macos-dmg.yml").read_text(encoding="utf-8")

        for token in (
            "name: Release macOS DMG",
            "workflow_dispatch:",
            "environment: macos-release",
            "runs-on: macos-latest",
            "MACOS_DEVELOPER_ID_CERTIFICATE_BASE64",
            "MACOS_DEVELOPER_ID_CERTIFICATE_PASSWORD",
            "MACOS_CODESIGN_IDENTITY",
            "APPLE_ID",
            "APPLE_TEAM_ID",
            "APPLE_APP_SPECIFIC_PASSWORD",
            "security create-keychain",
            "security import",
            "security set-key-partition-list",
            "xcrun notarytool store-credentials junas-notary",
            'JUNAS_RELEASE_SIGNING_REQUIRED: "1"',
            "scripts/package_macos_dmg.sh",
            "spctl -a -t open --context context:primary-signature",
            "spctl -a -t exec -vv",
            "actions/upload-artifact",
            "gh release upload",
            "security delete-keychain",
        ):
            self.assertIn(token, workflow)

    def test_release_docs_name_workflow_secrets_and_gates(self):
        signing = (ROOT / "docs" / "macos-signing-credentials.md").read_text(encoding="utf-8")
        dmg = (ROOT / "docs" / "macos-dmg-release.md").read_text(encoding="utf-8")
        release_process = (ROOT / "docs" / "release-process.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        for token in (
            "macos-release",
            "MACOS_DEVELOPER_ID_CERTIFICATE_BASE64",
            "MACOS_DEVELOPER_ID_CERTIFICATE_PASSWORD",
            "MACOS_CODESIGN_IDENTITY",
            "APPLE_ID",
            "APPLE_TEAM_ID",
            "APPLE_APP_SPECIFIC_PASSWORD",
            ".github/workflows/release-macos-dmg.yml",
        ):
            self.assertIn(token, signing)
        for token in (
            "Protected CI Release",
            ".github/workflows/release-macos-dmg.yml",
            "upload_to_release=true",
            "stock-Mac verification",
        ):
            self.assertIn(token, dmg)
        self.assertIn(".github/workflows/release-macos-dmg.yml", release_process)
        self.assertIn(".github/workflows/release-macos-dmg.yml", docs_index)


if __name__ == "__main__":
    unittest.main()
