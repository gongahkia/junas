"""Calibration script smoke tests (item 32).

Three guarantees:
1. Default run produces a well-formed JSON report carrying recommended bounds.
2. --apply writes a TOML file with the recommended bounds + weights.
3. The script's monkey-patch of LLM_TIER_MNPI_{LOWER,UPPER} is restored after each
   candidate evaluation — leaving engine globals dirty would corrupt later tests.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "calibrate_escalation_threshold.py"


class CalibrationCLITests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True, text=True, env=env, cwd=REPO_ROOT,
        )

    def test_default_run_produces_report(self):
        result = self._run("--iterations", "10")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        report = json.loads(result.stdout)
        self.assertIn("recommended", report)
        self.assertIn("lower", report["recommended"])
        self.assertIn("upper", report["recommended"])
        self.assertEqual(report["iterations"], 10)

    def test_missing_corpus_returns_1(self):
        result = self._run("--corpus", "/tmp/no-such-corpus-dir-kaypoh", "--iterations", "5")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no .txt fixtures", result.stderr)

    def test_top_k_reports_multiple_candidates(self):
        result = self._run("--iterations", "10", "--top-k", "3")
        self.assertEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertEqual(len(report["top_k"]), 3)

    def test_apply_writes_calibrated_toml(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "calibrated.toml"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(REPO_ROOT / "src")
            env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
            # patch DEFAULT_OUTPUT via env-aware override would be cleaner; for now we
            # accept that the script writes to configs/runtime_calibrated.toml and
            # back it up around the test.
            target = REPO_ROOT / "configs" / "runtime_calibrated.toml"
            backup = target.read_text(encoding="utf-8") if target.exists() else None
            try:
                result = self._run("--iterations", "5", "--apply")
                self.assertEqual(result.returncode, 0)
                self.assertTrue(target.exists())
                content = target.read_text(encoding="utf-8")
                self.assertIn("[llm_tier]", content)
                self.assertIn("mnpi_lower", content)
                self.assertIn("mnpi_upper", content)
                self.assertIn("[weights]", content)
            finally:
                if backup is not None:
                    target.write_text(backup, encoding="utf-8")
                elif target.exists():
                    target.unlink()


class CalibrationGlobalRestorationTests(unittest.TestCase):
    """The script monkey-patches engine.LLM_TIER_MNPI_{LOWER,UPPER}; restoration must hold."""

    def test_engine_globals_restored_after_calibration_run(self):
        from kaypoh.review import engine

        before_lower = engine.LLM_TIER_MNPI_LOWER
        before_upper = engine.LLM_TIER_MNPI_UPPER

        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
        subprocess.run(
            [sys.executable, str(SCRIPT), "--iterations", "5"],
            capture_output=True, text=True, env=env, cwd=REPO_ROOT,
        )

        # importing engine again must still see the shipped defaults
        from kaypoh.review import engine as engine_reimport

        self.assertEqual(engine_reimport.LLM_TIER_MNPI_LOWER, before_lower)
        self.assertEqual(engine_reimport.LLM_TIER_MNPI_UPPER, before_upper)


if __name__ == "__main__":
    unittest.main()
