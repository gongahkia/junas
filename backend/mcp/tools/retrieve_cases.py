"""MCP wrapper for local case retrieval."""
from __future__ import annotations


def _create_service():
    from api.config import get_settings
    from api.services.case_retrieval import create_case_retrieval_service

    settings = get_settings()
    return create_case_retrieval_service(
        data_root=settings.lecard_data_root,
        qdrant_url=settings.qdrant_url,
        biencoder_model_path=settings.case_biencoder_model_path,
        cross_encoder_model_path=settings.case_cross_encoder_model_path,
        metrics_path=settings.case_retrieval_metrics_path,
    )


def retrieve_cases(query: str, k: int = 5) -> dict:
    raw = str(query or "").strip()
    if not raw:
        return {"error": "query must not be blank"}
    top_k = max(1, min(int(k or 5), 50))

    try:
        service = _create_service()
        if service is None:
            return {"query": raw, "error": "case retrieval corpus is unavailable"}
        return service.search_cases(query=raw, top_k=top_k, include_scores=True)
    except Exception as exc:  # noqa: BLE001
        return {"query": raw, "error": str(exc)}
