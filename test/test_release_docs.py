import unittest
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent


class ReleaseDocsTests(unittest.TestCase):
    def test_v010_release_docs_match_package_version(self):
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        version = pyproject["project"]["version"]
        tag = f"v{version}"
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        notes = (ROOT / "docs" / "releases" / "v0.1.0.md").read_text(encoding="utf-8")

        self.assertEqual(version, "0.1.0")
        for text in (changelog, readme, notes):
            self.assertIn(tag, text)
            self.assertIn("junas-0.1.0-py3-none-any.whl", text)
            self.assertIn("junas-0.1.0.tar.gz", text)
            self.assertIn("https://github.com/gongahkia/junas/releases/tag/v0.1.0", text)

    def test_release_process_defines_tag_and_artifact_convention(self):
        text = (ROOT / "docs" / "release-process.md").read_text(encoding="utf-8")

        for token in (
            "vMAJOR.MINOR.PATCH",
            "project.version",
            "pyproject.toml",
            "readme-demo-assets-YYYY-MM-DD",
            "uv build",
            "junas-<version>.tar.gz",
            "junas-<version>-py3-none-any.whl",
            "GitHub release",
        ):
            self.assertIn(token, text)

    def test_changelog_keeps_demo_assets_separate_from_install_releases(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

        self.assertIn("Demo-asset tags", text)
        self.assertIn("not install releases", text)
        self.assertIn("No signed macOS DMG, Homebrew formula, Nix package, or Cargo artifact", text)


if __name__ == "__main__":
    unittest.main()
