import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.candidate_review import (
    collect_review_status_violations,
    labels_path_for,
    record_human_review,
    write_labels,
)
from scripts.promote_candidate_fixtures import MANIFEST_NAME, promote_candidates
from scripts.recall_gate import main as recall_gate_main
from scripts.review_candidate_fixture import main as review_candidate_main


def _fixture_labels(*, review_status: str = "pending") -> dict:
    return {
        "doc_id": "sg_candidate_review_001",
        "document_type": "memo",
        "source_jurisdiction": "SG",
        "destination_jurisdiction": "SG",
        "must_detect": [
            {"category": "PII", "rule": "sg_nric_fin", "matched_text": "S1234567D"},
        ],
        "must_not_detect": [],
        "uncertain": [],
        "_taxonomy_concept": "direct_identifier",
        "_label_source": "openai:test-auto",
        "_label_model": "test-model",
        "_human_review_status": review_status,
    }


def _write_fixture(root: Path, *, name: str = "sg_candidate_review_001.txt") -> Path:
    fixture = root / name
    fixture.write_text("Send Dr Jane Tan S1234567D before announcement.\n", encoding="utf-8")
    write_labels(labels_path_for(fixture), _fixture_labels())
    return fixture


def _quiet_main(main_func, argv: list[str]) -> int:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        return main_func(argv)


class CandidateReviewWorkflowTests(unittest.TestCase):
    def test_review_metadata_moves_candidate_label_from_pending_to_approved(self):
        labels = _fixture_labels()
        self.assertTrue(collect_review_status_violations_for_payload(labels))

        updated = record_human_review(
            labels,
            decision="approve",
            reviewer="legal-reviewer@example.com",
            notes="NRIC label checked against text span.",
            reviewed_at="2026-05-28T00:00:00Z",
        )

        self.assertEqual(updated["_human_review_status"], "approved")
        self.assertEqual(updated["_human_review"]["reviewer"], "legal-reviewer@example.com")
        self.assertEqual(updated["_human_review_history"][0]["decision"], "approve")
        self.assertFalse(collect_review_status_violations_for_payload(updated))

    def test_review_status_check_flags_pending_auto_labels_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp)
            fixture = _write_fixture(corpus)

            violations = collect_review_status_violations(corpus)
            self.assertEqual(len(violations), 1)
            self.assertIn("human_review_status=pending", violations[0])

            labels = json.loads(labels_path_for(fixture).read_text(encoding="utf-8"))
            record_human_review(labels, decision="approve", reviewer="counsel@example.com")
            write_labels(labels_path_for(fixture), labels)

            self.assertEqual(collect_review_status_violations(corpus), [])

    def test_review_cli_show_only_does_not_require_decision_or_reviewer(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _write_fixture(Path(tmp))
            result = _quiet_main(review_candidate_main, [str(fixture), "--show-only"])
            self.assertEqual(result, 0)

    def test_promotion_copies_only_human_approved_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate_dir = root / "candidates"
            target_dir = root / "reviewed"
            candidate_dir.mkdir()
            fixture = _write_fixture(candidate_dir)

            pending_result = promote_candidates(candidate_dir=candidate_dir, target_dir=target_dir)
            self.assertEqual(pending_result["promoted"], [])
            self.assertEqual(pending_result["skipped"][0]["reason"], "not_approved:pending")
            self.assertFalse(target_dir.exists())

            labels = json.loads(labels_path_for(fixture).read_text(encoding="utf-8"))
            record_human_review(labels, decision="approve", reviewer="counsel@example.com")
            write_labels(labels_path_for(fixture), labels)

            approved_result = promote_candidates(candidate_dir=candidate_dir, target_dir=target_dir)
            self.assertEqual(len(approved_result["promoted"]), 1)
            self.assertTrue((target_dir / fixture.name).exists())
            promoted_labels = json.loads((target_dir / labels_path_for(fixture).name).read_text(encoding="utf-8"))
            self.assertEqual(promoted_labels["_promotion"]["reviewer"], "counsel@example.com")
            manifest = target_dir / MANIFEST_NAME
            self.assertEqual(len(manifest.read_text(encoding="utf-8").strip().splitlines()), 1)

            collision_result = promote_candidates(candidate_dir=candidate_dir, target_dir=target_dir)
            self.assertEqual(len(collision_result["errors"]), 1)
            self.assertIn("refusing to overwrite", collision_result["errors"][0])

    def test_recall_gate_human_review_guard_blocks_unapproved_and_ambiguous_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp)
            fixture = _write_fixture(corpus)

            pending_result = _quiet_main(
                recall_gate_main,
                [
                    "--corpus",
                    str(corpus),
                    "--update",
                    "--reason",
                    "candidate human review baseline",
                    "--require-human-reviewed",
                ],
            )
            self.assertEqual(pending_result, 2)
            self.assertFalse((corpus / f"{corpus.name}.lock.json").exists())

            labels = json.loads(labels_path_for(fixture).read_text(encoding="utf-8"))
            record_human_review(labels, decision="approve", reviewer="counsel@example.com")
            write_labels(labels_path_for(fixture), labels)

            ambiguous_reason = _quiet_main(
                recall_gate_main,
                [
                    "--corpus",
                    str(corpus),
                    "--update",
                    "--reason",
                    "added SG fixture",
                    "--require-human-reviewed",
                ],
            )
            self.assertEqual(ambiguous_reason, 2)

            approved_result = _quiet_main(
                recall_gate_main,
                [
                    "--corpus",
                    str(corpus),
                    "--update",
                    "--reason",
                    "candidate human-reviewed SG fixture promotion",
                    "--require-human-reviewed",
                ],
            )
            self.assertEqual(approved_result, 0)
            self.assertTrue((corpus / f"{corpus.name}.lock.json").exists())


def collect_review_status_violations_for_payload(labels: dict) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        corpus = Path(tmp)
        fixture = corpus / "payload.txt"
        fixture.write_text("Send Dr Jane Tan S1234567D.\n", encoding="utf-8")
        write_labels(labels_path_for(fixture), labels)
        return collect_review_status_violations(corpus)


if __name__ == "__main__":
    unittest.main()
