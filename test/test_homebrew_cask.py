import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class HomebrewCaskTests(unittest.TestCase):
    def test_staged_aki_cask_targets_signed_dmg_release_shape(self):
        text = (ROOT / "packaging" / "homebrew" / "Casks" / "aki.rb").read_text(encoding="utf-8")

        for token in (
            'cask "aki" do',
            'version "0.1.0"',
            'url "https://github.com/gongahkia/junas/releases/download/v#{version}/JunasMenuBar-#{version}.dmg"',
            'name "Aki"',
            'name "Junas Menu Bar"',
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
            "`packaging/homebrew/Casks/aki.rb`",
            "brew tap gongahkia/tap",
            "brew install --cask aki",
            "brew upgrade --cask aki",
            "brew uninstall --cask aki",
            "`shasum -a 256 dist/JunasMenuBar-<version>.dmg`",
            "Replace the staged cask `sha256` placeholder",
            "signed DMG release asset",
            "brew style --cask Casks/aki.rb",
            "brew audit --cask --strict --online aki",
            "planned install path",
        ):
            self.assertIn(token, text)

    def test_readme_keeps_homebrew_non_primary_until_signed_dmg_exists(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn(
            "Packaged DMG, Homebrew, Nix, and signed desktop install paths are not the default README path yet", text
        )
        self.assertIn("Homebrew tap naming and cask publication gates", text)


if __name__ == "__main__":
    unittest.main()
