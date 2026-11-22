"""Versioned adapters must qualify legacy measurements without changing them."""

import json
from types import SimpleNamespace as N
from unittest.mock import patch

import pytest

from scripts import evaluate_candidate_corpus as candidate
from scripts import recall_gate
from scripts import run_ai4privacy_eval as ai
from scripts import run_tab_eval as tab
from scripts.span_metrics import internal_annotation_audit


def _tab_doc(split="test", doc_id="d", *, coverage=True):
    return tab.TabDocument(doc_id, split, "abcd efgh", {"a": {"entity_mentions": []}} if coverage else {}, split)


def _gold(start, end, kind="PERSON", split="test", doc_id="d", annotator="a"):
    return tab.GoldSpan(doc_id, split, annotator, start, end, "abcd efgh"[start:end], kind, "DIRECT", "e", f"{start}")


def _pred(start, end, *, category="PII", split="test", doc_id="d"):
    return tab.PredictedSpan(doc_id, start, end, "abcd efgh"[start:end], category, "r", "high", split)


def test_legacy_greedy_order_dependency_is_preserved_but_new_measurement_is_invariant():
    docs = [_tab_doc()]
    g = [_gold(0, 4), _gold(5, 9)]
    p = [_pred(0, 9), _pred(0, 4)]
    assert tab.score_spans(docs, g, p).true_positive == 1
    assert tab.score_spans(docs, g, p[::-1]).true_positive == 2
    a = tab.corrected_tab_measurements(docs, g, p)
    b = tab.corrected_tab_measurements(docs, g[::-1], p[::-1])
    assert a == b
    assert a["by_split"]["test"]["scores"]["overlap"]["matched"] == 2
    assert a["by_split"]["test"]["scores"]["overlap"]["precision_if_exhaustive"] is None


def test_tab_subtype_precision_is_not_invented_without_crosswalk():
    docs = [_tab_doc()]
    g = [_gold(0, 4), _gold(5, 9, "LOCATION")]
    p = [_pred(0, 4), _pred(5, 9)]
    legacy = tab._score_by_key(docs, g, p, key_name="entity_type", match_mode="exact")
    assert legacy["PERSON"]["precision"] == 0.5
    corrected = tab.corrected_tab_measurements(docs, g, p, annotation_coverage="exhaustive")
    result = corrected["by_split"]["test"]["scores"]["exact"]
    assert result["precision_if_exhaustive"] == 1
    assert result["by_entity_type"]["PERSON"]["precision"] is None
    assert result["by_entity_type"]["PERSON"]["labeled_span_recall"] == 1


def test_tab_filters_non_pii_predictions_out_of_binary_target():
    result = tab.corrected_tab_measurements(
        [_tab_doc()], [_gold(0, 4)], [_pred(0, 4), _pred(5, 9, category="MNPI")], annotation_coverage="exhaustive"
    )
    score = result["by_split"]["test"]["scores"]["exact"]
    assert score["predictions"] == 1 and score["precision_if_exhaustive"] == 1


def test_split_and_annotator_observations_remain_separate():
    docs = [_tab_doc(s, "same-id") for s in ("train", "dev", "test")]
    g = [_gold(0, 4, split=s, doc_id="same-id") for s in ("train", "dev", "test")]
    p = [_pred(0, 4, split="test", doc_id="same-id")]
    report = tab.corrected_tab_measurements(docs, g, p)
    assert set(report["by_split"]) == {"train", "dev", "test"}
    assert report["by_split"]["test"]["scores"]["exact"]["matched"] == 1
    assert report["by_split"]["dev"]["scores"]["exact"]["matched"] == 0
    assert report["holdout_status"].startswith("not established")
    assert len(report["cross_split_duplicate_text_hashes"]) == 1


def test_multiple_tab_annotators_are_not_merged_into_consensus():
    doc = _tab_doc()
    doc.annotations["b"] = {"entity_mentions": []}
    report = tab.corrected_tab_measurements([doc], [_gold(0, 4), _gold(0, 4, annotator="b")], [_pred(0, 4)])
    assert report["by_split"]["test"]["scores"]["exact"]["matched"] == 2


@pytest.mark.parametrize("case", ["bad_text", "missing_annotator", "split_mismatch", "duplicate_doc", "bad_prediction"])
def test_unqualified_tab_measurement_is_unavailable(case):
    docs = [_tab_doc()]
    g = [_gold(0, 4)]
    p = [_pred(0, 4)]
    diag = []
    if case == "bad_text":
        g = [tab.GoldSpan("d", "test", "a", 0, 4, "wrong", "PERSON", "DIRECT", "e", "m")]
    if case == "missing_annotator":
        docs = [_tab_doc(coverage=False)]
        g = []
    if case == "split_mismatch":
        docs = [tab.TabDocument("d", "train", "abcd efgh", {"a": {}}, "test")]
    if case == "duplicate_doc":
        docs = docs * 2
    if case == "bad_prediction":
        diag = ["invalid prediction dropped by legacy"]
    assert tab.corrected_tab_measurements(docs, g, p, diagnostics=diag)["status"] == "unavailable"


def test_ai_broad_prediction_legacy_and_corrected_definitions_are_distinct():
    row = ai.Ai4PrivacyRow(
        "d", "abcd efgh", "en", (ai.PrivacyMask("abcd", 0, 4, "SSN"), ai.PrivacyMask("efgh", 5, 9, "PERSON"))
    )
    engine = N(review=lambda **_: N(findings=[N(start_char=0, end_char=9, category="PII", rule="broad")]))
    corrected = {}
    legacy = ai.score_slice(
        [row],
        engine=engine,
        review_profile="strict",
        source_jurisdiction="US",
        match_mode="overlap",
        occurrence_output=corrected,
    )
    assert legacy.recall == 1
    assert corrected["scores"]["overlap"]["labeled_span_recall"] == 0.5
    assert corrected["scores"]["exact"]["matched"] == 0
    assert corrected["scores"]["overlap"]["precision_if_exhaustive"] is None


def test_ai_duplicate_rows_and_invalid_gold_are_unavailable():
    row = ai.Ai4PrivacyRow("d", "abcd efgh", "en", (ai.PrivacyMask("abcd", 0, 4, "SSN"),))
    assert ai.corrected_ai_measurements([(row, []), (row, [])])["status"] == "unavailable"
    malformed = ai.Ai4PrivacyRow("d", "abcd", "en", (ai.PrivacyMask("wrong", 0, 4, "SSN"),))
    assert ai.corrected_ai_measurements([(malformed, [])])["status"] == "unavailable"


def test_legacy_rule_text_and_hard_negative_precision_keep_their_identity(tmp_path):
    path = tmp_path / "d.txt"
    path.write_text("same same")
    labels = {
        "doc_id": "d",
        "must_detect": [{"rule": "r", "matched_text": "same"}] * 2,
        "_strict_runtime_reconciliation": {"source": "detector"},
    }
    path.with_suffix(".labels.json").write_text(json.dumps(labels))
    with patch.object(
        candidate, "_run_engine", return_value=[{"category": "PII", "rule": "r", "matched_text": "same"}]
    ):
        report = candidate._evaluate_one(path)
    assert len(report.matched) == 2
    assert len(report.independent_matched) == 2  # frozen v1 filter, not scientific independence
    assert report.annotation_audit_v1["occurrence_metrics"]["status"] == "unavailable"
    assert report.annotation_audit_v1["sections"]["must_detect"]["independence_status"] == {"not_established": 2}
    with patch.object(
        recall_gate,
        "_run_review",
        return_value=[{"rule": "r", "matched_text": "same"}, {"rule": "r", "matched_text": "extra"}],
    ):
        result = recall_gate._evaluate_doc("same extra", labels)
    assert recall_gate._aggregate_precision([result]) == {"r": 1}


def test_unknown_internal_labels_are_not_exhaustive_ground_truth():
    audit = internal_annotation_audit({"must_detect": [{"rule": "r", "matched_text": "same"}]})
    assert audit["annotation_coverage"] == "unknown"
    assert audit["sections"]["must_detect"]["items_with_offset_fields"] == 0
    assert audit["occurrence_metrics"]["status"] == "unavailable"
    assert audit["document_classification_accuracy"]["status"] == "unavailable"


def test_internal_existing_offsets_are_not_automatically_qualified():
    audit = internal_annotation_audit(
        {"must_detect": [{"rule": "r", "matched_text": "same", "start_char": 0, "end_char": 4}]}
    )
    assert audit["sections"]["must_detect"]["items_with_offset_fields"] == 1
    assert audit["occurrence_metrics"]["status"] == "unavailable"


def test_custom_accuracy_output_routes_external_reports_away_from_historical_paths(tmp_path, monkeypatch):
    from scripts import evaluate_accuracy as runner

    monkeypatch.setattr(
        runner,
        "evaluate_corpus",
        lambda _: {
            "regression_gate": {"passed": True},
            "summary": {"doc_count": 1, "candidate_recall": 1, "candidate_precision": 1, "candidate_f2": 1},
        },
    )
    monkeypatch.setattr(
        runner,
        "external_status",
        lambda: {
            "tab": {"available": True, "runner": "not-executed.py", "output": "reports/current/core_tab_eval.json"}
        },
    )
    calls = []
    monkeypatch.setattr(
        runner.subprocess, "run", lambda args, **_: calls.append(args) or N(returncode=0, stdout="", stderr="")
    )
    target = tmp_path / "fresh.json"
    assert runner.main(["--corpus", str(tmp_path), "--external", "available", "--output", str(target)]) == 0
    assert calls[0][-1] == str(tmp_path / "fresh.tab.json")


def test_corrected_tab_accepts_iterables_without_losing_later_splits():
    docs = [_tab_doc(s, "same-id") for s in ("train", "test")]
    g = [_gold(0, 4, split=s, doc_id="same-id") for s in ("train", "test")]
    p = [_pred(0, 4, split=s, doc_id="same-id") for s in ("train", "test")]
    report = tab.corrected_tab_measurements(iter(docs), iter(g), iter(p))
    assert all(v["scores"]["exact"]["matched"] == 1 for v in report["by_split"].values())


def test_tab_invalid_prediction_omission_disables_corrected_metrics(tmp_path):
    data = [{"doc_id": "d", "text": "abcd efgh", "annotations": {"a": {"entity_mentions": []}}}]
    (tmp_path / "echr_test.json").write_text(json.dumps(data))
    engine = N(review=lambda **_: N(findings=[N(start_char=-1, end_char=4, category="PII")]))
    report = tab.evaluate_tab(tab_dir=tmp_path, splits=["test"], engine_factory=lambda: engine)
    assert report["summary"]["predicted_spans"] == 0
    assert report["occurrence_v1"]["status"] == "unavailable"
    assert "invalid prediction" in report["occurrence_v1"]["reason"]


def test_ai_input_identities_and_overlapping_proxy_slices_are_recorded(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "d",
                "language": "en",
                "source_text": "abcd efgh",
                "privacy_mask": [
                    {"value": "abcd", "start": 0, "end": 4, "label": "SSN"},
                    {"value": "efgh", "start": 5, "end": 9, "label": "VEHICLEVRM"},
                ],
            }
        )
        + "\n"
    )
    report = ai.evaluate_ai4privacy(fixture=path, engine_factory=lambda: N(review=lambda **_: N(findings=[])))
    assert report["cross_slice_duplicate_row_ids"] == ["d"]
    assert len(report["input_identity_v1"]["fixture_sha256"]) == 64
    assert all(x["split"].startswith("unspecified") for x in report["occurrence_v1"].values())


def test_tab_exact_offsets_must_match_source_text_in_new_measurement(tmp_path):
    data = [
        {
            "doc_id": "d",
            "text": "abcd efgh",
            "annotations": {
                "a": {
                    "entity_mentions": [
                        {
                            "start_offset": 0,
                            "end_offset": 4,
                            "span_text": "wrong",
                            "identifier_type": "DIRECT",
                            "entity_type": "PERSON",
                        }
                    ]
                }
            },
        }
    ]
    (tmp_path / "echr_test.json").write_text(json.dumps(data))
    report = tab.evaluate_tab(
        tab_dir=tmp_path, splits=["test"], engine_factory=lambda: N(review=lambda **_: N(findings=[]))
    )
    assert report["warnings"]
    assert report["occurrence_v1"]["status"] == "unavailable"


def test_tab_physical_split_conflict_is_not_relabelled_silently(tmp_path):
    data = [{"doc_id": "d", "dataset_type": "train", "text": "abcd", "annotations": {"a": {"entity_mentions": []}}}]
    (tmp_path / "echr_test.json").write_text(json.dumps(data))
    report = tab.evaluate_tab(
        tab_dir=tmp_path, splits=["test"], engine_factory=lambda: N(review=lambda **_: N(findings=[]))
    )
    assert report["occurrence_v1"]["status"] == "unavailable"
    assert "physical split" in report["occurrence_v1"]["reason"]
