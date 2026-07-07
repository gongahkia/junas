import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class AuditPackSmokeTests(unittest.TestCase):
    def test_smoke_command_exports_and_verifies_pack(self):
        with tempfile.TemporaryDirectory(prefix="junas-audit-smoke-test-") as tmp:
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "smoke_audit_pack.py"), "--output-dir", tmp],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn('"ok": true', result.stdout)
            self.assertIn("status: valid", result.stdout)
            payload = json.loads(result.stdout)
            pack_path = Path(payload["pack_path"])
            with zipfile.ZipFile(pack_path) as archive:
                names = set(archive.namelist())
                findings = archive.read("findings.json").decode("utf-8")
            self.assertIn("defensibility_manifest.json", names)
            self.assertIn("statutory-coverage.md", names)
            self.assertNotIn("Dr Jane Tan", findings)
            self.assertIn("matched_text_sha256", findings)


if __name__ == "__main__":
    unittest.main()
