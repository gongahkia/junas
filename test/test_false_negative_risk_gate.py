import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.check_false_negative_risk import (
    DEFAULT_CORPORA,
    path_triggers_false_negative_gate,
    run_recall_gates,
    triggered_paths,
)


class FalseNegativeRiskGateTests(unittest.TestCase):
    def test_policy_rewrite_and_backend_paths_trigger_gate(self):
        self.assertTrue(path_triggers_false_negative_gate("src/junas/policy/engine.py"))
        self.assertTrue(path_triggers_false_negative_gate("src/junas/anonymize/engine.py"))
        self.assertTrue(path_triggers_false_negative_gate("src/junas/backend/main.py"))
        self.assertFalse(path_triggers_false_negative_gate("docs/feedback-loop.md"))
        self.assertFalse(path_triggers_false_negative_gate("test/test_policy_engine.py"))

    def test_triggered_paths_filters_changed_files(self):
        result = triggered_paths([
            "docs/feedback-loop.md",
            "src/junas/policy/config.py",
            "src/junas/anonymize/mapping_store.py",
        ])

        self.assertEqual(result, [
            "src/junas/anonymize/mapping_store.py",
            "src/junas/policy/config.py",
        ])

    def test_default_corpora_include_locked_legal_sets(self):
        corpus_names = {path.as_posix() for path in DEFAULT_CORPORA}

        self.assertIn("test/fixtures/legal-corpus", corpus_names)
        self.assertIn("test/fixtures/legal-corpus-adversarial", corpus_names)
        self.assertIn("test/fixtures/legal-corpus-reviewed-candidates", corpus_names)
        self.assertNotIn("test/fixtures/legal-corpus-candidates", corpus_names)

    def test_run_recall_gates_invokes_recall_gate_for_each_corpus(self):
        completed = type(
            "Completed",
            (),
            {"returncode": 0, "stdout": "ok", "stderr": ""},
        )()
        with patch("scripts.check_false_negative_risk.subprocess.run", return_value=completed) as run:
            results = run_recall_gates([Path("corpus-a"), Path("corpus-b")])

        self.assertEqual([item["returncode"] for item in results], [0, 0])
        self.assertEqual(run.call_count, 2)
        first_command = run.call_args_list[0].args[0]
        self.assertEqual(first_command[0], sys.executable)
        self.assertIn("recall_gate.py", first_command[1])
        self.assertEqual(first_command[-2:], ["--corpus", str(Path.cwd() / "corpus-a")])


if __name__ == "__main__":
    unittest.main()
