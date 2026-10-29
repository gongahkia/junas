import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.check_precision_risk import (
    DEFAULT_CORPORA,
    path_triggers_precision_gate,
    precision_baseline_rules,
    run_precision_gates,
    triggered_paths,
)


class PrecisionRiskGateTests(unittest.TestCase):
    def test_detector_and_pipeline_paths_trigger_gate(self):
        self.assertTrue(path_triggers_precision_gate("src/junas/review/detectors/identifiers.py"))
        self.assertTrue(path_triggers_precision_gate("src/junas/review/jurisdictions_data/SG.toml"))
        self.assertTrue(path_triggers_precision_gate("src/junas/models.py"))
        self.assertTrue(path_triggers_precision_gate("src/junas/pipeline.py"))
        self.assertFalse(path_triggers_precision_gate("test/test_core_pipeline.py"))
        self.assertFalse(path_triggers_precision_gate("docs/README.md"))

    def test_triggered_paths_filters_changed_files(self):
        result = triggered_paths(
            [
                "docs/README.md",
                "src/junas/review/engine.py",
                "src/junas/pipeline.py",
            ]
        )

        self.assertEqual(
            result,
            [
                "src/junas/pipeline.py",
                "src/junas/review/engine.py",
            ],
        )

    def test_default_corpora_have_precision_locks_and_exclude_candidates(self):
        corpus_names = {path.as_posix() for path in DEFAULT_CORPORA}

        self.assertIn("test/fixtures/legal-corpus", corpus_names)
        self.assertIn("test/fixtures/legal-corpus-adversarial", corpus_names)
        self.assertIn("test/fixtures/legal-corpus-reviewed-candidates", corpus_names)
        self.assertNotIn("test/fixtures/legal-corpus-candidates", corpus_names)
        for corpus in DEFAULT_CORPORA:
            self.assertGreater(len(precision_baseline_rules(corpus)), 0, corpus.as_posix())

    def test_precision_baseline_rules_requires_baseline_precision(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / "sample"
            corpus.mkdir()
            (corpus / "sample.lock.json").write_text('{"baseline_recall":{"x":1.0}}\n', encoding="utf-8")

            self.assertEqual(precision_baseline_rules(corpus), [])

    def test_run_precision_gates_invokes_recall_gate_for_each_precision_corpus(self):
        completed = type(
            "Completed",
            (),
            {"returncode": 0, "stdout": "ok", "stderr": ""},
        )()
        with (
            patch("scripts.check_precision_risk.precision_baseline_rules", return_value=["email_address"]),
            patch("scripts.check_precision_risk.subprocess.run", return_value=completed) as run,
        ):
            results = run_precision_gates([Path("corpus-a"), Path("corpus-b")])

        self.assertEqual([item["returncode"] for item in results], [0, 0])
        self.assertEqual([item["precision_rule_count"] for item in results], [1, 1])
        self.assertEqual(run.call_count, 2)
        first_command = run.call_args_list[0].args[0]
        self.assertEqual(first_command[0], sys.executable)
        self.assertIn("recall_gate.py", first_command[1])
        self.assertEqual(first_command[-2:], ["--corpus", str(Path.cwd() / "corpus-a")])

    def test_run_precision_gates_fails_when_precision_lock_missing(self):
        with patch("scripts.check_precision_risk.precision_baseline_rules", return_value=[]):
            results = run_precision_gates([Path("corpus-a")])

        self.assertEqual(results[0]["returncode"], 2)
        self.assertEqual(results[0]["stderr"], "precision baseline missing")


if __name__ == "__main__":
    unittest.main()
