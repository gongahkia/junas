import tempfile
import unittest
from pathlib import Path

from scripts.render_outlook_manifest import TEMPLATE, main, origin_for_profile, render_manifest


class OutlookManifestRenderTests(unittest.TestCase):
    def test_template_uses_origin_placeholder_instead_of_localhost(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("{{KAYPOH_OUTLOOK_ADDIN_ORIGIN}}/taskpane.html", text)
        self.assertNotIn("https://localhost:3000", text)

    def test_render_manifest_replaces_all_origin_placeholders(self):
        rendered = render_manifest(TEMPLATE, profile="staging", origin="https://addin.example.com")

        self.assertIn('DefaultValue="https://addin.example.com/taskpane.html"', rendered)
        self.assertIn('DefaultValue="https://addin.example.com/commands.html"', rendered)
        self.assertIn('DefaultValue="https://addin.example.com/launchevent.js"', rendered)
        self.assertNotIn("{{KAYPOH_OUTLOOK_ADDIN_ORIGIN}}", rendered)

    def test_staging_and_production_require_non_local_https_origin(self):
        with self.assertRaises(ValueError):
            origin_for_profile("staging", None)
        with self.assertRaises(ValueError):
            origin_for_profile("production", "http://addin.example.com")
        with self.assertRaises(ValueError):
            origin_for_profile("production", "https://localhost:3000")

        self.assertEqual(origin_for_profile("dev", None), "https://localhost:3000")

    def test_cli_writes_profile_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "manifest.xml"
            rc = main(["--profile", "staging", "--origin", "https://addin.example.com", "--output", str(output)])

            self.assertEqual(rc, 0)
            self.assertTrue(output.exists())
            text = output.read_text(encoding="utf-8")
            self.assertIn("https://addin.example.com/taskpane.html", text)


if __name__ == "__main__":
    unittest.main()
