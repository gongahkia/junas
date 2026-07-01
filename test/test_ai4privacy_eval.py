import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from scripts.run_ai4privacy_eval import (
    SCHEMA_VERSION,
    collect_slice_rows,
    evaluate_ai4privacy,
    iter_ai4privacy_rows,
)


class _FakeEngine:
    def __init__(self, findings_by_text):
        self.findings_by_text = findings_by_text

    def review(self, **kwargs):
        return SimpleNamespace(findings=list(self.findings_by_text.get(kwargs["text"], [])))


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


class Ai4PrivacyEvalTests(unittest.TestCase):
    def test_collect_slice_rows_uses_documented_proxy_labels(self):
        rows = [
            SimpleNamespace(language="en", masks=[SimpleNamespace(label="SSN")]),
            SimpleNamespace(language="en", masks=[SimpleNamespace(label="VEHICLEVRM")]),
            SimpleNamespace(language="fr", masks=[SimpleNamespace(label="SSN")]),
        ]
        from scripts.run_ai4privacy_eval import SLICE_DEFINITIONS

        selected = collect_slice_rows(rows, SLICE_DEFINITIONS.values())
        self.assertEqual(len(selected["en-US"]), 1)
        self.assertEqual(len(selected["en-GB"]), 1)

    def test_iter_rows_validates_offsets(self):
        with TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "english.jsonl"
            _write_jsonl(
                fixture,
                [
                    {
                        "id": 1,
                        "language": "en",
                        "source_text": "SSN 123-45-6789",
                        "privacy_mask": [{"value": "123-45-6789", "start": 4, "end": 15, "label": "SSN"}],
                    }
                ],
            )
            rows = list(iter_ai4privacy_rows(fixture))
        self.assertEqual(rows[0].row_id, "1")
        self.assertEqual(rows[0].masks[0].label, "SSN")

    def test_evaluate_ai4privacy_reports_recall_and_independence_tier(self):
        with TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "english.jsonl"
            us_text = "SSN 123-45-6789"
            gb_text = "Plate AB12 CDE"
            _write_jsonl(
                fixture,
                [
                    {
                        "id": 1,
                        "language": "en",
                        "source_text": us_text,
                        "privacy_mask": [{"value": "123-45-6789", "start": 4, "end": 15, "label": "SSN"}],
                    },
                    {
                        "id": 2,
                        "language": "en",
                        "source_text": gb_text,
                        "privacy_mask": [{"value": "AB12 CDE", "start": 6, "end": 14, "label": "VEHICLEVRM"}],
                    },
                ],
            )
            engine = _FakeEngine(
                {
                    us_text: [
                        SimpleNamespace(category="PII", rule="us_ssn", start_char=4, end_char=15),
                    ],
                    gb_text: [],
                }
            )
            report = evaluate_ai4privacy(fixture=fixture, engine_factory=lambda: engine)
        self.assertEqual(report["schema_version"], SCHEMA_VERSION)
        self.assertEqual(report["source"]["independence_tier"], "semi-independent")
        self.assertFalse(report["source"]["locale_field_available"])
        self.assertEqual(report["slice_results"]["en-US"]["recall"], 1.0)
        self.assertEqual(report["slice_results"]["en-GB"]["recall"], 0.0)
        self.assertEqual(report["slice_results"]["en-US"]["slice_method"], "label_proxy")


if __name__ == "__main__":
    unittest.main()
