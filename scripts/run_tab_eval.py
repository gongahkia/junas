#!/usr/bin/env python3
"""Run Junas against the independent Text Anonymization Benchmark fixture."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

DEFAULT_TAB_DIR = REPO_ROOT / "test" / "fixtures" / "external" / "text-anonymization-benchmark"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "tab-eval" / "tab_eval.json"
TAB_REPO_URL = "https://github.com/NorskRegnesentral/text-anonymization-benchmark"
TAB_SPLIT_FILES = {
    "train": "echr_train.json",
    "dev": "echr_dev.json",
    "test": "echr_test.json",
}
MASKED_IDENTIFIER_TYPES = {"DIRECT", "QUASI"}
SCHEMA_VERSION = "junas.tab_eval.v2"


@dataclass(frozen=True)
class TabDocument:
    doc_id: str
    split: str
    text: str
    annotations: dict[str, Any]


@dataclass(frozen=True)
class GoldSpan:
    doc_id: str
    split: str
    annotator: str
    start: int
    end: int
    text: str
    entity_type: str
    identifier_type: str
    entity_id: str
    entity_mention_id: str


@dataclass(frozen=True)
class PredictedSpan:
    doc_id: str
    start: int
    end: int
    text: str
    category: str
    rule: str
    severity: str


@dataclass(frozen=True)
class Score:
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f2: float


def _round_metric(value: float) -> float:
    return round(value, 6)


def _f_beta(precision: float, recall: float, *, beta: float = 2.0) -> float:
    if precision == 0.0 and recall == 0.0:
        return 0.0
    beta_squared = beta * beta
    return (1 + beta_squared) * precision * recall / ((beta_squared * precision) + recall)


def _score_from_counts(true_positive: int, false_positive: int, false_negative: int) -> Score:
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = true_positive / precision_denominator if precision_denominator else 0.0
    recall = true_positive / recall_denominator if recall_denominator else 0.0
    return Score(
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        precision=_round_metric(precision),
        recall=_round_metric(recall),
        f2=_round_metric(_f_beta(precision, recall)),
    )


def _span_matches(predicted: PredictedSpan, gold: GoldSpan, match_mode: str) -> bool:
    if predicted.doc_id != gold.doc_id:
        return False
    if match_mode == "exact":
        return predicted.start == gold.start and predicted.end == gold.end
    if match_mode == "overlap":
        return predicted.start < gold.end and gold.start < predicted.end
    raise ValueError(f"unsupported match mode: {match_mode}")


def load_tab_documents(tab_dir: Path, splits: Iterable[str]) -> list[TabDocument]:
    docs: list[TabDocument] = []
    for split in splits:
        if split not in TAB_SPLIT_FILES:
            raise ValueError(f"unsupported TAB split: {split}")
        path = tab_dir / TAB_SPLIT_FILES[split]
        if not path.is_file():
            raise FileNotFoundError(f"missing TAB split file: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"TAB split is not a JSON list: {path}")
        for raw_doc in payload:
            doc_id = str(raw_doc.get("doc_id") or "")
            text = str(raw_doc.get("text") or "")
            annotations = raw_doc.get("annotations") or {}
            if not doc_id or not text or not isinstance(annotations, dict):
                raise ValueError(f"invalid TAB document in {path}")
            docs.append(
                TabDocument(
                    doc_id=doc_id,
                    split=str(raw_doc.get("dataset_type") or split),
                    text=text,
                    annotations=annotations,
                )
            )
    return docs


def extract_gold_spans(docs: Iterable[TabDocument]) -> tuple[list[GoldSpan], list[str]]:
    spans: list[GoldSpan] = []
    warnings: list[str] = []
    for doc in docs:
        for annotator, annotation_payload in doc.annotations.items():
            mentions = annotation_payload.get("entity_mentions") if isinstance(annotation_payload, dict) else None
            if mentions is None:
                raise ValueError(f"{doc.doc_id}: annotation {annotator} missing entity_mentions")
            for mention in mentions:
                identifier_type = str(mention.get("identifier_type") or "")
                if identifier_type not in MASKED_IDENTIFIER_TYPES:
                    continue
                start = int(mention["start_offset"])
                end = int(mention["end_offset"])
                text = str(mention.get("span_text") or doc.text[start:end])
                if doc.text[start:end] != text:
                    warnings.append(
                        f"{doc.doc_id}:{annotator}:{mention.get('entity_mention_id', '')} span_text offset mismatch"
                    )
                spans.append(
                    GoldSpan(
                        doc_id=doc.doc_id,
                        split=doc.split,
                        annotator=str(annotator),
                        start=start,
                        end=end,
                        text=text,
                        entity_type=str(mention.get("entity_type") or ""),
                        identifier_type=identifier_type,
                        entity_id=str(mention.get("entity_id") or ""),
                        entity_mention_id=str(mention.get("entity_mention_id") or ""),
                    )
                )
    return spans, warnings


def _default_engine_factory() -> Any:
    from junas.review.engine import PreSendReviewEngine

    return PreSendReviewEngine()


def run_junas_predictions(
    docs: Iterable[TabDocument],
    *,
    engine_factory: Callable[[], Any] = _default_engine_factory,
    review_profile: str = "strict",
    source_jurisdiction: str = "EU",
    destination_jurisdiction: str = "EU",
    categories: set[str] | None = None,
) -> list[PredictedSpan]:
    engine = engine_factory()
    predictions: list[PredictedSpan] = []
    for doc in docs:
        result = engine.review(
            text=doc.text,
            source_jurisdiction=source_jurisdiction,
            destination_jurisdiction=destination_jurisdiction,
            entity_id=None,
            include_suggestions=False,
            document_type="court_case",
            review_profile=review_profile,
        )
        for finding in result.findings:
            category = str(getattr(finding, "category", ""))
            if categories is not None and category not in categories:
                continue
            start = int(getattr(finding, "start_char"))
            end = int(getattr(finding, "end_char"))
            if start < 0 or end <= start or end > len(doc.text):
                continue
            predictions.append(
                PredictedSpan(
                    doc_id=doc.doc_id,
                    start=start,
                    end=end,
                    text=str(getattr(finding, "matched_text", doc.text[start:end])),
                    category=category,
                    rule=str(getattr(finding, "rule", "")),
                    severity=str(getattr(finding, "severity", "")),
                )
            )
    return predictions


def _annotators_by_doc(docs: Iterable[TabDocument]) -> dict[str, set[str]]:
    annotators: dict[str, set[str]] = {}
    for doc in docs:
        annotators[doc.doc_id] = {str(item) for item in doc.annotations}
    return annotators


def score_spans(
    docs: Iterable[TabDocument],
    gold_spans: Iterable[GoldSpan],
    predictions: Iterable[PredictedSpan],
    *,
    match_mode: str = "overlap",
) -> Score:
    gold = list(gold_spans)
    predicted_units: list[tuple[PredictedSpan, str]] = []
    annotators = _annotators_by_doc(docs)
    for prediction in predictions:
        doc_annotators = annotators.get(prediction.doc_id) or {""}
        for annotator in doc_annotators:
            predicted_units.append((prediction, annotator))

    unmatched = set(range(len(gold)))
    true_positive = 0
    false_positive = 0
    for prediction, annotator in predicted_units:
        matched_index = None
        for index in sorted(unmatched):
            candidate = gold[index]
            if candidate.annotator == annotator and _span_matches(prediction, candidate, match_mode):
                matched_index = index
                break
        if matched_index is None:
            false_positive += 1
        else:
            unmatched.remove(matched_index)
            true_positive += 1
    return _score_from_counts(true_positive, false_positive, len(unmatched))


def _score_by_key(
    docs: Iterable[TabDocument],
    gold_spans: Iterable[GoldSpan],
    predictions: Iterable[PredictedSpan],
    *,
    key_name: str,
    match_mode: str,
) -> dict[str, dict[str, float | int]]:
    docs_list = list(docs)
    gold_by_key: dict[str, list[GoldSpan]] = defaultdict(list)
    for gold in gold_spans:
        gold_by_key[str(getattr(gold, key_name))].append(gold)
    output: dict[str, dict[str, float | int]] = {}
    for key, spans in sorted(gold_by_key.items()):
        score = score_spans(docs_list, spans, predictions, match_mode=match_mode)
        output[key] = asdict(score)
    return output


def _singling_out_validation(
    docs: Iterable[TabDocument],
    gold_spans: Iterable[GoldSpan],
    predictions: Iterable[PredictedSpan],
    *,
    match_mode: str,
) -> dict[str, Any]:
    docs_list = list(docs)
    gold = list(gold_spans)
    predicted = list(predictions)
    quasi_gold = [span for span in gold if span.identifier_type == "QUASI"]
    qic_predictions = [span for span in predicted if span.rule == "quasi_identifier_combination"]
    coref: dict[tuple[str, str, str], list[GoldSpan]] = defaultdict(list)
    for span in quasi_gold:
        if span.entity_id:
            coref[(span.doc_id, span.annotator, span.entity_id)].append(span)
    coref_groups = [spans for spans in coref.values() if len(spans) > 1]
    qic_score = score_spans(docs_list, quasi_gold, qic_predictions, match_mode=match_mode)
    return {
        "external_gold_source": "TAB QUASI annotations and entity_id co-reference groups",
        "gold_quasi_spans": len(quasi_gold),
        "gold_quasi_docs": len({span.doc_id for span in quasi_gold}),
        "gold_quasi_coreference_groups": len(coref_groups),
        "gold_quasi_coreference_spans": sum(len(spans) for spans in coref_groups),
        "quasi_identifier_combination_predictions": len(qic_predictions),
        "quasi_identifier_combination_docs": len({span.doc_id for span in qic_predictions}),
        "quasi_identifier_combination_overlap_score": asdict(qic_score),
        "validation_note": (
            "Uses external TAB quasi-identifier/coreference annotations; no Junas-authored "
            "singling-out labels are used."
        ),
    }


def _git_commit(path: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def build_report(
    *,
    tab_dir: Path,
    docs: list[TabDocument],
    gold_spans: list[GoldSpan],
    predictions: list[PredictedSpan],
    score: Score,
    warnings: list[str],
    splits: list[str],
    review_profile: str,
    match_mode: str,
    categories: set[str] | None,
    source_jurisdiction: str,
    destination_jurisdiction: str,
) -> dict[str, Any]:
    doc_ids = {doc.doc_id for doc in docs}
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "name": "Text Anonymization Benchmark",
            "repo": TAB_REPO_URL,
            "fixture_path": str(tab_dir.relative_to(REPO_ROOT) if tab_dir.is_relative_to(REPO_ROOT) else tab_dir),
            "fixture_commit": _git_commit(tab_dir),
            "splits": splits,
            "document_count": len(doc_ids),
            "gold_label_source": "TAB annotations only; no Junas-authored labels",
            "masked_identifier_types": sorted(MASKED_IDENTIFIER_TYPES),
        },
        "evaluation": {
            "separate_from_candidate_corpus": True,
            "never_updates_promotion_lock": True,
            "match_mode": match_mode,
            "multi_annotator_policy": "predictions are expanded per TAB annotator before span-level scoring",
            "review_profile": review_profile,
            "source_jurisdiction": source_jurisdiction,
            "destination_jurisdiction": destination_jurisdiction,
            "finding_categories": sorted(categories) if categories is not None else ["ALL"],
            "beta": 2,
        },
        "summary": {
            "documents": len(doc_ids),
            "gold_spans": len(gold_spans),
            "predicted_spans": len(predictions),
            **asdict(score),
        },
        "by_identifier_type": _score_by_key(
            docs,
            gold_spans,
            predictions,
            key_name="identifier_type",
            match_mode=match_mode,
        ),
        "by_entity_type": _score_by_key(
            docs,
            gold_spans,
            predictions,
            key_name="entity_type",
            match_mode=match_mode,
        ),
        "prediction_rule_counts": dict(sorted(Counter(prediction.rule for prediction in predictions).items())),
        "singling_out_validation": _singling_out_validation(
            docs,
            gold_spans,
            predictions,
            match_mode=match_mode,
        ),
        "warnings": warnings,
    }


def evaluate_tab(
    *,
    tab_dir: Path,
    splits: list[str],
    engine_factory: Callable[[], Any] = _default_engine_factory,
    review_profile: str = "strict",
    match_mode: str = "overlap",
    categories: set[str] | None = {"PII"},
    source_jurisdiction: str = "EU",
    destination_jurisdiction: str = "EU",
    limit: int | None = None,
) -> dict[str, Any]:
    docs = load_tab_documents(tab_dir, splits)
    if limit is not None:
        docs = docs[:limit]
    gold_spans, warnings = extract_gold_spans(docs)
    predictions = run_junas_predictions(
        docs,
        engine_factory=engine_factory,
        review_profile=review_profile,
        source_jurisdiction=source_jurisdiction,
        destination_jurisdiction=destination_jurisdiction,
        categories=categories,
    )
    score = score_spans(docs, gold_spans, predictions, match_mode=match_mode)
    return build_report(
        tab_dir=tab_dir,
        docs=docs,
        gold_spans=gold_spans,
        predictions=predictions,
        score=score,
        warnings=warnings,
        splits=splits,
        review_profile=review_profile,
        match_mode=match_mode,
        categories=categories,
        source_jurisdiction=source_jurisdiction,
        destination_jurisdiction=destination_jurisdiction,
    )


def _parse_categories(values: list[str]) -> set[str] | None:
    categories = {value.strip() for value in values if value.strip()}
    if "ALL" in categories:
        return None
    return categories


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate Junas PII span detection on TAB")
    parser.add_argument("--tab-dir", type=Path, default=DEFAULT_TAB_DIR)
    parser.add_argument("--splits", nargs="+", choices=tuple(TAB_SPLIT_FILES), default=tuple(TAB_SPLIT_FILES))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--profile", default="strict", choices=("strict", "audit_grade"))
    parser.add_argument("--match-mode", default="overlap", choices=("exact", "overlap"))
    parser.add_argument("--source-jurisdiction", default="EU")
    parser.add_argument("--destination-jurisdiction", default="EU")
    parser.add_argument("--categories", nargs="+", default=["PII"], help="Finding categories to score; use ALL for all")
    parser.add_argument("--limit", type=int, help="Evaluate only the first N TAB docs")
    args = parser.parse_args(argv)

    tab_dir = args.tab_dir if args.tab_dir.is_absolute() else REPO_ROOT / args.tab_dir
    if not tab_dir.is_dir():
        print(
            f"missing TAB fixture at {tab_dir}; run scripts/fetch_tab_fixture.sh first",
            file=sys.stderr,
        )
        return 2
    report = evaluate_tab(
        tab_dir=tab_dir,
        splits=list(args.splits),
        review_profile=args.profile,
        match_mode=args.match_mode,
        categories=_parse_categories(args.categories),
        source_jurisdiction=args.source_jurisdiction,
        destination_jurisdiction=args.destination_jurisdiction,
        limit=args.limit,
    )
    output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = report["summary"]
    print(
        "TAB span P/R/F2 "
        f"precision={summary['precision']:.6f} "
        f"recall={summary['recall']:.6f} "
        f"f2={summary['f2']:.6f} "
        f"gold={summary['gold_spans']} predicted={summary['predicted_spans']}"
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
