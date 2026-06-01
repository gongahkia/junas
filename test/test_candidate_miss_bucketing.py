import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from scripts import (
    bucket_candidate_misses,
    evaluate_candidate_corpus,
    miss_concentration,
    run_layer_attribution_eval,
)


class CandidateEvaluationProfileTests(unittest.TestCase):
    def test_candidate_eval_records_profile_and_label_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp)
            (corpus / "sample.txt").write_text(
                "Contact Ms Jane Tan at jane.tan@example.sg about Project Helios.",
                encoding="utf-8",
            )
            (corpus / "sample.labels.json").write_text(
                json.dumps({
                    "doc_id": "sample",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "document_type": "memo",
                    "_human_review_status": "approved",
                    "_label_source": "unit",
                    "must_detect": [
                        {
                            "category": "PII",
                            "rule": "email_address",
                            "matched_text": "jane.tan@example.sg",
                            "reason": "personal email",
                        }
                    ],
                    "ideal_must_detect": [
                        {
                            "category": "PII",
                            "rule": "quasi_identifier_combination",
                            "matched_text": "Ms Jane Tan at jane.tan@example.sg",
                            "concept": "singling out",
                        }
                    ],
                }),
                encoding="utf-8",
            )
            output = corpus / "report.json"
            with redirect_stdout(StringIO()):
                rc = evaluate_candidate_corpus.main([
                    "--corpus",
                    str(corpus),
                    "--output",
                    str(output),
                    "--profile",
                    "strict",
                ])
            self.assertEqual(rc, 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["review_profile"], "strict")
            self.assertEqual(payload["documents"][0]["matched"][0]["reason"], "personal email")
            self.assertEqual(payload["documents"][0]["ideal_missed"][0]["concept"], "singling out")


class CandidateMissBucketingTests(unittest.TestCase):
    def test_bucket_report_groups_ideal_misses(self):
        report = {
            "corpus": "candidate",
            "review_profile": "strict",
            "documents": [
                {
                    "doc_id": "d1",
                    "path": "test/fixtures/legal-corpus-candidates/sg/example.txt",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "document_type": "memo",
                    "ideal_missed": [
                        {
                            "category": "PII",
                            "rule": "quasi_identifier_combination",
                            "matched_text": "Jane Tan, DOB 1972, Bukit Timah",
                        },
                        {
                            "category": "PII",
                            "rule": "in_aadhaar",
                            "matched_text": "2345 6789 0123",
                        },
                        {
                            "category": "MNPI",
                            "rule": "blackout_period_reference",
                            "matched_text": "during the pre-results blackout",
                        },
                        {
                            "category": "MNPI",
                            "rule": "material_event",
                            "matched_text": "not generally known to the market",
                            "reason": "requires not generally known judgement",
                        },
                    ],
                }
            ],
        }
        payload = bucket_candidate_misses.bucket_report(report)
        buckets = [item["bucket"] for item in payload["misses"]]
        self.assertEqual(buckets, [
            "singling_out_miss",
            "coverage_gap",
            "conjunction_miss",
            "true_inference_miss",
        ])
        self.assertEqual(payload["summary"]["by_bucket"]["coverage_gap"], 1)
        self.assertEqual(payload["summary"]["by_detector_family"]["quasi_identifier"]["singling_out_miss"], 1)

    def test_concentration_report_keeps_examples(self):
        bucketed = {
            "source_review_profile": "strict",
            "misses": [
                {
                    "doc_id": "d1",
                    "path": "a.txt",
                    "source_jurisdiction": "SG",
                    "detector_family": "direct_identifier",
                    "bucket": "coverage_gap",
                    "rule": "email_address",
                    "matched_text": "jane@example.sg",
                    "bucket_reason": "direct_identifier detector did not cover the ideal span",
                },
                {
                    "doc_id": "d2",
                    "path": "b.txt",
                    "source_jurisdiction": "SG",
                    "detector_family": "direct_identifier",
                    "bucket": "coverage_gap",
                    "rule": "phone_number",
                    "matched_text": "+65 9123 4567",
                    "bucket_reason": "direct_identifier detector did not cover the ideal span",
                },
            ],
        }
        payload = miss_concentration.concentration_report(bucketed, examples_per_cell=1)
        self.assertEqual(payload["summary"]["by_detector_family"]["direct_identifier"], 2)
        self.assertEqual(payload["cells"][0]["miss_count"], 2)
        self.assertEqual(len(payload["cells"][0]["examples"]), 1)
        markdown = miss_concentration.render_markdown(payload)
        self.assertIn("# Miss Concentration", markdown)
        self.assertIn("| direct_identifier | SG | coverage_gap | 2 |", markdown)


class LayerAttributionRunnerTests(unittest.TestCase):
    def test_strict_runner_writes_manifest_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            corpus = root / "corpus"
            out = root / "out"
            corpus.mkdir()
            (corpus / "sample.txt").write_text(
                "Email jane.tan@example.sg about Project Helios.",
                encoding="utf-8",
            )
            (corpus / "sample.labels.json").write_text(
                json.dumps({
                    "doc_id": "sample",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                    "document_type": "memo",
                    "_human_review_status": "approved",
                    "_label_source": "unit",
                    "must_detect": [
                        {
                            "category": "PII",
                            "rule": "email_address",
                            "matched_text": "jane.tan@example.sg",
                        }
                    ],
                    "ideal_must_detect": [
                        {
                            "category": "MNPI",
                            "rule": "blackout_period_reference",
                            "matched_text": "Project Helios",
                            "reason": "public-status judgement needed",
                        }
                    ],
                }),
                encoding="utf-8",
            )
            with redirect_stdout(StringIO()):
                rc = run_layer_attribution_eval.main([
                    "--corpus",
                    str(corpus),
                    "--output-dir",
                    str(out),
                    "--run-id",
                    "unit",
                ])
            self.assertEqual(rc, 0)
            manifest = json.loads((out / "unit_manifest.json").read_text(encoding="utf-8"))
            self.assertIn("strict", manifest["profiles"])
            self.assertTrue((out / "unit_strict_candidate_eval.json").exists())
            self.assertTrue((out / "unit_strict_miss_buckets.json").exists())
            self.assertTrue((out / "unit_strict_miss_concentration.json").exists())

    def test_audit_grade_requires_explicit_cost_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                rc = run_layer_attribution_eval.main([
                    "--output-dir",
                    tmp,
                    "--profile",
                    "audit_grade",
                ])
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
