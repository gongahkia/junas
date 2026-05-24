import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class LegalCorpusRecallTests(unittest.TestCase):
    def test_recall_gate_passes_against_locked_baseline(self):
        # invoke the gate as a subprocess so failures surface in CI exactly as they would
        # at the pre-push hook layer. PYTHONPATH=src so the script sees the package.
        env_path_extension = str(REPO_ROOT / "src")
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "recall_gate.py")],
            capture_output=True,
            text=True,
            env={"PYTHONPATH": env_path_extension, "PATH": ""},
            cwd=REPO_ROOT,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"recall_gate exit={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
