import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_corpus_coverage import coverage_report


class CorpusCoverageGateTests(unittest.TestCase):
    def test_coverage_report_classifies_required_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp)
            txt = corpus / "sg_adversarial_ocr_multilingual.txt"
            txt.write_text("OCR broken run: S 1234567 D\n地址: 77 Shenton Way Singapore 068810", encoding="utf-8")
            txt.with_suffix(".labels.json").write_text(
                json.dumps(
                    {
                        "doc_id": "sg_adversarial_ocr_multilingual",
                        "must_detect": [
                            {"rule": "postal_address", "matched_text": "77 Shenton Way Singapore 068810"},
                            {
                                "rule": "health_condition",
                                "matched_text": "Parkinson's disease",
                                "_taxonomy_concept": "special_category",
                            },
                            {
                                "rule": "pharma_trial_mnpi",
                                "matched_text": "top-line results",
                                "_taxonomy_concept": "sector_mnpi",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = coverage_report(
                corpus,
                {
                    "fixtures": 1,
                    "adversarial": 1,
                    "ocr_broken_run": 1,
                    "multilingual": 1,
                    "address": 1,
                    "special_category": 1,
                    "sector_mnpi": 1,
                },
            )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["counts"]["fixtures"], 1)
        self.assertEqual(report["counts"]["sector_mnpi"], 1)

    def test_missing_corpus_reports_blocker(self):
        report = coverage_report(Path("/tmp/kaypoh-missing-corpus-for-test"), {"fixtures": 1})

        self.assertEqual(report["status"], "missing_corpus")
        self.assertEqual(report["missing"], {"fixtures": 1})


if __name__ == "__main__":
    unittest.main()
