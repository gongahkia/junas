import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from scripts.run_tab_eval import (
    SCHEMA_VERSION,
    evaluate_tab,
    extract_gold_spans,
    load_tab_documents,
    score_spans,
)


class _FakeEngine:
    def __init__(self, findings):
        self.findings = findings

    def review(self, **kwargs):
        return SimpleNamespace(findings=list(self.findings))


def _write_tab_split(root: Path, split: str, docs: list[dict]) -> None:
    (root / f"echr_{split}.json").write_text(json.dumps(docs), encoding="utf-8")


class TabEvalTests(unittest.TestCase):
    def test_gold_spans_use_only_tab_direct_and_quasi_labels(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = "Alice met Bob."
            _write_tab_split(
                root,
                "test",
                [
                    {
                        "doc_id": "doc-1",
                        "dataset_type": "test",
                        "text": text,
                        "annotations": {
                            "ann-1": {
                                "entity_mentions": [
                                    {
                                        "entity_type": "PERSON",
                                        "entity_mention_id": "m1",
                                        "start_offset": 0,
                                        "end_offset": 5,
                                        "span_text": "Alice",
                                        "identifier_type": "DIRECT",
                                    },
                                    {
                                        "entity_type": "PERSON",
                                        "entity_mention_id": "m2",
                                        "start_offset": 10,
                                        "end_offset": 13,
                                        "span_text": "Bob",
                                        "identifier_type": "NO_MASK",
                                    },
                                ]
                            }
                        },
                    }
                ],
            )
            docs = load_tab_documents(root, ["test"])
            spans, warnings = extract_gold_spans(docs)
        self.assertEqual(warnings, [])
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].text, "Alice")
        self.assertEqual(spans[0].identifier_type, "DIRECT")

    def test_score_spans_micro_averages_by_annotator(self):
        text = "Alice met Bob."
        docs = [
            SimpleNamespace(
                doc_id="doc-1",
                split="test",
                text=text,
                annotations={"ann-1": {}, "ann-2": {}},
            )
        ]
        gold = [
            SimpleNamespace(doc_id="doc-1", annotator="ann-1", start=0, end=5),
            SimpleNamespace(doc_id="doc-1", annotator="ann-2", start=0, end=5),
            SimpleNamespace(doc_id="doc-1", annotator="ann-2", start=10, end=13),
        ]
        predictions = [
            SimpleNamespace(doc_id="doc-1", start=0, end=5),
            SimpleNamespace(doc_id="doc-1", start=6, end=9),
        ]
        score = score_spans(docs, gold, predictions, match_mode="exact")
        self.assertEqual(score.true_positive, 2)
        self.assertEqual(score.false_positive, 2)
        self.assertEqual(score.false_negative, 1)
        self.assertEqual(score.precision, 0.5)
        self.assertEqual(score.recall, 0.666667)
        self.assertEqual(score.f2, 0.625)

    def test_evaluate_tab_reports_boundary_and_f2_without_candidate_lock(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = "Contact jane@example.com."
            start = text.index("jane@example.com")
            end = start + len("jane@example.com")
            _write_tab_split(
                root,
                "test",
                [
                    {
                        "doc_id": "doc-1",
                        "dataset_type": "test",
                        "text": text,
                        "annotations": {
                            "ann-1": {
                                "entity_mentions": [
                                    {
                                        "entity_type": "EMAIL",
                                        "entity_mention_id": "m1",
                                        "start_offset": start,
                                        "end_offset": end,
                                        "span_text": "jane@example.com",
                                        "identifier_type": "DIRECT",
                                    }
                                ]
                            }
                        },
                    }
                ],
            )
            finding = SimpleNamespace(
                category="PII",
                rule="email_address",
                severity="medium",
                matched_text="jane@example.com",
                start_char=start,
                end_char=end,
            )
            report = evaluate_tab(
                tab_dir=root,
                splits=["test"],
                engine_factory=lambda: _FakeEngine([finding]),
                match_mode="exact",
            )
        self.assertEqual(report["schema_version"], SCHEMA_VERSION)
        self.assertEqual(report["source"]["gold_label_source"], "TAB annotations only; no Junas-authored labels")
        self.assertTrue(report["evaluation"]["separate_from_candidate_corpus"])
        self.assertTrue(report["evaluation"]["never_updates_promotion_lock"])
        self.assertEqual(report["summary"]["precision"], 1.0)
        self.assertEqual(report["summary"]["recall"], 1.0)
        self.assertEqual(report["summary"]["f2"], 1.0)


if __name__ == "__main__":
    unittest.main()
