from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from data.parsers.lecard_parser import (
    attach_candidate_charges,
    build_candidate_charge_map,
    build_corpus,
    discover_lecard_data_root,
    load_all_candidates,
    load_baseline_predictions,
    load_criminal_charges,
    load_labels,
    load_queries,
    load_stopwords,
)
from ml.retrieval.case_retrieval import (
    DEFAULT_BIENCODER_MODEL,
    DEFAULT_CROSS_ENCODER_MODEL,
    CaseRetrievalPipeline,
)


def _ndcg_at_k(predicted_ids: list[str], label_map: dict[str, int], k: int) -> float:
    ideal = sorted(label_map.values(), reverse=True)[:k]
    if not ideal or sum(ideal) == 0:
        return 0.0
    gains = [label_map.get(str(case_id), 0) for case_id in predicted_ids[:k]]
    if len(gains) < k:
        gains.extend([0] * (k - len(gains)))
    dcg = 0.0
    idcg = 0.0
    for idx in range(k):
        discount = math.log2(idx + 2)
        dcg += gains[idx] / discount
        idcg += ideal[idx] / discount
    return dcg / idcg if idcg > 0 else 0.0


def _precision_at_k(predicted_ids: list[str], label_map: dict[str, int], k: int) -> float:
    if k <= 0:
        return 0.0
    hits = sum(1 for case_id in predicted_ids[:k] if label_map.get(str(case_id), 0) == 3)
    return hits / k


def _mean_average_precision(predictions: dict[str, list[str]], labels: dict[str, dict[str, int]]) -> float:
    ap_values: list[float] = []
    for ridx, label_map in labels.items():
        predicted = [case_id for case_id in predictions.get(ridx, []) if case_id in label_map]
        relevant_total = sum(1 for score in label_map.values() if int(score) == 3)
        if relevant_total == 0:
            ap_values.append(0.0)
            continue
        score_sum = 0.0
        hit_count = 0
        for rank, case_id in enumerate(predicted, start=1):
            if int(label_map.get(case_id, 0)) == 3:
                hit_count += 1
                score_sum += hit_count / rank
        ap_values.append(score_sum / relevant_total if hit_count else 0.0)
    return sum(ap_values) / len(ap_values) if ap_values else 0.0


def evaluate_predictions(predictions: dict[str, list[str]], labels: dict[str, dict[str, int]]) -> dict[str, float]:
    query_ids = [qid for qid in labels.keys() if qid in predictions]
    if not query_ids:
        return {"NDCG@10": 0.0, "NDCG@20": 0.0, "NDCG@30": 0.0, "P@5": 0.0, "P@10": 0.0, "MAP": 0.0}
    n = len(query_ids)
    return {
        "NDCG@10": sum(_ndcg_at_k(predictions[qid], labels[qid], 10) for qid in query_ids) / n,
        "NDCG@20": sum(_ndcg_at_k(predictions[qid], labels[qid], 20) for qid in query_ids) / n,
        "NDCG@30": sum(_ndcg_at_k(predictions[qid], labels[qid], 30) for qid in query_ids) / n,
        "P@5": sum(_precision_at_k(predictions[qid], labels[qid], 5) for qid in query_ids) / n,
        "P@10": sum(_precision_at_k(predictions[qid], labels[qid], 10) for qid in query_ids) / n,
        "MAP": _mean_average_precision(predictions, labels),
    }

DEFAULT_METRICS_PATH = "models/case-retrieval/eval_results.json"
PUBLISHED_BASELINES = {
    "BM25": {"NDCG@10": 0.731, "NDCG@20": 0.773, "NDCG@30": 0.812, "P@5": 0.640, "P@10": 0.580, "MAP": 0.484},
    "TFIDF": {"NDCG@10": 0.715, "NDCG@20": 0.759, "NDCG@30": 0.800, "P@5": 0.626, "P@10": 0.570, "MAP": 0.471},
    "LM": {"NDCG@10": 0.728, "NDCG@20": 0.768, "NDCG@30": 0.807, "P@5": 0.637, "P@10": 0.575, "MAP": 0.479},
    "BERT": {"NDCG@10": 0.830, "NDCG@20": 0.867, "NDCG@30": 0.899, "P@5": 0.746, "P@10": 0.668, "MAP": 0.568},
}


class CaseRetrievalService:
    def __init__(
        self,
        pipeline: CaseRetrievalPipeline,
        corpus: dict[str, dict[str, Any]],
        known_charges: list[str],
        labels: dict[str, dict[str, int]],
        baseline_predictions: dict[str, dict[str, list[str]]],
        metrics_path: str | Path = DEFAULT_METRICS_PATH,
    ):
        self.pipeline = pipeline
        self.corpus = corpus
        self.known_charges = sorted(set(known_charges))
        self.labels = labels
        self.baseline_predictions = baseline_predictions
        self.metrics_path = Path(metrics_path)

    def search_cases(
        self,
        query: str,
        top_k: int = 10,
        stages: list[str] | None = None,
        include_scores: bool = True,
    ) -> dict[str, Any]:
        payload = self.pipeline.search(query_text=query, top_k=top_k, stages=stages)
        results = payload["results"]
        if not include_scores:
            for row in results:
                row.pop("relevance_score", None)
        return {
            "query": query,
            "results": results,
            "retrieval_info": payload["retrieval_info"],
        }

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        row = self.corpus.get(case_id)
        if row is None:
            return None
        return {
            "case_id": case_id,
            "ajId": row.get("ajId", ""),
            "case_name": row.get("ajName", ""),
            "facts": row.get("ajjbqk", ""),
            "judgment": row.get("pjjg", ""),
            "full_text": row.get("qw", ""),
            "charges": row.get("charges", []),
            "writ_id": row.get("writId", ""),
            "writ_name": row.get("writName", ""),
        }

    def list_charges(self) -> list[str]:
        charges = set(self.known_charges)
        for row in self.corpus.values():
            for charge in row.get("charges", []):
                charge_str = str(charge).strip()
                if charge_str:
                    charges.add(charge_str)
        return sorted(charges)

    def get_metrics(self) -> dict[str, Any]:
        latest: dict[str, Any] | None = None
        if self.metrics_path.exists() and self.metrics_path.is_file():
            try:
                latest = json.loads(self.metrics_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                latest = None

        computed_baselines = {
            name.upper(): evaluate_predictions(predictions, self.labels)
            for name, predictions in self.baseline_predictions.items()
            if predictions
        }

        return {
            "published": PUBLISHED_BASELINES,
            "computed_baselines": computed_baselines,
            "latest": latest,
        }


def create_case_retrieval_service(
    data_root: str | Path | None = None,
    qdrant_url: str = "http://localhost:6333",
    biencoder_model_path: str = DEFAULT_BIENCODER_MODEL,
    cross_encoder_model_path: str = DEFAULT_CROSS_ENCODER_MODEL,
    metrics_path: str | Path = DEFAULT_METRICS_PATH,
) -> CaseRetrievalService | None:
    root = Path(data_root) if data_root is not None else discover_lecard_data_root()
    if not root.exists() or not root.is_dir():
        return None

    queries = load_queries(root)
    labels = load_labels(root)
    all_candidates = load_all_candidates(queries, root)
    corpus = build_corpus(all_candidates)
    if not corpus:
        return None

    charge_map = build_candidate_charge_map(queries, all_candidates)
    corpus = attach_candidate_charges(corpus, charge_map)

    pipeline = CaseRetrievalPipeline(
        corpus=corpus,
        stopwords=load_stopwords(root),
        qdrant_url=qdrant_url,
        biencoder_model_path=biencoder_model_path,
        cross_encoder_model_path=cross_encoder_model_path,
    )

    return CaseRetrievalService(
        pipeline=pipeline,
        corpus=corpus,
        known_charges=load_criminal_charges(root),
        labels=labels,
        baseline_predictions=load_baseline_predictions(root),
        metrics_path=metrics_path,
    )
