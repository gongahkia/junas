"""recall_gate.py --update writes an attribution line to recall.lock.history.jsonl
so an auditor can reconstruct who moved the baseline and why."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "recall_gate.py"
CORPUS_DIR = REPO_ROOT / "test" / "fixtures" / "legal-corpus"
HISTORY_PATH = CORPUS_DIR / "recall.lock.history.jsonl"


class RecallAttributionTests(unittest.TestCase):
    """The tests do not mutate the committed lock — they back up + restore
    recall.lock.json and recall.lock.history.jsonl around each run."""

    def setUp(self):
        self._lock_backup = (CORPUS_DIR / "recall.lock.json").read_text(encoding="utf-8")
        self._history_existed = HISTORY_PATH.exists()
        if self._history_existed:
            self._history_backup = HISTORY_PATH.read_text(encoding="utf-8")
        else:
            self._history_backup = None

    def tearDown(self):
        (CORPUS_DIR / "recall.lock.json").write_text(self._lock_backup, encoding="utf-8")
        if self._history_existed:
            HISTORY_PATH.write_text(self._history_backup or "", encoding="utf-8")
        elif HISTORY_PATH.exists():
            HISTORY_PATH.unlink()

    def _run(self, *args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True, text=True, env=env, cwd=REPO_ROOT,
        )

    def test_update_without_reason_exits_2(self):
        result = self._run("--update")
        self.assertEqual(result.returncode, 2, msg=result.stderr)
        self.assertIn("--reason", result.stderr)

    def test_update_with_reason_appends_history_entry(self):
        if HISTORY_PATH.exists():
            HISTORY_PATH.unlink()
        result = self._run(
            "--update", "--reason", "added 5 new SPA fixtures (Q2 corpus expansion)",
            env_extra={"JUNAS_RECALL_ACTOR": "audit-bot@example.com"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue(HISTORY_PATH.exists(), "expected history file to be created")
        lines = HISTORY_PATH.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[-1])
        self.assertEqual(entry["actor"], "audit-bot@example.com")
        self.assertEqual(entry["reason"], "added 5 new SPA fixtures (Q2 corpus expansion)")
        self.assertIn("ts", entry)
        # commit_sha is best-effort; in CI inside a git repo it'll be set, locally too
        self.assertIn("commit_sha", entry)

    def test_history_diff_records_changed_rules(self):
        if HISTORY_PATH.exists():
            HISTORY_PATH.unlink()
        # mutate the lock to simulate a deliberate baseline lowering, then re-run --update.
        # this proves the diff captures both old + new and isn't blank when baseline shifts.
        mutated = {"baseline_recall": {"named_person": 0.5}}
        (CORPUS_DIR / "recall.lock.json").write_text(
            json.dumps(mutated, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        result = self._run(
            "--update", "--reason", "test diff capture",
            env_extra={"JUNAS_RECALL_ACTOR": "tester@example.com"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        entry = json.loads(HISTORY_PATH.read_text(encoding="utf-8").strip().splitlines()[-1])
        diff = entry["diff"]
        current_lock = json.loads(self._lock_backup)
        expected_named_person = current_lock["baseline_recall"]["named_person"]
        # named_person moved 0.5 -> the current committed baseline.
        self.assertIn("named_person", diff)
        self.assertEqual(diff["named_person"]["old"], 0.5)
        self.assertEqual(diff["named_person"]["new"], expected_named_person)
        # the rest of the rules were added from the committed lock.
        added_rules = [r for r, d in diff.items() if d.get("old") is None]
        self.assertTrue(added_rules, f"expected added rules in diff: {diff}")


if __name__ == "__main__":
    unittest.main()
