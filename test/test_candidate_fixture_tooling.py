import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import autolabel_fixture, generate_legal_fixture
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
        self.assertIn("strict detector-aligned labels", autolabel_fixture.SYSTEM)
        self.assertIn("ideal_must_detect", prompt)
        self.assertIn("uncertain", prompt)

    def test_autolabel_env_helpers_validate_positive_numbers(self):
        with patch.dict("os.environ", {"KAYPOH_AUTOLABEL_AZURE_MAX_COMPLETION_TOKENS": "8000"}):
            self.assertEqual(
                autolabel_fixture._positive_int_env("KAYPOH_AUTOLABEL_AZURE_MAX_COMPLETION_TOKENS", 16000),
                8000,
            )
        with patch.dict("os.environ", {"KAYPOH_AUTOLABEL_AZURE_RETRY_SLEEP_SECONDS": "0.25"}):
            self.assertEqual(
                autolabel_fixture._positive_float_env("KAYPOH_AUTOLABEL_AZURE_RETRY_SLEEP_SECONDS", 2.0),
                0.25,
            )
        with patch.dict("os.environ", {"KAYPOH_AUTOLABEL_AZURE_MAX_ATTEMPTS": "0"}):
            with self.assertRaises(RuntimeError):
                autolabel_fixture._positive_int_env("KAYPOH_AUTOLABEL_AZURE_MAX_ATTEMPTS", 3)

    def test_negative_generation_prompt_does_not_force_dense_positives(self):
        _, prompt = generate_legal_fixture._build_prompt(
            "memo",
            adversarial=False,
            multilingual=False,
            jurisdiction="SG",
            concept="special_category",
            variant="negative",
        )
        self.assertIn("primarily a precision fixture", prompt)
        self.assertIn("at most one or two clearly intentional positive spans", prompt)
        self.assertIn("Do not add a named person", prompt)
        self.assertNotIn("Include at least one fictional named person with an honorific", prompt)

    def test_label_validation_preserves_category_and_uncertain_notes(self):
        body = "Dr Jane Tan S1234567D reviewed Project Atlas before announcement."
        labels = {
            "must_detect": [
                {"category": "PII", "rule": "sg_nric_fin", "matched_text": "S1234567D"},
                {"category": "PII", "rule": "transaction_codename", "matched_text": "Project Atlas"},
                {"rule": "not_a_rule", "matched_text": "Project Atlas"},
            ],
            "ideal_must_detect": [
                {"category": "MNPI", "rule": "transaction_codename", "matched_text": "Project Atlas"},
                {"category": "PII", "rule": "named_person", "matched_text": "Not In Body"},
            ],
            "must_not_detect": [{"matched_text": "Purchaser", "reason": "defined role"}],
            "uncertain": [{"matched_text": "before announcement", "concept": "public status", "reason": "contextual"}],
        }
        cleaned, warnings = autolabel_fixture._validate_labels(labels, body + " Purchaser")
        self.assertEqual(cleaned["must_detect"][0]["category"], "PII")
        self.assertEqual(cleaned["must_detect"][1]["category"], "MNPI")
        self.assertEqual(len(cleaned["must_detect"]), 2)
        self.assertEqual(cleaned["ideal_must_detect"], [
            {"category": "MNPI", "rule": "transaction_codename", "matched_text": "Project Atlas"},
        ])
        self.assertEqual(cleaned["uncertain"][0]["concept"], "public status")
        self.assertTrue(any("invalid rule" in warning for warning in warnings))
        self.assertTrue(any("mismatched category" in warning for warning in warnings))
        self.assertTrue(any("ideal_must_detect" in warning and "not verbatim" in warning for warning in warnings))

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
                        "ideal_must_detect": [
                            {"category": "PII", "rule": "sg_nric_fin", "matched_text": "S1234567D"},
                            {"category": "MNPI", "rule": "nonpublic_marker", "matched_text": "before announcement"},
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
        self.assertEqual(len(report.ideal_matched), 2)
        self.assertEqual(len(report.ideal_missed), 1)
        triage_buckets = {item["bucket"] for item in report.unexpected_triage}
        self.assertIn("ideal_only_statutory_gap", triage_buckets)
        self.assertIn("real_detector_hit_missing_from_strict_labels", triage_buckets)
        self.assertEqual(report.human_review_status, "pending")
        self.assertEqual(summary["candidate_recall"], 0.5)
        self.assertIn("candidate_precision", summary)
        self.assertIn("unexpected_triage", summary)
        self.assertEqual(summary["ideal_candidate_recall"], 0.6667)


if __name__ == "__main__":
    unittest.main()
