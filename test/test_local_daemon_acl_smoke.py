import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class LocalDaemonAclSmokeTests(unittest.TestCase):
    def test_smoke_command_passes(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "smoke_local_daemon_acl.py")],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn('"ok": true', result.stdout)
        self.assertIn("cors_preflight_allowed", result.stdout)


if __name__ == "__main__":
    unittest.main()
