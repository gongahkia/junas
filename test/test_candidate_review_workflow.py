import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.candidate_review import (
    collect_review_status_violations,
    collect_stage_b_readiness_violations,
    labels_path_for,
    record_human_review,
    write_labels,
)
from scripts.check_candidate_stage_gate import STAGE_B_DOCS, stage_gate_status
from scripts.check_candidate_stage_gate import main as stage_gate_main
from scripts.promote_candidate_exact_spans import promote_exact_spans
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

    def test_stage_b_readiness_check_requires_explicit_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp)
            fixture = _write_fixture(corpus, name="sg_direct_identifiers_memo_default_001.txt")
            labels = json.loads(labels_path_for(fixture).read_text(encoding="utf-8"))
            labels["doc_id"] = "sg_direct_identifiers_memo_default_001"
            record_human_review(labels, decision="approve", reviewer="counsel@example.com")
            write_labels(labels_path_for(fixture), labels)

            violations = collect_stage_b_readiness_violations(corpus)
            self.assertEqual(len(violations), 1)
            self.assertIn("stage_b_readiness=missing", violations[0])

            labels["_stage_readiness"] = {
                "stage_a": "reviewed",
                "stage_b": "ready",
                "stage_c": "pending",
                "status": "stage_b_ready",
                "reviewer": "project-owner",
            }
            write_labels(labels_path_for(fixture), labels)
            self.assertEqual(collect_stage_b_readiness_violations(corpus), [])

    def test_stage_b_readiness_check_ignores_expanded_stage_b_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp)
            memo = _write_fixture(corpus, name="sg_direct_identifiers_memo_default_001.txt")
            memo_labels = json.loads(labels_path_for(memo).read_text(encoding="utf-8"))
            record_human_review(memo_labels, decision="approve", reviewer="counsel@example.com")
            memo_labels["_stage_readiness"] = {
                "stage_a": "reviewed",
                "stage_b": "ready",
                "stage_c": "pending",
                "status": "stage_b_ready",
                "reviewer": "project-owner",
            }
            write_labels(labels_path_for(memo), memo_labels)

            expanded = _write_fixture(corpus, name="sg_direct_identifiers_privacy_notice_default_001.txt")
            expanded_labels = json.loads(labels_path_for(expanded).read_text(encoding="utf-8"))
            expanded_labels["document_type"] = "memo"
            expanded_labels["doc_id"] = "sg_direct_identifiers_privacy_notice_default_001"
            write_labels(labels_path_for(expanded), expanded_labels)

            self.assertEqual(collect_stage_b_readiness_violations(corpus), [])
            self.assertEqual(collect_review_status_violations(corpus, stage_a_only=True), [])
            self.assertEqual(len(collect_review_status_violations(corpus)), 1)

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

    def test_exact_span_promotion_only_moves_runtime_exact_ideal_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp)
            fixture = corpus / "sg_quasi_identifiers_memo_default_001.txt"
            text = "Dr Jane Tan can be reached at +65 9123 4567 or jane.tan@example.sg."
            exact_text = text.rstrip(".")
            fixture.write_text(text, encoding="utf-8")
            write_labels(
                labels_path_for(fixture),
                {
                    "doc_id": fixture.stem,
                    "document_type": "memo",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "must_detect": [
                        {"category": "PII", "rule": "named_person", "matched_text": "Dr Jane Tan"},
                    ],
                    "ideal_must_detect": [
                        {"category": "PII", "rule": "quasi_identifier_combination", "matched_text": exact_text},
                        {
                            "category": "PII",
                            "rule": "quasi_identifier_combination",
                            "matched_text": "broader non-exact cluster",
                        },
                    ],
                    "must_not_detect": [],
                    "_taxonomy_concept": "quasi_identifiers",
                },
            )

            dry = promote_exact_spans(corpus=corpus, dry_run=True, actor="test")
            self.assertEqual(dry["promoted_count"], 1)
            labels_after_dry = json.loads(labels_path_for(fixture).read_text(encoding="utf-8"))
            self.assertEqual(len(labels_after_dry["must_detect"]), 1)

            result = promote_exact_spans(corpus=corpus, dry_run=False, actor="test")
            self.assertEqual(result["promoted_count"], 1)
            labels = json.loads(labels_path_for(fixture).read_text(encoding="utf-8"))
            promoted = [
                item for item in labels["must_detect"]
                if item["rule"] == "quasi_identifier_combination"
            ]
            self.assertEqual(len(promoted), 1)
            self.assertEqual(promoted[0]["matched_text"], exact_text)
            self.assertEqual(labels["_exact_span_promotion"]["actor"], "test")

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

    def test_stage_gate_reports_evaluated_but_pending_owner_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            corpus = root / "candidates"
            cell = corpus / "sg" / "direct_identifiers"
            cell.mkdir(parents=True)
            documents = []
            for idx in range(1, STAGE_B_DOCS + 1):
                fixture = cell / f"sg_direct_identifiers_memo_default_{idx:03d}.txt"
                fixture.write_text("Send S1234567D before announcement.\n", encoding="utf-8")
                labels = _fixture_labels(review_status="approved" if idx == 1 else "pending")
                labels["doc_id"] = fixture.stem
                labels["source_jurisdiction"] = "SG"
                write_labels(labels_path_for(fixture), labels)
                documents.append({
                    "source_jurisdiction": "SG",
                    "matched": [{"rule": "sg_nric_fin", "matched_text": "S1234567D"}],
                    "missed": [],
                    "unexpected": [],
                    "must_not_detect_violations": [],
                    "ideal_matched": [{"rule": "sg_nric_fin", "matched_text": "S1234567D"}],
                    "ideal_missed": [],
                })
            eval_report = root / "eval.json"
            eval_report.write_text(json.dumps({"documents": documents}), encoding="utf-8")

            status = stage_gate_status(
                corpus=corpus,
                jurisdiction="SG",
                target_stage="stage_b",
                eval_reports=[eval_report],
            )
            self.assertEqual(status["status"], "evaluated_pending_owner_review")
            self.assertTrue(status["clean_eval"])
            self.assertFalse(status["owner_reviewed"])

            rc = _quiet_main(
                stage_gate_main,
                [
                    "--corpus",
                    str(corpus),
                    "--jurisdiction",
                    "SG",
                    "--target-stage",
                    "stage_b",
                    "--eval-report",
                    str(eval_report),
                    "--require-promotion-ready",
                ],
            )
            self.assertEqual(rc, 1)


def collect_review_status_violations_for_payload(labels: dict) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        corpus = Path(tmp)
        fixture = corpus / "payload.txt"
        fixture.write_text("Send Dr Jane Tan S1234567D.\n", encoding="utf-8")
        write_labels(labels_path_for(fixture), labels)
        return collect_review_status_violations(corpus)


if __name__ == "__main__":
    unittest.main()
