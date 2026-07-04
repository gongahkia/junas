import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class DistributionDocsTests(unittest.TestCase):
    def test_distribution_doc_separates_current_and_planned_install_paths(self):
        text = (ROOT / "docs" / "distribution.md").read_text(encoding="utf-8")

        for token in (
            "v0.1.0",
            "junas-0.1.0-py3-none-any.whl",
            "junas-0.1.0.tar.gz",
            "checkout-first path",
            "`cargo install aki` is not available",
            "There is no `Cargo.toml`",
            "No Nix flake or package expression is committed yet",
            "This is a plan, not a current install path",
            "No Homebrew formula/cask or signed macOS DMG is published",
        ):
            self.assertIn(token, text)

    def test_distribution_doc_plan_has_nix_exit_gates(self):
        text = (ROOT / "docs" / "distribution.md").read_text(encoding="utf-8")

        for token in (
            "flake.nix",
            "pyproject.toml",
            "uv.lock",
            "Python 3.12",
            "packages.<system>.junas",
            "apps.<system>.junas",
            "nix flake check",
            "starts the local backend from a clean checkout",
        ):
            self.assertIn(token, text)

    def test_repo_has_no_cargo_or_nix_install_surface_yet(self):
        self.assertFalse((ROOT / "Cargo.toml").exists())
        self.assertFalse((ROOT / "flake.nix").exists())
        self.assertFalse((ROOT / "default.nix").exists())
        self.assertFalse((ROOT / "shell.nix").exists())


if __name__ == "__main__":
    unittest.main()
