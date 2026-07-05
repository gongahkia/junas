from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class MacosDmgPackagingTests(unittest.TestCase):
    def test_dmg_release_script_builds_app_sidecar_signs_notarizes_and_hashes(self):
        script = (ROOT / "scripts" / "package_macos_dmg.sh").read_text(encoding="utf-8")
        spec = (ROOT / "packaging" / "junas-sidecar.spec").read_text(encoding="utf-8")
        entrypoint = (ROOT / "packaging" / "junas_sidecar_entrypoint.py").read_text(encoding="utf-8")
        client = (
            ROOT / "apps" / "macos-menu-bar" / "Sources" / "JunasMenuBar" / "Services" / "SidecarClient.swift"
        ).read_text(encoding="utf-8")
        run_script = (ROOT / "script" / "build_and_run.sh").read_text(encoding="utf-8")

        for token in (
            "JUNAS_RELEASE_SIGNING_REQUIRED",
            "./script/build_and_run.sh --bundle-only",
            "uv run pyinstaller packaging/junas-sidecar.spec",
            "Contents/Resources/junas-sidecar",
            "codesign --force --timestamp --options runtime",
            "hdiutil create",
            "notarytool submit",
            "stapler staple",
            "spctl -a -t open",
            "shasum -a 256",
        ):
            self.assertIn(token, script)
        self.assertIn('main(["sidecar", "stdio"])', entrypoint)
        self.assertIn('name="junas-sidecar"', spec)
        self.assertIn("junas.desktop.sidecar_protocol", spec)
        self.assertIn('appending(path: "junas-sidecar/junas-sidecar")', client)
        self.assertIn("--bundle-only|bundle", run_script)

    def test_release_signing_required_fails_before_dmg_build_without_credentials(self):
        env = dict(os.environ)
        env["JUNAS_RELEASE_SIGNING_REQUIRED"] = "1"
        env["JUNAS_CODESIGN_IDENTITY"] = ""
        env["JUNAS_NOTARYTOOL_PROFILE"] = ""

        completed = subprocess.run(
            ["bash", str(ROOT / "scripts" / "package_macos_dmg.sh"), "--check-config"],
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
        self.assertNotIn("hdiutil", output.lower())
        self.assertNotIn("password", output.lower())

    def test_dmg_release_docs_cover_unsigned_signed_stock_mac_and_release_notes_gates(self):
        doc = (ROOT / "docs" / "macos-dmg-release.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        packaging = (ROOT / "packaging" / "README.md").read_text(encoding="utf-8")
        distribution = (ROOT / "docs" / "distribution.md").read_text(encoding="utf-8")

        for token in (
            "JunasMenuBar.app",
            "Contents/Resources/junas-sidecar/junas-sidecar",
            "Local Unsigned DMG",
            "Signed Release DMG",
            "notarization",
            "staples",
            "spctl -a -t open",
            "Homebrew cask",
            "Release Notes Gate",
        ):
            self.assertIn(token, doc)
        for text in (readme, docs_index, packaging, distribution):
            self.assertIn("macos-dmg-release.md", text)


if __name__ == "__main__":
    unittest.main()
