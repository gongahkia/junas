import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from scripts import candidate_run_ledger, generate_candidate_corpus, run_candidate_corpus_pipeline
from scripts.fixture_taxonomy import CONCEPTS, JURISDICTIONS


class GenerateCandidateCorpusTests(unittest.TestCase):
    def test_plan_targets_missing_indices_instead_of_adding_more(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            cell_dir = out_dir / "sg" / "direct_identifiers"
            cell_dir.mkdir(parents=True)
            (cell_dir / "sg_direct_identifiers_memo_default_001.txt").write_text("one\n", encoding="utf-8")
            (cell_dir / "sg_direct_identifiers_memo_default_003.txt").write_text("three\n", encoding="utf-8")

            plan = generate_candidate_corpus.plan_candidate_matrix(
                out_dir=out_dir,
                jurisdictions=("SG",),
                concepts=("direct_identifiers",),
                doc_types=("memo",),
                variants=("default",),
                target_count=3,
            )

        self.assertEqual([item.slug for item in plan], ["sg_direct_identifiers_memo_default_002"])

    def test_expected_saturation_profile_size_is_4284(self):
        total = generate_candidate_corpus.expected_matrix_size(
            jurisdictions=tuple(JURISDICTIONS),
            concepts=tuple(CONCEPTS),
            doc_types=generate_candidate_corpus.DEFAULT_DOC_TYPES,
            variants=generate_candidate_corpus.DEFAULT_VARIANTS,
            target_count=3,
        )
        self.assertEqual(total, 4284)

    def test_saturation_dry_run_writes_complete_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = generate_candidate_corpus.main([
                    "--profile",
                    "saturation-4284",
                    "--provider",
                    "azure",
                    "--out-dir",
                    str(tmp_path / "candidates"),
                    "--manifest-dir",
                    str(tmp_path / "run"),
                    "--dry-run",
                ])

            manifest = tmp_path / "run" / "generation_plan.jsonl"
            line_count = len(manifest.read_text(encoding="utf-8").splitlines())

        self.assertEqual(result, 0)
        self.assertEqual(line_count, 4284)
        self.assertIn("planned=4284", stdout.getvalue())
        self.assertIn("--provider azure", stdout.getvalue())

    def test_negative_max_failures_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate_candidate_corpus.main([
                "--out-dir",
                str(Path(tmp) / "candidates"),
                "--max-failures",
                "-1",
                "--dry-run",
            ])
        self.assertEqual(result, 2)

class CandidatePipelineEnvTests(unittest.TestCase):
    def test_load_env_file_supports_unexported_and_exported_values_without_overriding(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "OPENAI_API_KEY=from-file\n"
                "export GPT5_MINI_ENDPOINT='https://example.test'\n"
                "GPT5_MINI_API_VERSION=\"2024-01-01\"\n",
                encoding="utf-8",
            )
            env_keys = ("OPENAI_API_KEY", "GPT5_MINI_ENDPOINT", "GPT5_MINI_API_VERSION")
            previous = {key: os.environ.get(key) for key in env_keys}
            try:
                os.environ["OPENAI_API_KEY"] = "already-set"
                os.environ.pop("GPT5_MINI_ENDPOINT", None)
                os.environ.pop("GPT5_MINI_API_VERSION", None)
                loaded = run_candidate_corpus_pipeline._load_env_file(env_path)
                self.assertEqual(loaded, 2)
                self.assertEqual(os.environ["OPENAI_API_KEY"], "already-set")
                self.assertEqual(os.environ["GPT5_MINI_ENDPOINT"], "https://example.test")
                self.assertEqual(os.environ["GPT5_MINI_API_VERSION"], "2024-01-01")
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

    def test_missing_env_groups_accepts_aliases(self):
        group = (("PRIMARY_MISSING", "SECONDARY_PRESENT"),)
        previous = os.environ.get("SECONDARY_PRESENT")
        try:
            os.environ["SECONDARY_PRESENT"] = "value"
            self.assertEqual(run_candidate_corpus_pipeline._missing_env_groups(group), [])
        finally:
            if previous is None:
                os.environ.pop("SECONDARY_PRESENT", None)
            else:
                os.environ["SECONDARY_PRESENT"] = previous

    def test_candidate_run_ledger_summarises_manifests_eval_and_cost_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            candidate_dir = root / "candidates"
            run_dir.mkdir()
            candidate_dir.mkdir()
            (candidate_dir / "sample.txt").write_text("Synthetic fixture text.\n", encoding="utf-8")
            (candidate_dir / "sample.labels.json").write_text('{"_human_review_status":"pending"}\n', encoding="utf-8")
            (run_dir / "pipeline_manifest.jsonl").write_text(
                '{"event":"finish","step":"generate","returncode":0,"elapsed_seconds":3}\n'
                '{"event":"finish","step":"autolabel","returncode":0,"elapsed_seconds":5}\n',
                encoding="utf-8",
            )
            (run_dir / "generation_manifest.jsonl").write_text(
                '{"event":"planned","slug":"sample"}\n'
                '{"event":"generated","slug":"sample"}\n'
                '{"event":"summary","expected":2,"planned":1,"generated":1,"failed":0,'
                '"skipped_existing_or_complete":1,"elapsed_seconds":3,"provider":"azure","model":"mini"}\n',
                encoding="utf-8",
            )
            (run_dir / "autolabel_manifest.jsonl").write_text(
                '{"event":"fixture","fixture":"sample.txt","status":"labeled","warnings":2}\n'
                '{"event":"summary","provider":"azure","model":"mini","label_model":"azure:mini",'
                '"labeled":1,"skipped":0,"errors":0,"elapsed_seconds":5,"workers":1}\n',
                encoding="utf-8",
            )
            (run_dir / "candidate_evaluation.json").write_text(
                '{"summary":{"doc_count":1,"candidate_recall":1.0,"candidate_precision":1.0}}\n',
                encoding="utf-8",
            )

            ledger = candidate_run_ledger.build_ledger(run_dir, candidate_dir=candidate_dir)

        self.assertEqual(ledger["pipeline"]["elapsed_seconds"], 8)
        self.assertEqual(ledger["generation"]["generated"], 1)
        self.assertEqual(ledger["generation"]["skipped_existing_or_complete"], 1)
        self.assertEqual(ledger["autolabel"]["labeled"], 1)
        self.assertEqual(ledger["autolabel"]["warnings"], 2)
        self.assertEqual(ledger["evaluation"]["summary"]["candidate_recall"], 1.0)
        self.assertEqual(ledger["cost"]["status"], "estimate_only_no_provider_token_usage")


if __name__ == "__main__":
    unittest.main()
