import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class HomebrewCaskTests(unittest.TestCase):
    def test_staged_junas_cask_targets_signed_dmg_release_shape(self):
        text = (ROOT / "packaging" / "homebrew" / "Casks" / "junas.rb").read_text(encoding="utf-8")

        for token in (
            'cask "junas" do',
            'version "0.1.0"',
            'url "https://github.com/gongahkia/junas/releases/download/v#{version}/JunasMenuBar-#{version}.dmg"',
            'name "Junas"',
            'name "Junas Menu Bar"',
            "depends_on macos: :sonoma",
            'app "JunasMenuBar.app"',
        ):
            self.assertIn(token, text)
        self.assertRegex(text, r'sha256 "[a-f0-9]{64}"')
        self.assertNotIn("sha256 :no_check", text)

    def test_homebrew_cask_doc_records_tap_commands_and_gates(self):
        text = (ROOT / "docs" / "homebrew-cask.md").read_text(encoding="utf-8")

        for token in (
            "Status: staging only",
            "`gongahkia/tap`",
            "`gongahkia/homebrew-tap`",
            "`packaging/homebrew/Casks/junas.rb`",
            "brew tap gongahkia/tap",
            "brew install --cask junas",
            "brew upgrade --cask junas",
            "brew uninstall --cask junas",
            "uv run python scripts/update_homebrew_cask.py",
            "./scripts/verify_homebrew_cask.sh",
            "`shasum -a 256 dist/JunasMenuBar-<version>.dmg`",
            "signed DMG release asset",
            "brew style --cask Casks/junas.rb",
            "brew audit --cask --strict --online junas",
            "planned install path",
        ):
            self.assertIn(token, text)

    def test_readme_keeps_homebrew_non_primary_until_signed_dmg_exists(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn(
            "Packaged DMG, Homebrew, Nix, and signed desktop install paths are not the default README path yet", text
        )
        self.assertIn("Homebrew tap naming and cask publication gates", text)

    def test_update_homebrew_cask_script_sets_version_and_sha_from_dmg(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cask_path = tmp_path / "junas.rb"
            dmg_path = tmp_path / "JunasMenuBar-1.2.3.dmg"
            cask_path.write_text((ROOT / "packaging" / "homebrew" / "Casks" / "junas.rb").read_text(), encoding="utf-8")
            dmg_path.write_bytes(b"synthetic signed dmg bytes")

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "update_homebrew_cask.py"),
                    "--version",
                    "1.2.3",
                    "--dmg",
                    str(dmg_path),
                    "--cask",
                    str(cask_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            updated = cask_path.read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('version "1.2.3"', updated)
        self.assertIn("65279f1de64bfa36ffe413f95f49ffe58249192a3536ee76bdc56f49edd36beb", updated)
        self.assertIn("version=1.2.3", result.stdout)

    def test_homebrew_cask_verifier_creates_temp_tap_and_runs_style(self):
        text = (ROOT / "scripts" / "verify_homebrew_cask.sh").read_text(encoding="utf-8")

        for token in (
            "brew tap-new --no-git",
            "junas/cask-verify",
            "Casks/junas.rb",
            "brew style",
            "brew untap",
            "homebrew_cask_style_verified: true",
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
