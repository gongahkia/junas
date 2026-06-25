import json
import tempfile
import unittest
from pathlib import Path

from training.distillation import eval_against_corpus
from training.distillation.promotion_gate import validate_manifest

ROOT = Path(__file__).resolve().parent.parent


def _model_card_text() -> str:
    return "\n".join(
        [
            "# Card",
            "## Promotion Status",
            "## Intended Use",
            "## Training Data",
            "## Evaluation",
            "## Privacy",
            "## Invariants",
        ]
    )


def _privacy_eval(status: str = "pass", *, raw_text_remote_allowed: bool = False) -> dict:
    return {
        "schema_version": "junas.llm_privacy_eval.v1",
        "evaluation_status": status,
        "input_mode": "structured_tokens",
        "raw_text_remote_allowed": raw_text_remote_allowed,
        "checks": [
            {"name": "structured_tokens_default", "status": "pass"},
            {"name": "remote_raw_text_blocked", "status": "pass"},
            {"name": "tenant_consent_required", "status": "pass"},
            {"name": "privacy_ledger_recorded", "status": "pass"},
            {"name": "pdpc_genai_personal_data_review", "status": "pass"},
        ],
    }


def _eval_report() -> dict:
    return {
        "student_provider": "local_distilled",
        "overall": {
            "total": 2,
            "agreements": 2,
            "agreement_rate": 1.0,
            "invariant_violations": 0,
        },
    }


class LLMGovernanceTests(unittest.TestCase):
    def test_default_manifest_records_no_promoted_adapter(self):
        result = validate_manifest(ROOT / "training" / "distillation" / "promotion_manifest.json")

        self.assertEqual(result["status"], "not_promoted")
        self.assertFalse(result["promoted"])
        self.assertEqual(result["failures"], [])

    def test_promoted_manifest_requires_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "promotion.json"
            manifest.write_text(
                json.dumps({
                    "schema_version": "junas.distillation_promotion.v1",
                    "promoted": True,
                    "adapter_path": "missing-adapter",
                    "model_card_path": "missing-card.md",
                    "privacy_eval_path": "missing-privacy.json",
                    "eval_report_path": "missing-report.json",
                    "thresholds": {"min_agreement": 0.9, "max_invariant_violations": 0},
                }),
                encoding="utf-8",
            )

            result = validate_manifest(manifest)

        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("adapter_path missing" in item for item in result["failures"]))
        self.assertTrue(any("model_card_path missing" in item for item in result["failures"]))

    def test_promoted_manifest_passes_with_required_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "adapter").mkdir()
            (root / "MODEL_CARD.md").write_text(_model_card_text(), encoding="utf-8")
            (root / "privacy.json").write_text(json.dumps(_privacy_eval()), encoding="utf-8")
            (root / "eval.json").write_text(json.dumps(_eval_report()), encoding="utf-8")
            manifest = root / "promotion.json"
            manifest.write_text(
                json.dumps({
                    "schema_version": "junas.distillation_promotion.v1",
                    "promoted": True,
                    "adapter_path": "adapter",
                    "model_card_path": "MODEL_CARD.md",
                    "privacy_eval_path": "privacy.json",
                    "eval_report_path": "eval.json",
                    "thresholds": {"min_agreement": 0.9, "max_invariant_violations": 0},
                }),
                encoding="utf-8",
            )

            result = validate_manifest(manifest)

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["failures"], [])

    def test_privacy_eval_blocks_remote_raw_text_for_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "adapter").mkdir()
            (root / "MODEL_CARD.md").write_text(_model_card_text(), encoding="utf-8")
            (root / "privacy.json").write_text(
                json.dumps(_privacy_eval(raw_text_remote_allowed=True)),
                encoding="utf-8",
            )
            (root / "eval.json").write_text(json.dumps(_eval_report()), encoding="utf-8")
            manifest = root / "promotion.json"
            manifest.write_text(
                json.dumps({
                    "schema_version": "junas.distillation_promotion.v1",
                    "promoted": True,
                    "adapter_path": "adapter",
                    "model_card_path": "MODEL_CARD.md",
                    "privacy_eval_path": "privacy.json",
                    "eval_report_path": "eval.json",
                    "thresholds": {"min_agreement": 0.9, "max_invariant_violations": 0},
                }),
                encoding="utf-8",
            )

            result = validate_manifest(manifest)

        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("remote raw text" in item for item in result["failures"]))

    def test_promoted_manifest_requires_pdpc_genai_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            privacy = _privacy_eval()
            privacy["checks"] = [
                item for item in privacy["checks"]
                if item["name"] != "pdpc_genai_personal_data_review"
            ]
            (root / "adapter").mkdir()
            (root / "MODEL_CARD.md").write_text(_model_card_text(), encoding="utf-8")
            (root / "privacy.json").write_text(json.dumps(privacy), encoding="utf-8")
            (root / "eval.json").write_text(json.dumps(_eval_report()), encoding="utf-8")
            manifest = root / "promotion.json"
            manifest.write_text(
                json.dumps({
                    "schema_version": "junas.distillation_promotion.v1",
                    "promoted": True,
                    "adapter_path": "adapter",
                    "model_card_path": "MODEL_CARD.md",
                    "privacy_eval_path": "privacy.json",
                    "eval_report_path": "eval.json",
                    "thresholds": {"min_agreement": 0.9, "max_invariant_violations": 0},
                }),
                encoding="utf-8",
            )

            result = validate_manifest(manifest)

        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("pdpc_genai_personal_data_review" in item for item in result["failures"]))

    def test_eval_against_corpus_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            corpus = root / "corpus"
            corpus.mkdir()
            (corpus / "sample.txt").write_text("Routine note with no sensitive data.", encoding="utf-8")
            report = root / "eval.json"

            code = eval_against_corpus.main([
                "--corpus", str(corpus),
                "--student-provider", "mock",
                "--output-report", str(report),
            ])

            payload = json.loads(report.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(payload["student_provider"], "mock")
        self.assertEqual(payload["overall"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
