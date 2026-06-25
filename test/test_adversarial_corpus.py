"""Adversarial corpus gate — recall + precision both held at the locked baseline.

The adversarial corpus exists to surface precision regressions (rules that fire on text the
labels file specifically says they should NOT). Recall is checked too, but the headline
contract is precision: when a rule's precision drops below the lock, the gate fails."""

import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ADVERSARIAL_DIR = REPO_ROOT / "test" / "fixtures" / "legal-corpus-adversarial"


class AdversarialCorpusGateTests(unittest.TestCase):
    def test_adversarial_gate_passes_against_locked_baseline(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "recall_gate.py"),
                "--corpus", str(ADVERSARIAL_DIR),
            ],
            capture_output=True, text=True, env=env, cwd=REPO_ROOT,
        )
        self.assertEqual(
            result.returncode, 0,
            msg=f"adversarial gate failed: stdout={result.stdout}\nstderr={result.stderr}",
        )

    def test_adversarial_corpus_has_fixtures_and_lock(self):
        self.assertTrue(ADVERSARIAL_DIR.exists())
        fixtures = sorted(ADVERSARIAL_DIR.glob("*.txt"))
        self.assertGreaterEqual(len(fixtures), 3, "expected ≥3 adversarial fixtures")
        for fixture in fixtures:
            labels = fixture.with_suffix(".labels.json")
            self.assertTrue(labels.exists(), f"missing labels for {fixture.name}")
        self.assertTrue((ADVERSARIAL_DIR / "recall_adversarial.lock.json").exists())


if __name__ == "__main__":
    unittest.main()
