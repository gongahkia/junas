import json
import tempfile
import unittest
from pathlib import Path

from scripts import autolabel_fixture
from scripts.evaluate_candidate_corpus import _evaluate_one, _summary
from scripts.fixture_taxonomy import JURISDICTIONS, MNPI_RULES, PII_RULES


class CandidateFixtureToolingTests(unittest.TestCase):
    def test_taxonomy_covers_architecture_jurisdictions_and_current_rule_surface(self):
        self.assertEqual(
            set(JURISDICTIONS),
            {"SG", "MY", "ID", "TH", "PH", "VN", "HK", "AU", "JP", "KR", "US", "UK", "EU", "IN", "CN", "AE", "SA"},
        )
        for rule in ("cn_resident_id", "ae_trade_licence", "sg_paynow", "us_driver_license"):
            self.assertIn(rule, PII_RULES)
        for rule in ("dpt_pre_listing_marker", "cyber_incident_pre_disclosure", "blackout_period_reference"):
            self.assertIn(rule, MNPI_RULES)

    def test_autolabel_prompt_uses_independent_jurisdiction_context(self):
        body = "Project Jade memo for Dr Wang Li, passport E12345678, before announcement."
        prompt = autolabel_fixture._build_user_prompt(
            body,
            "memo",
            source_jurisdiction="CN",
            destination_jurisdiction="HK",
            taxonomy_concept="jurisdictional_mnpi",
        )
        self.assertIn("PIPL", prompt)
        self.assertIn("not generally known", prompt)
        self.assertIn("Do not infer what an existing detector can pass", autolabel_fixture.SYSTEM)
        self.assertIn("uncertain", prompt)

    def test_label_validation_preserves_category_and_uncertain_notes(self):
        body = "Dr Jane Tan S1234567D reviewed Project Atlas before announcement."
        labels = {
            "must_detect": [
                {"category": "PII", "rule": "sg_nric_fin", "matched_text": "S1234567D"},
                {"category": "PII", "rule": "transaction_codename", "matched_text": "Project Atlas"},
                {"rule": "not_a_rule", "matched_text": "Project Atlas"},
            ],
            "must_not_detect": [{"matched_text": "Purchaser", "reason": "defined role"}],
            "uncertain": [{"matched_text": "before announcement", "concept": "public status", "reason": "contextual"}],
        }
        cleaned, warnings = autolabel_fixture._validate_labels(labels, body + " Purchaser")
        self.assertEqual(cleaned["must_detect"][0]["category"], "PII")
        self.assertEqual(cleaned["must_detect"][1]["category"], "MNPI")
        self.assertEqual(len(cleaned["must_detect"]), 2)
        self.assertEqual(cleaned["uncertain"][0]["concept"], "public status")
        self.assertTrue(any("invalid rule" in warning for warning in warnings))
        self.assertTrue(any("mismatched category" in warning for warning in warnings))

    def test_candidate_evaluator_reports_matched_and_missed_without_locking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "sg_candidate_001.txt"
            fixture.write_text("Send Dr Jane Tan S1234567D before announcement.\n", encoding="utf-8")
            fixture.with_suffix(".labels.json").write_text(
                json.dumps(
                    {
                        "doc_id": "sg_candidate_001",
                        "document_type": "memo",
                        "source_jurisdiction": "SG",
                        "destination_jurisdiction": "SG",
                        "must_detect": [
                            {"category": "PII", "rule": "sg_nric_fin", "matched_text": "S1234567D"},
                            {"category": "MNPI", "rule": "transaction_codename", "matched_text": "Project Missing"},
                        ],
                        "must_not_detect": [],
                        "uncertain": [{"matched_text": "before announcement", "concept": "public status"}],
                        "_label_source": "openai:test-auto",
                        "_human_review_status": "pending",
                    }
                ),
                encoding="utf-8",
            )
            report = _evaluate_one(fixture)
        summary = _summary([report])
        self.assertEqual(len(report.matched), 1)
        self.assertEqual(len(report.missed), 1)
        self.assertEqual(report.human_review_status, "pending")
        self.assertEqual(summary["candidate_recall"], 0.5)


if __name__ == "__main__":
    unittest.main()
