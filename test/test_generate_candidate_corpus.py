import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts import generate_candidate_corpus
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


if __name__ == "__main__":
    unittest.main()
