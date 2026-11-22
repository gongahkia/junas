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

from scripts.span_metrics import Span, file_sha256, input_identity, occurrence_scores, reproducibility  # noqa: E402

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
    file_split: str = ""


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
    split: str = ""


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
                    file_split=split,
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
    diagnostics: list[str] | None = None,
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
        if diagnostics is not None and getattr(result, "degraded_modes", []):
            diagnostics.append(f"{doc.doc_id}: analysis reported degraded modes")
        for finding in result.findings:
            category = str(getattr(finding, "category", ""))
            if categories is not None and category not in categories:
                continue
            start = int(getattr(finding, "start_char"))
            end = int(getattr(finding, "end_char"))
            if start < 0 or end <= start or end > len(doc.text):
                if diagnostics is not None:
                    diagnostics.append(f"{doc.doc_id}: invalid prediction offsets omitted by legacy scoring")
                continue
            if diagnostics is not None and (
                type(getattr(finding, "start_char")) is not int or type(getattr(finding, "end_char")) is not int
            ):
                diagnostics.append(f"{doc.doc_id}: non-integer prediction offsets")
            predictions.append(
                PredictedSpan(
                    doc_id=doc.doc_id,
                    start=start,
                    end=end,
                    text=str(getattr(finding, "matched_text", doc.text[start:end])),
                    category=category,
                    rule=str(getattr(finding, "rule", "")),
                    severity=str(getattr(finding, "severity", "")),
                    split=getattr(doc, "file_split", "") or doc.split,
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

    # Only annotations from the same document/annotator can match. Preserve the
    # original gold order within each group so greedy one-to-one matching is unchanged.
    unmatched: dict[tuple[str, str], dict[int, GoldSpan]] = defaultdict(dict)
    for index, span in enumerate(gold):
        unmatched[(span.doc_id, span.annotator)][index] = span
    true_positive = 0
    false_positive = 0
    for prediction, annotator in predicted_units:
        candidates = unmatched.get((prediction.doc_id, annotator), {})
        matched_index = None
        for index, candidate in candidates.items():
            if _span_matches(prediction, candidate, match_mode):
                matched_index = index
                break
        if matched_index is None:
            false_positive += 1
        else:
            del candidates[matched_index]
            true_positive += 1
    return _score_from_counts(true_positive, false_positive, len(gold) - true_positive)


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


def corrected_tab_measurements(
    docs, gold, predictions, *, annotation_coverage="unknown", diagnostics=(), categories=None
):
    """Binary masking agreement, separately per physical split and annotator."""
    try:
        docs, gold, predictions = list(docs), list(gold), list(predictions)
        if diagnostics:
            raise ValueError("; ".join(diagnostics))
        if categories is not None and "PII" not in categories:
            raise ValueError("PII predictions were not requested")
        lookup = {}
        for doc in docs:
            split = getattr(doc, "file_split", "") or doc.split
            if split != doc.split:
                raise ValueError(f"{doc.doc_id}: dataset_type differs from physical split file")
            key = (split, doc.doc_id)
            if key in lookup:
                raise ValueError(f"duplicate document identity {key}")
            lookup[key] = doc
            for annotation in doc.annotations.values():
                for mention in annotation.get("entity_mentions", []):
                    if mention.get("identifier_type") in MASKED_IDENTIFIER_TYPES and (
                        type(mention.get("start_offset")) is not int or type(mention.get("end_offset")) is not int
                    ):
                        raise ValueError("gold offsets must be integers")
        by_split = {}
        for split in sorted({key[0] for key in lookup}):
            texts = {
                (split, doc.doc_id, str(a)): doc.text
                for key, doc in lookup.items()
                if key[0] == split
                for a in doc.annotations
            }
            g = []
            original = {}
            for item in gold:
                if item.split != split:
                    continue
                doc = lookup[(split, item.doc_id)]
                if doc.text[item.start : item.end] != item.text:
                    raise ValueError(f"{item.doc_id}: gold span text does not match offsets")
                unit = (split, item.doc_id, item.annotator)
                g.append(Span(unit, item.start, item.end, "PII", "mask"))
                original[(unit, item.start, item.end)] = item
            p = []
            for item in predictions:
                possible = [key[0] for key in lookup if key[1] == item.doc_id]
                assigned = getattr(item, "split", "") or (possible[0] if len(possible) == 1 else "")
                if assigned not in {key[0] for key in lookup if key[1] == item.doc_id}:
                    raise ValueError("ambiguous or unknown prediction split/document")
                if assigned != split or item.category != "PII":
                    continue
                doc = lookup[(split, item.doc_id)]
                if doc.text[item.start : item.end] != item.text:
                    raise ValueError(f"{item.doc_id}: prediction text does not match offsets")
                if not doc.annotations:
                    raise ValueError(f"{item.doc_id}: no annotator coverage is recorded")
                for a in doc.annotations:
                    p.append(Span((split, item.doc_id, str(a)), item.start, item.end, "PII", "mask"))
            if any(not doc.annotations for key, doc in lookup.items() if key[0] == split):
                raise ValueError("documents without annotations are not exhaustive negatives")
            scores = occurrence_scores(g, p, texts=texts, coverage={u: annotation_coverage for u in texts})
            for mode in ("exact", "overlap"):
                if mode not in scores:
                    continue
                matched = {(tuple(m["unit"]), m["start"], m["end"]) for m in scores[mode]["matched_gold"]}
                for key in ("entity_type", "identifier_type"):
                    groups = {}
                    for value in sorted({getattr(item, key) for item in original.values()}):
                        subset = {identity for identity, item in original.items() if getattr(item, key) == value}
                        hits = len(subset & matched)
                        groups[value] = {
                            "gold": len(subset),
                            "matched": hits,
                            "labeled_span_recall": hits / len(subset),
                            "precision": None,
                            "reason": "no approved prediction-to-gold subtype crosswalk; global assignment retained",
                        }
                    scores[mode]["by_" + key] = groups
            by_split[split] = {
                "documents": [
                    {"id": doc.doc_id, "text_sha256": input_identity(doc.text)}
                    for key, doc in sorted(lookup.items())
                    if key[0] == split
                ],
                "scores": scores,
            }
        identities = defaultdict(set)
        for (split, _), doc in lookup.items():
            identities[input_identity(doc.text)].add(split)
        return {
            "schema_version": "junas.tab_occurrence.v1",
            "status": "available" if by_split else "unavailable",
            "target": (
                "binary DIRECT/QUASI masking vs PII predictions; upstream entity types are not classifier rule labels"
            ),
            "annotation_coverage": annotation_coverage,
            "coverage_basis": "caller declaration, not inferred from missing labels",
            "annotator_policy": "predictions replicated per annotator; no consensus gold invented",
            "by_split": by_split,
            "holdout_status": "not established; split names alone do not prove protection from tuning",
            "cross_split_duplicate_text_hashes": sorted(k for k, v in identities.items() if len(v) > 1),
        }
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        return {"schema_version": "junas.tab_occurrence.v1", "status": "unavailable", "reason": str(exc)}


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
    annotation_coverage: str = "unknown",
    prediction_diagnostics: list[str] | None = None,
) -> dict[str, Any]:
    doc_ids = {doc.doc_id for doc in docs}
    return {
        "schema_version": SCHEMA_VERSION,
        "legacy_metric_contract": (
            "summary/subgroups retain historical greedy binary matching; "
            "subgroup precision includes out-of-subgroup predictions"
        ),
        "occurrence_v1": corrected_tab_measurements(
            docs,
            gold_spans,
            predictions,
            annotation_coverage=annotation_coverage,
            diagnostics=prediction_diagnostics or [],
            categories=categories,
        ),
        "reproducibility_v1": reproducibility(Path(__file__)),
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
    annotation_coverage: str = "unknown",
) -> dict[str, Any]:
    if len(set(splits)) != len(splits):
        raise ValueError("duplicate requested TAB splits")
    docs = load_tab_documents(tab_dir, splits)
    if limit is not None:
        if type(limit) is not int or limit < 0:
            raise ValueError("TAB limit must be a nonnegative integer")
        docs = docs[:limit]
    gold_spans, warnings = extract_gold_spans(docs)
    prediction_diagnostics: list[str] = []
    predictions = run_junas_predictions(
        docs,
        engine_factory=engine_factory,
        review_profile=review_profile,
        source_jurisdiction=source_jurisdiction,
        destination_jurisdiction=destination_jurisdiction,
        categories=categories,
        diagnostics=prediction_diagnostics,
    )
    score = score_spans(docs, gold_spans, predictions, match_mode=match_mode)
    report = build_report(
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
        annotation_coverage=annotation_coverage,
        prediction_diagnostics=prediction_diagnostics,
    )
    report["occurrence_v1"]["requested_splits"] = splits
    report["occurrence_v1"]["limit"] = limit
    report["occurrence_v1"]["prediction_origin"] = (
        "bundled_engine" if engine_factory is _default_engine_factory else "caller_supplied_engine; not fingerprinted"
    )
    report["occurrence_v1"]["input_file_sha256"] = {
        split: file_sha256(tab_dir / TAB_SPLIT_FILES[split]) for split in splits
    }
    return report


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
    parser.add_argument(
        "--annotation-coverage",
        choices=("unknown", "partial", "exhaustive"),
        default="unknown",
        help="Declaration for corrected target metrics only; does not establish independence",
    )
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
        annotation_coverage=args.annotation_coverage,
    )
    output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = report["summary"]
    print(
        "Legacy TAB span P/R/F2 "
        f"precision={summary['precision']:.6f} "
        f"recall={summary['recall']:.6f} "
        f"f2={summary['f2']:.6f} "
        f"gold={summary['gold_spans']} predicted={summary['predicted_spans']}"
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
