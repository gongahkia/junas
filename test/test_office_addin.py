import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFICE = ROOT / "packaging" / "office_addin"


class OfficeAddinTests(unittest.TestCase):
    def test_taskpane_exposes_token_storage_controls(self):
        html = (OFFICE / "taskpane.html").read_text(encoding="utf-8")
        self.assertIn('id="endpoint"', html)
        self.assertIn('id="token"', html)
        self.assertIn('type="password"', html)
        self.assertIn('id="saveSettings"', html)
        self.assertIn('id="checkPairing"', html)

    def test_taskpane_persists_token_and_sets_local_header(self):
        js = (OFFICE / "taskpane.js").read_text(encoding="utf-8")
        self.assertIn("OfficeRuntime?.storage", js)
        self.assertIn("localStorage.setItem", js)
        self.assertIn("kaypoh.localToken", js)
        self.assertIn('headers["X-Kaypoh-Local-Token"] = currentConfig.token', js)

    def test_taskpane_can_check_pairing_status(self):
        js = (OFFICE / "taskpane.js").read_text(encoding="utf-8")
        self.assertIn("/local/pairing/status", js)
        self.assertIn("token_provisioned", js)
        self.assertIn("acl_enabled", js)


if __name__ == "__main__":
    unittest.main()
