from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class MacosSigningPolicyTests(unittest.TestCase):
    def test_signing_policy_documents_identity_and_secret_storage(self):
        doc = (ROOT / "docs" / "macos-signing-credentials.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        install = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")
        packaging = (ROOT / "packaging" / "README.md").read_text(encoding="utf-8")

        for token in (
            "project-level `Developer ID Application`",
            "not a contributor's personal Apple developer identity",
            "JUNAS_CODESIGN_IDENTITY",
            "JUNAS_NOTARYTOOL_PROFILE",
            "JUNAS_RELEASE_SIGNING_REQUIRED=1",
            "GitHub Actions environment secret",
            "temporary keychain",
            "fails before building",
        ):
            self.assertIn(token, doc)
        for text in (readme, docs_index, install, packaging):
            self.assertIn("macos-signing-credentials.md", text)

    def test_release_signing_required_fails_before_build_without_credentials(self):
        env = dict(os.environ)
        env["JUNAS_RELEASE_SIGNING_REQUIRED"] = "1"
        env["JUNAS_CODESIGN_IDENTITY"] = ""
        env["JUNAS_NOTARYTOOL_PROFILE"] = ""

        completed = subprocess.run(
            ["bash", str(ROOT / "scripts" / "package_macos_desktop.sh")],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        output = completed.stderr + completed.stdout
        self.assertEqual(completed.returncode, 78)
        self.assertIn("JUNAS_CODESIGN_IDENTITY is required", output)
        self.assertNotIn("pyinstaller", output.lower())
        self.assertNotIn("password", output.lower())


if __name__ == "__main__":
    unittest.main()
