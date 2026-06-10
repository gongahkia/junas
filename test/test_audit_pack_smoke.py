import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class AuditPackSmokeTests(unittest.TestCase):
    def test_smoke_command_exports_and_verifies_pack(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "smoke_audit_pack.py")],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn('"ok": true', result.stdout)
        self.assertIn("status: valid", result.stdout)


if __name__ == "__main__":
    unittest.main()
