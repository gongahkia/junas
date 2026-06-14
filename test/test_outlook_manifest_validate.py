import tempfile
import unittest
from pathlib import Path

from scripts.render_outlook_manifest import TEMPLATE, render_manifest
from scripts.validate_outlook_manifest import main, validate_manifest


class OutlookManifestValidateTests(unittest.TestCase):
    def write_rendered(self, origin: str) -> Path:
        path = Path(self.tmp.name) / "manifest.xml"
        path.write_text(render_manifest(TEMPLATE, profile="production", origin=origin), encoding="utf-8")
        return path

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_accepts_rendered_production_manifest(self):
        path = self.write_rendered("https://outlook-addin.example.com")

        self.assertEqual(validate_manifest(path, profile="production"), [])

    def test_rejects_unrendered_template(self):
        errors = validate_manifest(TEMPLATE, profile="dev")

        self.assertTrue(any("unrendered placeholder" in error for error in errors))

    def test_rejects_production_localhost(self):
        path = self.write_rendered("https://localhost:3000")

        errors = validate_manifest(path, profile="production")

        self.assertTrue(any("production host cannot be localhost" in error for error in errors))

    def test_cli_returns_nonzero_for_wrong_send_mode(self):
        path = self.write_rendered("https://outlook-addin.example.com")

        self.assertEqual(main([str(path), "--profile", "production", "--expected-send-mode", "Block"]), 64)


if __name__ == "__main__":
    unittest.main()
