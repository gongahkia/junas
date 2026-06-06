from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from api.indices import LEGIS_ID_COLLAPSE, LEGIS_ID_FIELD, LEGAL_SEARCH_SORT, PaginationCursor
from api.services.case_retrieval import CaseRetrievalService
from api.services.retrieval_orchestrator import RetrievalOrchestrator, SourceType
from api.services.statute_lookup import StatuteService


class RecordingES:
    def __init__(self, responses: list[dict[str, Any]]):
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def search(self, index: str, body: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"index": index, "body": body})
        return self.responses.pop(0)


class StubQdrant:
    async def search(self, **_: Any) -> list[Any]:
        return [
            SimpleNamespace(
                payload={
                    "number": "13",
                    "name": "Consent required",
                    "chapter_number": "PDPA2012",
                    LEGIS_ID_FIELD: "PDPA2012:13",
                    "sort_date": "2021-12-31",
                    "text_snippet": "vector copy",
                },
                score=0.98,
            )
        ]


class StubEmbedder:
    def encode(self, _: str) -> list[float]:
        return [0.1, 0.2, 0.3]


def _statute_hit(number: str, legis_id: str, sort_values: list[Any], score: float = 1.0) -> dict[str, Any]:
    return {
        "_score": score,
        "sort": sort_values,
        "_source": {
            "number": number,
            "name": "Consent required",
            "chapter_number": "PDPA2012",
            "text_plain": "statute text",
            LEGIS_ID_FIELD: legis_id,
            "sort_date": sort_values[0],
            "version_id": "PDPA2012@2020",
        },
    }


def test_statute_keyword_search_uses_collapse_sort_and_next_cursor() -> None:
    es = RecordingES(
        [
            {
                "hits": {
                    "total": {"value": 3},
                    "hits": [
                        _statute_hit("13", "PDPA2012:13", ["2021-12-31", "PDPA2012:13"]),
                        _statute_hit("14", "PDPA2012:14", ["2021-12-30", "PDPA2012:14"]),
                    ],
                }
            }
        ]
    )
    service = StatuteService(es=es, qdrant=None)

    payload = asyncio.run(service.search(q="consent", chapter="PDPA2012", mode="keyword", page=1, per_page=2))

    body = es.calls[0]["body"]
    assert "from" not in body
    assert body["size"] == 2
    assert body["collapse"] == LEGIS_ID_COLLAPSE
    assert body["sort"] == LEGAL_SEARCH_SORT
    assert payload["results"][0][LEGIS_ID_FIELD] == "PDPA2012:13"
    assert PaginationCursor.from_token(payload["next_cursor"]).sort_values == ["2021-12-30", "PDPA2012:14"]


def test_statute_keyword_search_applies_search_after_cursor() -> None:
    cursor = PaginationCursor(sort_values=["2021-12-30", "PDPA2012:14"])
    es = RecordingES([{"hits": {"total": {"value": 3}, "hits": []}}])
    service = StatuteService(es=es, qdrant=None)

    asyncio.run(service.search(q="consent", chapter=None, mode="keyword", page=1, per_page=2, cursor=cursor))

    assert es.calls[0]["body"]["search_after"] == ["2021-12-30", "PDPA2012:14"]


def test_orchestrator_dedupes_statute_halves_by_legis_id() -> None:
    es = RecordingES(
        [
            {
                "hits": {
                    "total": {"value": 1},
                    "hits": [_statute_hit("13", "PDPA2012:13", ["2021-12-31", "PDPA2012:13"])],
                }
            }
        ]
    )
    previous = RetrievalOrchestrator._embedder
    RetrievalOrchestrator._embedder = StubEmbedder()
    try:
        orchestrator = RetrievalOrchestrator(es_client=es, qdrant_client=StubQdrant())
        chunks = asyncio.run(
            orchestrator.retrieve(
                "consent",
                sources=[SourceType.STATUTE],
                top_k=5,
                cursor=PaginationCursor(sort_values=["2021-12-31", "PDPA2012:12"]),
            )
        )
    finally:
        RetrievalOrchestrator._embedder = previous

    assert len(chunks) == 1
    assert chunks[0].metadata[LEGIS_ID_FIELD] == "PDPA2012:13"
    assert chunks[0].score > 1 / 61
    assert es.calls[0]["body"]["collapse"] == LEGIS_ID_COLLAPSE
    assert es.calls[0]["body"]["search_after"] == ["2021-12-31", "PDPA2012:12"]


def test_case_service_dedupes_by_legis_id_before_returning_results() -> None:
    class StubPipeline:
        def search(self, **_: Any) -> dict[str, Any]:
            return {
                "results": [
                    {"case_id": "old", LEGIS_ID_FIELD: "case-1", "relevance_score": 0.1},
                    {"case_id": "new", LEGIS_ID_FIELD: "case-1", "relevance_score": 0.9},
                    {"case_id": "other", "relevance_score": 0.2},
                ],
                "retrieval_info": {"stages_used": ["bm25"]},
            }

    service = CaseRetrievalService(
        pipeline=StubPipeline(),
        corpus={},
        known_charges=[],
        labels={},
        baseline_predictions={},
    )

    payload = service.search_cases("query")

    assert [row["case_id"] for row in payload["results"]] == ["new", "other"]
