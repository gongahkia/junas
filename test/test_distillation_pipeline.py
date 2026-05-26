import pytest

pytest.skip(
    "legacy classifier pipeline archived 2026-05-26; "
    "see ARCHITECTURE-PIVOT-24-MAY.md item 63. Tests reference layer1-6 / mosaic "
    "/ legacy classify shape and need rewriting against the engine.review() wrapper.",
    allow_module_level=True,
)

"""End-to-end smoke tests for the distillation pipeline (item 29).

Four components, all tested with mocked LLMs so no real teacher / GPU is required:

1. Shared prompts module: shape parity between training and inference.
2. teacher_collector.py: walks corpora, emits JSONL, ledger, idempotency.
3. distill_train.py --dry-run: dataset validation catches degenerate datasets.
4. eval_against_corpus.py: agreement metrics + invariant violation detection.
5. local_distilled provider: routed via LocalLLMAdjudicator without breaking
   the existing provider gates.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent


class SharedPromptsTests(unittest.TestCase):
    def test_raw_text_messages_carry_document_text(self):
        from training.distillation.prompts import build_messages

        msgs = build_messages(
            input_mode="raw_text",
            text="confidential text",
            current_classification="LOW_RISK",
        )
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertIn("confidential text", msgs[1]["content"])

    def test_structured_tokens_messages_omit_raw_text(self):
        from training.distillation.prompts import build_messages

        msgs = build_messages(
            input_mode="structured_tokens",
            text="confidential text",
            current_classification="LOW_RISK",
            structured_query={
                "mode": "structured_tokens",
                "body_hash": "abc",
                "findings": [],
                "entity_id": "",
                "public_evidence_summary": {"status": "skipped", "source_count": 0,
                                            "blocked_query_count": 0},
                "current_classification": "LOW_RISK",
            },
        )
        self.assertNotIn("confidential text", msgs[1]["content"])
        self.assertIn("abc", msgs[1]["content"])

    def test_structured_tokens_requires_structured_query(self):
        from training.distillation.prompts import build_messages

        with self.assertRaises(ValueError):
            build_messages(
                input_mode="structured_tokens",
                text="x",
                current_classification="SAFE",
                structured_query=None,
            )

    def test_build_target_produces_canonical_json(self):
        from training.distillation.prompts import build_target

        verdict = {
            "risk_label": "LOW_RISK",
            "public_status": "ambiguous",
            "confidence": 0.7,
            "materiality_reason": "borderline",
        }
        target = build_target(verdict)
        self.assertEqual(json.loads(target)["risk_label"], "LOW_RISK")
        # canonical: sorted keys, defaults filled in
        self.assertIn("matched_public_sources", target)
        # idempotent: same verdict -> same target
        self.assertEqual(target, build_target(verdict))


class TeacherCollectorCLITests(unittest.TestCase):
    def _run(self, *args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PYTHONPATH"] = f"{REPO_ROOT / 'src'}:{REPO_ROOT}"
        env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "training" / "distillation" / "teacher_collector.py"),
             *args],
            capture_output=True, text=True, env=env, cwd=REPO_ROOT,
        )

    def test_mock_provider_emits_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "teacher.jsonl"
            journal = Path(tmp) / "journal"
            result = self._run(
                "--corpus", "test/fixtures/legal-corpus",
                "--output", str(output),
                "--provider", "mock",
                env_extra={"KAYPOH_JOURNAL_DIR": str(journal)},
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["rows_written"], 6)
            self.assertEqual(report["errors"], 0)
            self.assertTrue(output.exists())
            rows = output.read_text().strip().splitlines()
            self.assertEqual(len(rows), 6)
            first = json.loads(rows[0])
            self.assertIn("text_hash", first)
            self.assertIn("user_content", first)
            self.assertEqual(first["teacher_verdict"]["status"], "adjudicated")
            self.assertEqual(first["teacher_verdict"]["provider"], "mock")

    def test_idempotent_re_run_skips_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "teacher.jsonl"
            journal = Path(tmp) / "journal"
            # first run
            self._run(
                "--corpus", "test/fixtures/legal-corpus",
                "--output", str(output),
                "--provider", "mock",
                env_extra={"KAYPOH_JOURNAL_DIR": str(journal)},
            )
            # second run should write zero new rows
            r2 = self._run(
                "--corpus", "test/fixtures/legal-corpus",
                "--output", str(output),
                "--provider", "mock",
                env_extra={"KAYPOH_JOURNAL_DIR": str(journal)},
            )
            self.assertEqual(r2.returncode, 0)
            self.assertEqual(json.loads(r2.stdout)["rows_written"], 0)
            # ledger should record both "collected" and "skipped" events
            ledger_lines = (journal / "training_ledger.jsonl").read_text().strip().splitlines()
            statuses = {json.loads(line)["status"] for line in ledger_lines}
            self.assertIn("collected", statuses)
            self.assertIn("skipped", statuses)

    def test_missing_corpus_returns_2(self):
        result = self._run(
            "--corpus", "/tmp/no-such-kaypoh-corpus",
            "--output", "/tmp/never-written.jsonl",
            "--provider", "mock",
        )
        self.assertEqual(result.returncode, 2)


class DistillTrainDryRunTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PYTHONPATH"] = f"{REPO_ROOT / 'src'}:{REPO_ROOT}"
        env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "training" / "distillation" / "distill_train.py"),
             *args],
            capture_output=True, text=True, env=env, cwd=REPO_ROOT,
        )

    def _make_diverse_dataset(self, path: Path) -> None:
        rows = []
        for i, label in enumerate(["SAFE", "LOW_RISK", "HIGH_RISK", "SAFE", "HIGH_RISK"]):
            rows.append({
                "doc_id": f"doc-{i}",
                "text_hash": f"hash-{i}",
                "document_type": "memo",
                "source_jurisdiction": "SG",
                "destination_jurisdiction": "SG",
                "input_mode": "raw_text",
                "user_content": json.dumps({"document_text": f"sample {i}", "runtime_context": {}}),
                "teacher_verdict": {
                    "status": "adjudicated",
                    "risk_label": label,
                    "public_status": "ambiguous",
                    "confidence": 0.5,
                    "materiality_reason": "test",
                    "matched_public_sources": [],
                    "unverified_claims": [],
                    "review_recommendation": "ok",
                    "provider": "mock",
                    "model": "mock",
                },
            })
        path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    def test_dry_run_validates_diverse_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "ds.jsonl"
            self._make_diverse_dataset(dataset)
            result = self._run("--dataset", str(dataset), "--dry-run", "--min-rows", "3")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["validation_errors"], [])
            self.assertFalse(report["would_train"])  # dry-run never trains

    def test_dry_run_rejects_single_label_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "ds.jsonl"
            rows = [{
                "doc_id": "d", "text_hash": "h", "document_type": "memo",
                "source_jurisdiction": "SG", "destination_jurisdiction": "SG",
                "input_mode": "raw_text",
                "user_content": "{}",
                "teacher_verdict": {"status": "adjudicated", "risk_label": "HIGH_RISK",
                                    "public_status": "ambiguous", "confidence": 0.5,
                                    "materiality_reason": "x", "matched_public_sources": [],
                                    "unverified_claims": [], "review_recommendation": "ok"},
            } for _ in range(5)]
            dataset.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            result = self._run("--dataset", str(dataset), "--dry-run", "--min-rows", "3")
            self.assertEqual(result.returncode, 1)
            report = json.loads(result.stdout)
            self.assertTrue(any("single risk_label" in e for e in report["validation_errors"]))

    def test_dry_run_rejects_too_few_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "ds.jsonl"
            self._make_diverse_dataset(dataset)
            result = self._run("--dataset", str(dataset), "--dry-run", "--min-rows", "100")
            self.assertEqual(result.returncode, 1)


class StudentEvalTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PYTHONPATH"] = f"{REPO_ROOT / 'src'}:{REPO_ROOT}"
        env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "training" / "distillation" / "eval_against_corpus.py"),
             *args],
            capture_output=True, text=True, env=env, cwd=REPO_ROOT,
        )

    def test_mock_student_perfect_agreement(self):
        result = self._run(
            "--corpus", "test/fixtures/legal-corpus",
            "--student-provider", "mock",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["overall"]["agreement_rate"], 1.0)
        self.assertEqual(report["overall"]["invariant_violations"], 0)

    def test_min_agreement_threshold_fails_when_underperforming(self):
        # mock student has 100% agreement, so this only fails if we set min_agreement > 1.0
        result = self._run(
            "--corpus", "test/fixtures/legal-corpus",
            "--student-provider", "mock",
            "--min-agreement", "1.5",  # impossible
        )
        self.assertEqual(result.returncode, 1)

    def test_local_distilled_requires_adapter_path(self):
        result = self._run(
            "--corpus", "test/fixtures/legal-corpus",
            "--student-provider", "local_distilled",
        )
        self.assertEqual(result.returncode, 2)


class LocalDistilledProviderTests(unittest.TestCase):
    """The LocalLLMAdjudicator routes provider=local_distilled to the student
    backend. Verify routing + missing-adapter handling without loading any model."""

    def _settings(self, *, adapter_path: str = "") -> SimpleNamespace:
        return SimpleNamespace(
            enabled=True,
            provider="local_distilled",
            api_key="",
            base_url="",
            model="local-distilled",
            timeout_seconds=2.0,
            allow_remote_base_url=False,
            tenant_opt_in_openai=False,
            llm_input_mode="raw_text",
            distilled_adapter_path=adapter_path,
            distilled_base_model="Qwen/Qwen2.5-1.5B-Instruct",
        )

    def test_missing_adapter_path_returns_error(self):
        from kaypoh.workflow.layer8_llm_adjudicator.inference import LocalLLMAdjudicator

        adj = LocalLLMAdjudicator(self._settings(adapter_path=""))
        result = adj.adjudicate(text="x", current_classification="LOW_RISK")
        self.assertEqual(result["status"], "error")
        self.assertIn("DISTILLED_ADAPTER_PATH", result["review_recommendation"])

    def test_invalid_adapter_path_returns_error_not_raise(self):
        from kaypoh.workflow.layer8_llm_adjudicator.inference import LocalLLMAdjudicator

        adj = LocalLLMAdjudicator(self._settings(adapter_path="/tmp/no-such-adapter-dir-kp"))
        result = adj.adjudicate(text="x", current_classification="LOW_RISK")
        # adapter load triggers torch import inside student_provider; will fail with
        # either ImportError or FileNotFoundError. either way: status=error, no crash.
        self.assertEqual(result["provider"], "local_distilled")
        self.assertIn(result["status"], {"error", "disabled"})

    def test_local_distilled_in_provider_allowlist(self):
        # provider validation in runtime.py must accept the new provider; checked
        # by direct dict membership rather than spinning up config loader.
        from kaypoh.workflow.layer8_llm_adjudicator.inference import LocalLLMAdjudicator

        adj = LocalLLMAdjudicator(self._settings(adapter_path=""))
        # unsupported provider would return an "unsupported LLM provider" error;
        # local_distilled instead returns the missing-adapter-path error, proving
        # the routing branch was taken.
        result = adj.adjudicate(text="x", current_classification="LOW_RISK")
        self.assertNotIn("unsupported", result["review_recommendation"])


if __name__ == "__main__":
    unittest.main()
