#!/usr/bin/env python3
"""Evaluate Junas recall on ai4privacy pii-masking-200k English slices."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
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

DEFAULT_FIXTURE = REPO_ROOT / "test" / "fixtures" / "external" / "ai4privacy-pii-masking-200k" / "english_pii_43k.jsonl"
DEFAULT_MANIFEST = DEFAULT_FIXTURE.parent / "fixture_manifest.json"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "current" / "ai4privacy_pii_masking_200k_en_us_en_gb_eval.json"
DATASET_ID = "ai4privacy/pii-masking-200k"
DATASET_URL = "https://huggingface.co/datasets/ai4privacy/pii-masking-200k"
SCHEMA_VERSION = "junas.ai4privacy_eval.v1"


@dataclass(frozen=True)
class SliceDefinition:
    name: str
    source_jurisdiction: str
    proxy_labels: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class PrivacyMask:
    value: str
    start: int
    end: int
    label: str
    offsets_valid: bool = True


@dataclass(frozen=True)
class Ai4PrivacyRow:
    row_id: str
    source_text: str
    language: str
    masks: tuple[PrivacyMask, ...]


@dataclass(frozen=True)
class PredictedSpan:
    start: int
    end: int
    category: str
    rule: str


@dataclass(frozen=True)
class SliceScore:
    documents: int
    gold_spans: int
    matched_spans: int
    recall: float
    predicted_spans: int
    matched_by_label: dict[str, int]
    gold_by_label: dict[str, int]


SLICE_DEFINITIONS = {
    "en-US": SliceDefinition(
        name="en-US",
        source_jurisdiction="US",
        proxy_labels=("SSN",),
        rationale=(
            "The 200k release exposes language=en but no locale field; this slice uses rows containing "
            "the US-specific SSN label as an English-US proxy."
        ),
    ),
    "en-GB": SliceDefinition(
        name="en-GB",
        source_jurisdiction="UK",
        proxy_labels=("VEHICLEVRM",),
        rationale=(
            "The 200k release exposes language=en but no locale field; this slice uses rows containing "
            "the UK vehicle registration mark label as an English-GB proxy."
        ),
    ),
}


def _round_metric(value: float) -> float:
    return round(value, 6)


def _default_engine_factory() -> Any:
    from junas.review.engine import PreSendReviewEngine

    return PreSendReviewEngine()


def _parse_masks(raw_masks: Any) -> tuple[PrivacyMask, ...]:
    if isinstance(raw_masks, str):
        raw_masks = json.loads(raw_masks)
    if not isinstance(raw_masks, list):
        raise ValueError("privacy_mask must be a list")
    masks: list[PrivacyMask] = []
    for item in raw_masks:
        if not isinstance(item, dict):
            raise ValueError("privacy_mask entry must be an object")
        masks.append(
            PrivacyMask(
                value=str(item.get("value") or ""),
                start=int(item["start"]),
                end=int(item["end"]),
                label=str(item.get("label") or ""),
                offsets_valid=type(item.get("start")) is int and type(item.get("end")) is int,
            )
        )
    return tuple(masks)


def iter_ai4privacy_rows(path: Path) -> Iterable[Ai4PrivacyRow]:
    with path.open("r", encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            text = str(payload.get("source_text") or "")
            if not text:
                raise ValueError(f"{path}:{line_number}: missing source_text")
            row_id = str(payload.get("id") if payload.get("id") is not None else line_number)
            masks = _parse_masks(payload.get("privacy_mask"))
            for mask in masks:
                if text[mask.start : mask.end] != mask.value:
                    raise ValueError(f"{path}:{line_number}: mask offset mismatch for {mask.label}")
            yield Ai4PrivacyRow(
                row_id=row_id,
                source_text=text,
                language=str(payload.get("language") or ""),
                masks=masks,
            )


def row_matches_slice(row: Ai4PrivacyRow, definition: SliceDefinition) -> bool:
    if row.language != "en":
        return False
    labels = {mask.label for mask in row.masks}
    return any(label in labels for label in definition.proxy_labels)


def collect_slice_rows(
    rows: Iterable[Ai4PrivacyRow],
    definitions: Iterable[SliceDefinition],
    *,
    max_rows_per_slice: int | None = None,
) -> dict[str, list[Ai4PrivacyRow]]:
    wanted = {definition.name: definition for definition in definitions}
    selected: dict[str, list[Ai4PrivacyRow]] = {name: [] for name in wanted}
    for row in rows:
        for name, definition in wanted.items():
            if max_rows_per_slice is not None and len(selected[name]) >= max_rows_per_slice:
                continue
            if row_matches_slice(row, definition):
                selected[name].append(row)
        if max_rows_per_slice is not None and all(len(items) >= max_rows_per_slice for items in selected.values()):
            break
    return selected


def _span_matches(prediction: PredictedSpan, mask: PrivacyMask, match_mode: str) -> bool:
    if match_mode == "exact":
        return prediction.start == mask.start and prediction.end == mask.end
    if match_mode == "overlap":
        return prediction.start < mask.end and mask.start < prediction.end
    raise ValueError(f"unsupported match mode: {match_mode}")


def _predict(
    row: Ai4PrivacyRow,
    *,
    engine: Any,
    review_profile: str,
    source_jurisdiction: str,
    categories: set[str] | None,
    diagnostics: list[str] | None = None,
) -> list[PredictedSpan]:
    result = engine.review(
        text=row.source_text,
        source_jurisdiction=source_jurisdiction,
        destination_jurisdiction=source_jurisdiction,
        entity_id=None,
        include_suggestions=False,
        document_type="generic",
        review_profile=review_profile,
    )
    predictions: list[PredictedSpan] = []
    if diagnostics is not None and getattr(result, "degraded_modes", []):
        diagnostics.append(f"{row.row_id}: analysis reported degraded modes")
    for finding in result.findings:
        category = str(getattr(finding, "category", ""))
        if categories is not None and category not in categories:
            continue
        start = int(getattr(finding, "start_char"))
        end = int(getattr(finding, "end_char"))
        if start < 0 or end <= start or end > len(row.source_text):
            if diagnostics is not None:
                diagnostics.append(f"{row.row_id}: invalid prediction offsets omitted by legacy scoring")
            continue
        if diagnostics is not None and (
            type(getattr(finding, "start_char")) is not int
            or type(getattr(finding, "end_char")) is not int
            or getattr(finding, "matched_text", row.source_text[start:end]) != row.source_text[start:end]
        ):
            diagnostics.append(f"{row.row_id}: invalid prediction offsets/text")
        predictions.append(
            PredictedSpan(
                start=start,
                end=end,
                category=category,
                rule=str(getattr(finding, "rule", "")),
            )
        )
    return predictions


def score_slice(
    rows: Iterable[Ai4PrivacyRow],
    *,
    engine: Any,
    review_profile: str,
    source_jurisdiction: str,
    match_mode: str,
    categories: set[str] | None = {"PII"},
    occurrence_output: dict[str, Any] | None = None,
    annotation_coverage: str = "unknown",
) -> SliceScore:
    row_list = list(rows)
    gold_by_label: defaultdict[str, int] = defaultdict(int)
    matched_by_label: defaultdict[str, int] = defaultdict(int)
    gold_spans = 0
    matched_spans = 0
    predicted_spans = 0
    observations = []
    diagnostics: list[str] = []
    for row in row_list:
        predictions = _predict(
            row,
            engine=engine,
            review_profile=review_profile,
            source_jurisdiction=source_jurisdiction,
            categories=categories,
            diagnostics=diagnostics,
        )
        observations.append((row, predictions))
        predicted_spans += len(predictions)
        for mask in row.masks:
            gold_spans += 1
            gold_by_label[mask.label] += 1
            if any(_span_matches(prediction, mask, match_mode) for prediction in predictions):
                matched_spans += 1
                matched_by_label[mask.label] += 1
    if occurrence_output is not None:
        occurrence_output.update(
            corrected_ai_measurements(
                observations, annotation_coverage=annotation_coverage, diagnostics=diagnostics, categories=categories
            )
        )
    recall = matched_spans / gold_spans if gold_spans else 0.0
    return SliceScore(
        documents=len(row_list),
        gold_spans=gold_spans,
        matched_spans=matched_spans,
        recall=_round_metric(recall),
        predicted_spans=predicted_spans,
        matched_by_label=dict(sorted(matched_by_label.items())),
        gold_by_label=dict(sorted(gold_by_label.items())),
    )


def corrected_ai_measurements(observations, *, annotation_coverage="unknown", diagnostics=(), categories=None):
    try:
        observations = list(observations)
        if diagnostics:
            raise ValueError("; ".join(diagnostics))
        if categories is not None and "PII" not in categories:
            raise ValueError("PII predictions were not requested")
        texts = {}
        gold = []
        predictions: list[Span] = []
        originals = {}
        for row, predicted in observations:
            unit = ("unspecified", row.row_id, "dataset")
            if unit in texts:
                raise ValueError("duplicate row identity in selected slice")
            texts[unit] = row.source_text
            for mask in row.masks:
                if not getattr(mask, "offsets_valid", True) or row.source_text[mask.start : mask.end] != mask.value:
                    raise ValueError(f"{row.row_id}: invalid gold offsets/text")
                gold.append(Span(unit, mask.start, mask.end, "PII", "mask"))
                originals[(unit, mask.start, mask.end)] = mask.label
            predictions.extend(Span(unit, p.start, p.end, "PII", "mask") for p in predicted if p.category == "PII")
        scores = occurrence_scores(gold, predictions, texts=texts, coverage={u: annotation_coverage for u in texts})
        for mode in ("exact", "overlap"):
            if mode not in scores:
                continue
            matched = {(tuple(m["unit"]), m["start"], m["end"]) for m in scores[mode]["matched_gold"]}
            scores[mode]["by_upstream_label"] = {}
            for label in sorted(set(originals.values())):
                subset = {k for k, v in originals.items() if v == label}
                hits = len(matched & subset)
                scores[mode]["by_upstream_label"][label] = {
                    "gold": len(subset),
                    "matched": hits,
                    "labeled_span_recall": hits / len(subset),
                    "precision": None,
                    "reason": "no approved classifier-to-upstream label crosswalk",
                }
        return {
            "schema_version": "junas.ai4privacy_occurrence.v1",
            "status": scores["status"],
            "scores": scores,
            "documents": [{"id": r.row_id, "text_sha256": input_identity(r.source_text)} for r, _ in observations],
            "annotation_origin": "external synthetic labels; independent human annotation not established",
            "annotation_coverage": annotation_coverage,
            "coverage_basis": "caller declaration; no exhaustiveness inferred",
            "target": "binary masking vs PII findings; one-to-one per row; no entity-type crosswalk",
            "split": "unspecified; fixture/locale proxy is not a protected evaluation split",
            "holdout_status": "not established",
        }
    except (ValueError, TypeError, AttributeError) as exc:
        return {"schema_version": "junas.ai4privacy_occurrence.v1", "status": "unavailable", "reason": str(exc)}


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_categories(values: list[str]) -> set[str] | None:
    categories = {value.strip() for value in values if value.strip()}
    if "ALL" in categories:
        return None
    return categories


def evaluate_ai4privacy(
    *,
    fixture: Path,
    manifest_path: Path = DEFAULT_MANIFEST,
    slice_names: list[str] | None = None,
    max_rows_per_slice: int | None = None,
    engine_factory: Callable[[], Any] = _default_engine_factory,
    review_profile: str = "strict",
    match_mode: str = "overlap",
    categories: set[str] | None = {"PII"},
    annotation_coverage: str = "unknown",
) -> dict[str, Any]:
    if max_rows_per_slice is not None and (type(max_rows_per_slice) is not int or max_rows_per_slice < 0):
        raise ValueError("slice limit must be a nonnegative integer")
    definitions = [SLICE_DEFINITIONS[name] for name in (slice_names or list(SLICE_DEFINITIONS))]
    selected = collect_slice_rows(iter_ai4privacy_rows(fixture), definitions, max_rows_per_slice=max_rows_per_slice)
    if len({d.name for d in definitions}) != len(definitions):
        raise ValueError("duplicate requested slice")
    engine = engine_factory()
    slices: dict[str, Any] = {}
    occurrences = {}
    for definition in definitions:
        corrected: dict[str, Any] = {}
        score = score_slice(
            selected[definition.name],
            engine=engine,
            review_profile=review_profile,
            source_jurisdiction=definition.source_jurisdiction,
            match_mode=match_mode,
            categories=categories,
            occurrence_output=corrected,
            annotation_coverage=annotation_coverage,
        )
        occurrences[definition.name] = corrected
        slices[definition.name] = {
            **asdict(score),
            "source_jurisdiction": definition.source_jurisdiction,
            "proxy_labels": list(definition.proxy_labels),
            "slice_method": "label_proxy",
            "rationale": definition.rationale,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "legacy_metric_contract": "slice_results retain many-to-one gold coverage recall; no precision was measured",
        "occurrence_v1": occurrences,
        "input_identity_v1": {
            "fixture_sha256": file_sha256(fixture),
            "manifest_sha256": file_sha256(manifest_path) if manifest_path.is_file() else None,
            "prediction_origin": "bundled_engine"
            if engine_factory is _default_engine_factory
            else "caller_supplied_engine; not fingerprinted",
        },
        "reproducibility_v1": reproducibility(Path(__file__)),
        "cross_slice_duplicate_row_ids": sorted(
            set.intersection(*(set(r.row_id for r in selected[d.name]) for d in definitions))
        )
        if len(definitions) > 1
        else [],
        "source": {
            "name": DATASET_ID,
            "url": DATASET_URL,
            "fixture_path": str(fixture.relative_to(REPO_ROOT) if fixture.is_relative_to(REPO_ROOT) else fixture),
            "manifest": _load_manifest(manifest_path),
            "independence_tier": "semi-independent",
            "independence_reason": (
                "External synthetic dataset generated by ai4privacy proprietary algorithms with human-in-the-loop "
                "validation claims; Hugging Face also publishes a Presidio-powered PII detection report, so this is "
                "not treated as manually annotated independence like TAB."
            ),
            "locale_field_available": False,
        },
        "evaluation": {
            "review_profile": review_profile,
            "match_mode": match_mode,
            "finding_categories": sorted(categories) if categories is not None else ["ALL"],
            "slices": [definition.name for definition in definitions],
            "max_rows_per_slice": max_rows_per_slice,
        },
        "slice_results": slices,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate Junas recall on ai4privacy pii-masking-200k")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--slices", nargs="+", choices=tuple(SLICE_DEFINITIONS), default=tuple(SLICE_DEFINITIONS))
    parser.add_argument("--max-rows-per-slice", type=int, default=0, help="0 means full selected slice")
    parser.add_argument("--profile", choices=("strict", "audit_grade"), default="strict")
    parser.add_argument("--match-mode", choices=("exact", "overlap"), default="overlap")
    parser.add_argument(
        "--annotation-coverage",
        choices=("unknown", "partial", "exhaustive"),
        default="unknown",
        help="Declaration for corrected target metrics only; does not certify annotation independence",
    )
    parser.add_argument("--categories", nargs="+", default=["PII"], help="Finding categories to score; use ALL for all")
    args = parser.parse_args(argv)

    fixture = args.fixture if args.fixture.is_absolute() else REPO_ROOT / args.fixture
    if not fixture.is_file():
        print(
            f"missing ai4privacy fixture at {fixture}; run scripts/fetch_ai4privacy_fixture.py first",
            file=sys.stderr,
        )
        return 2
    max_rows = args.max_rows_per_slice if args.max_rows_per_slice > 0 else None
    report = evaluate_ai4privacy(
        fixture=fixture,
        manifest_path=args.manifest if args.manifest.is_absolute() else REPO_ROOT / args.manifest,
        slice_names=list(args.slices),
        max_rows_per_slice=max_rows,
        review_profile=args.profile,
        match_mode=args.match_mode,
        categories=_parse_categories(args.categories),
        annotation_coverage=args.annotation_coverage,
    )
    output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for name, result in report["slice_results"].items():
        print(
            f"{name} legacy gold-coverage recall={result['recall']:.6f} "
            f"matched={result['matched_spans']} gold={result['gold_spans']} docs={result['documents']}"
        )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
