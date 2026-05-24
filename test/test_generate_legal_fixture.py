"""Smoke tests for scripts/generate_legal_fixture.py.

The script wraps OpenAI; the harness only exercises --dry-run (no network) and CLI validation.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class GenerateLegalFixtureTests(unittest.TestCase):
    def _run(self, *args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "generate_legal_fixture.py"), *args],
            capture_output=True, text=True, env=env, cwd=REPO_ROOT,
        )

    def test_dry_run_emits_constraints(self):
        result = self._run("spa", "--dry-run")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Share Purchase Agreement", result.stdout)
        self.assertIn("fictional Singapore NRIC", result.stdout)
        self.assertIn("fictional UEN", result.stdout)

    def test_dry_run_adversarial_includes_obfuscation_clause(self):
        result = self._run("memo", "--adversarial", "--dry-run")
        self.assertEqual(result.returncode, 0)
        self.assertIn("obfuscated identifier", result.stdout)
        self.assertIn("project plan", result.stdout)

    def test_dry_run_multilingual_includes_name_diversity_clause(self):
        result = self._run("sha", "--multilingual", "--dry-run")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Malay name", result.stdout)

    def test_missing_api_key_returns_2(self):
        # remove key from env so script bails out before any network call.
        result = self._run("spa", "--slug", "spa_99", env_extra={"OPENAI_API_KEY": ""})
        self.assertEqual(result.returncode, 2)
        self.assertIn("OPENAI_API_KEY", result.stderr)

    def test_unknown_doc_type_is_rejected_by_argparse(self):
        result = self._run("not_a_real_doc_type", "--dry-run")
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
