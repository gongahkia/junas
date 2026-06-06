from __future__ import annotations

import importlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from api.indices import (
    ES,
    LEGIS_ID_COLLAPSE,
    LEGIS_ID_FIELD,
    LEGAL_SEARCH_SORT,
    PaginationCursor,
    QDRANT,
    SORT_DATE_FIELD,
)


class SourceType(str, Enum):
    STATUTE = "statute"
    GLOSSARY = "glossary"
    CASE_LAW = "case_law"


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    source_type: SourceType
    source_id: str
    metadata: dict[str, Any]
    score: float


class RetrievalOrchestrator:
    _embedder: Any = None

    def __init__(self, es_client: Any, qdrant_client: Any, case_service: Any | None = None):
        self.es = es_client
        self.qdrant = qdrant_client
        self.case_service = case_service

    @classmethod
    def _get_embedder(cls) -> Any:
        if cls._embedder is not None:
            return cls._embedder

        module = importlib.import_module("sentence_transformers")
        sentence_transformer_cls = getattr(module, "SentenceTransformer", None)
        if sentence_transformer_cls is None:
            raise RuntimeError("sentence-transformers is unavailable")

        cls._embedder = sentence_transformer_cls("sentence-transformers/all-MiniLM-L6-v2")
        return cls._embedder

    async def retrieve(
        self,
        query: str,
        sources: list[SourceType] | None = None,
        top_k: int = 10,
        cursor: PaginationCursor | None = None,
    ) -> list[RetrievedChunk]:
        selected_sources = sources or [SourceType.STATUTE, SourceType.GLOSSARY]
        chunks: list[RetrievedChunk] = []

        if SourceType.STATUTE in selected_sources:
            es_hits = await self._search_statutes_es(query, top_k * 2, cursor=cursor)
            vector_hits = await self._search_statutes_vector(query, top_k * 2)
            chunks.extend(self._rrf_merge(es_hits, vector_hits, top_k * 2))

        if SourceType.GLOSSARY in selected_sources:
            chunks.extend(await self._search_glossary(query, top_k))

        if SourceType.CASE_LAW in selected_sources:
            chunks.extend(await self._search_case_law(query, top_k))

        unique_chunks = self._dedupe_keep_best(chunks)
        unique_chunks.sort(key=lambda item: item.score, reverse=True)
        return unique_chunks[:top_k]

    async def _search_statutes_es(
        self,
        query: str,
        limit: int,
        cursor: PaginationCursor | None = None,
    ) -> list[RetrievedChunk]:
        if self.es is None:
            return []

        body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["name^3", "text_plain^2", "cross_references"],
                    "type": "best_fields",
                }
            },
            "size": limit,
            "collapse": LEGIS_ID_COLLAPSE,
            "sort": LEGAL_SEARCH_SORT,
            "track_total_hits": True,
        }
        if cursor is not None:
            body["search_after"] = cursor.sort_values
        response = await self.es.search(index=ES.statutes, body=body)
        hits = response.get("hits", {}).get("hits", [])

        chunks: list[RetrievedChunk] = []
        for hit in hits:
            source = hit.get("_source", {})
            number = str(source.get("number", "")).strip()
            if not number:
                continue

            chunks.append(
                RetrievedChunk(
                    text=str(source.get("text_plain", ""))[:1600],
                    source_type=SourceType.STATUTE,
                    source_id=f"ORS {number}",
                    metadata={
                        "number": number,
                        "name": source.get("name", ""),
                        "chapter": source.get("chapter_number", ""),
                        LEGIS_ID_FIELD: _legis_id_from_statute_source(source),
                        SORT_DATE_FIELD: _sort_date_from_source(source),
                        "version_id": source.get("version_id", ""),
                    },
                    score=float(hit.get("_score", 0.0)),
                )
            )

        return chunks

    async def _search_statutes_vector(self, query: str, limit: int) -> list[RetrievedChunk]:
        if self.qdrant is None:
            return []

        try:
            embedder = self._get_embedder()
        except Exception:
            return []

        raw_vector = embedder.encode(query)
        if hasattr(raw_vector, "tolist"):
            query_vector = raw_vector.tolist()
        else:
            query_vector = list(raw_vector)

        try:
            if hasattr(self.qdrant, "search"):
                hits = await self.qdrant.search(
                    collection_name=QDRANT.statutes,
                    query_vector=query_vector,
                    limit=limit,
                )
            elif hasattr(self.qdrant, "query_points"):
                response = await self.qdrant.query_points(
                    collection_name=QDRANT.statutes,
                    query=query_vector,
                    limit=limit,
                )
                hits = getattr(response, "points", response)
            else:
                return []
        except Exception:
            return []

        chunks: list[RetrievedChunk] = []
        for hit in hits:
            payload = getattr(hit, "payload", None) or {}
            number = str(payload.get("number", "")).strip()
            if not number:
                continue

            chunks.append(
                RetrievedChunk(
                    text=str(payload.get("text_snippet", "")),
                    source_type=SourceType.STATUTE,
                    source_id=f"ORS {number}",
                    metadata={
                        "number": number,
                        "name": payload.get("name", ""),
                        "chapter": payload.get("chapter_number", ""),
                        LEGIS_ID_FIELD: _legis_id_from_statute_source(payload),
                        SORT_DATE_FIELD: _sort_date_from_source(payload),
                    },
                    score=float(getattr(hit, "score", 0.0)),
                )
            )

        return chunks

    async def _search_glossary(self, query: str, limit: int) -> list[RetrievedChunk]:
        if self.es is None:
            return []

        body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["phrase^3", "definition_text"],
                    "type": "best_fields",
                }
            },
            "size": limit,
        }
        response = await self.es.search(index=ES.glossary, body=body)
        hits = response.get("hits", {}).get("hits", [])

        chunks: list[RetrievedChunk] = []
        for hit in hits:
            source = hit.get("_source", {})
            phrase = str(source.get("phrase", "")).strip()
            if not phrase:
                continue

            definition = str(source.get("definition_text", "")).strip()
            chunks.append(
                RetrievedChunk(
                    text=f"{phrase}: {definition}" if definition else phrase,
                    source_type=SourceType.GLOSSARY,
                    source_id=phrase,
                    metadata={
                        "jurisdiction": source.get("jurisdiction", ""),
                        "domain": source.get("domain", ""),
                        "source_title": source.get("source_title", ""),
                    },
                    score=float(hit.get("_score", 0.0)),
                )
            )

        return chunks

    async def _search_case_law(self, query: str, limit: int) -> list[RetrievedChunk]:
        if self.case_service is not None:
            try:
                payload = self.case_service.search_cases(
                    query=query,
                    top_k=limit,
                    stages=["bm25", "dense", "rerank"],
                    include_scores=True,
                )
            except Exception:
                payload = None

            if isinstance(payload, dict):
                results = payload.get("results", [])
                chunks: list[RetrievedChunk] = []
                for row in results:
                    case_id = str(row.get("case_id", "")).strip()
                    if not case_id:
                        continue
                    facts = str(row.get("facts", "")).strip()
                    judgment = str(row.get("judgment", "")).strip()
                    text = facts if facts else judgment
                    if facts and judgment:
                        text = f"{facts[:800]}\n\nJudgment: {judgment[:400]}"

                    chunks.append(
                        RetrievedChunk(
                            text=text,
                            source_type=SourceType.CASE_LAW,
                            source_id=case_id,
                            metadata={
                                "case_name": row.get("case_name", ""),
                                "charges": row.get("charges", []),
                                "retrieval_stage": row.get("retrieval_stage", ""),
                                LEGIS_ID_FIELD: str(row.get(LEGIS_ID_FIELD) or case_id),
                                SORT_DATE_FIELD: row.get(SORT_DATE_FIELD, ""),
                            },
                            score=float(row.get("relevance_score", 0.0) or 0.0),
                        )
                    )
                return chunks

        if self.qdrant is None:
            return []

        try:
            embedder = self._get_embedder()
        except Exception:
            return []

        raw_vector = embedder.encode(query)
        if hasattr(raw_vector, "tolist"):
            query_vector = raw_vector.tolist()
        else:
            query_vector = list(raw_vector)

        try:
            if hasattr(self.qdrant, "search"):
                hits = await self.qdrant.search(
                    collection_name=QDRANT.cases,
                    query_vector=query_vector,
                    limit=limit,
                )
            elif hasattr(self.qdrant, "query_points"):
                response = await self.qdrant.query_points(
                    collection_name=QDRANT.cases,
                    query=query_vector,
                    limit=limit,
                )
                hits = getattr(response, "points", response)
            else:
                return []
        except Exception:
            return []

        vector_chunks: list[RetrievedChunk] = []
        for hit in hits:
            payload = getattr(hit, "payload", None) or {}
            case_id = str(payload.get("ajId", "")).strip()
            if not case_id:
                continue

            vector_chunks.append(
                RetrievedChunk(
                    text=str(payload.get("text_snippet", "")),
                    source_type=SourceType.CASE_LAW,
                    source_id=case_id,
                    metadata={
                        "case_name": payload.get("ajName", ""),
                        LEGIS_ID_FIELD: str(payload.get(LEGIS_ID_FIELD) or case_id),
                        SORT_DATE_FIELD: payload.get(SORT_DATE_FIELD, ""),
                    },
                    score=float(getattr(hit, "score", 0.0)),
                )
            )

        return vector_chunks

    @staticmethod
    def _rrf_merge(es_hits: list[RetrievedChunk], vector_hits: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        rrf_k = 60
        scores: dict[tuple[str, str], float] = {}
        chunks_by_key: dict[tuple[str, str], RetrievedChunk] = {}

        def _apply(hits: Iterable[RetrievedChunk]) -> None:
            for rank, chunk in enumerate(hits):
                key = RetrievalOrchestrator._dedupe_key(chunk)
                score = 1.0 / (rrf_k + rank + 1)
                scores[key] = scores.get(key, 0.0) + score
                chunks_by_key[key] = chunk

        _apply(es_hits)
        _apply(vector_hits)

        merged = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
        return [
            RetrievedChunk(
                text=chunks_by_key[key].text,
                source_type=chunks_by_key[key].source_type,
                source_id=chunks_by_key[key].source_id,
                metadata=chunks_by_key[key].metadata,
                score=float(score),
            )
            for key, score in merged
        ]

    @staticmethod
    def _dedupe_keep_best(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        best: dict[tuple[str, str], RetrievedChunk] = {}
        for chunk in chunks:
            key = RetrievalOrchestrator._dedupe_key(chunk)
            previous = best.get(key)
            if previous is None or chunk.score > previous.score:
                best[key] = chunk
        return list(best.values())

    @staticmethod
    def _dedupe_key(chunk: RetrievedChunk) -> tuple[str, str]:
        legis_id = str(chunk.metadata.get(LEGIS_ID_FIELD) or "").strip()
        if legis_id and chunk.source_type in {SourceType.STATUTE, SourceType.CASE_LAW}:
            return (chunk.source_type.value, legis_id)
        return (chunk.source_type.value, chunk.source_id)


def _legis_id_from_statute_source(source: dict[str, Any]) -> str:
    value = str(source.get(LEGIS_ID_FIELD) or "").strip()
    if value:
        return value
    chapter = str(source.get("chapter_number") or "").strip()
    number = str(source.get("number") or "").strip()
    return f"{chapter}:{number}" if chapter and number else number


def _sort_date_from_source(source: dict[str, Any]) -> str:
    return str(source.get(SORT_DATE_FIELD) or source.get("valid_start_date") or "").strip()
