import json
import unittest
from pathlib import Path

from scripts.run_singling_out_pack_eval import DEFAULT_OUTPUT, SCHEMA_VERSION, compact_tab_report

ROOT = Path(__file__).resolve().parent.parent


class SinglingOutPackEvalTests(unittest.TestCase):
    def test_compact_tab_report_keeps_quasi_and_singling_out_scores(self):
        report = {
            "summary": {"documents": 1},
            "by_identifier_type": {"QUASI": {"recall": 0.5}},
            "prediction_rule_counts": {"quasi_identifier_combination": 2},
            "singling_out_validation": {
                "gold_quasi_spans": 3,
                "gold_quasi_docs": 1,
                "gold_quasi_coreference_groups": 1,
                "gold_quasi_coreference_spans": 3,
                "quasi_identifier_combination_predictions": 2,
                "quasi_identifier_combination_docs": 1,
                "quasi_identifier_combination_overlap_score": {
                    "precision": 1.0,
                    "recall": 0.5,
                    "f2": 0.555556,
                },
            },
        }

        compact = compact_tab_report(report)

        self.assertEqual(compact["quasi_identifier_type_score"]["recall"], 0.5)
        self.assertEqual(compact["singling_out"]["quasi_identifier_combination_predictions"], 2)
        self.assertEqual(compact["singling_out"]["quasi_identifier_combination_f2"], 0.555556)

    def test_committed_pack_report_covers_sg_us_uk_and_decision(self):
        payload = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        self.assertEqual(set(payload["packs"]), {"SG", "US", "UK"})
        self.assertEqual(payload["decision"]["status"], "deepen_sg_us_uk_before_widening")
        for pack in ("SG", "US", "UK"):
            with self.subTest(pack=pack):
                self.assertIn("quasi_identifier_combination_recall", payload["packs"][pack]["singling_out"])

    def test_docs_record_thin_pack_widening_decision(self):
        text = (ROOT / "docs" / "singling-out-pack-eval.md").read_text(encoding="utf-8")

        self.assertIn("SG, US, and UK", text)
        self.assertIn("deepen SG/US/UK before widening", text)
        self.assertIn("reports/current/singling_out_pack_eval_20260701.json", text)


if __name__ == "__main__":
    unittest.main()
