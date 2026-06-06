"""Pipeline: ingest SSO statutes JSONL into Elasticsearch + Qdrant.

Replaces the legacy ``ingest_statutes.py`` ORS-only path with the SG SSO
flow per #25 + #28. The data source is the JSONL produced by
``backend/data/ingestion/sso.py``; this module only handles indexing.

If the SSO JSONL is missing on disk this pipeline will invoke the
ingestion module itself (``backend.data.ingestion.sso.run``) to fetch +
materialise it. Reruns are idempotent at the JSONL level.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import logging
import re
from itertools import count
from pathlib import Path
from typing import Any, Iterator

from prefect import flow, task

from api.indices import ES, LEGIS_ID_FIELD, QDRANT, SORT_DATE_FIELD
from data.ingestion.sso import DEFAULT_OUTPUT as SSO_JSONL_DEFAULT
from data.ingestion.sso import run as sso_ingest_run

logger = logging.getLogger(__name__)

INDEX_NAME = ES.statutes
COLLECTION_NAME = QDRANT.statutes
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
ES_BATCH_SIZE = 500
QDRANT_BATCH_SIZE = 256
MAX_EMBED_CHARS = 2000

MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "legal_english": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "english_stemmer", "english_stop"],
                }
            },
            "filter": {
                "english_stemmer": {"type": "stemmer", "language": "english"},
                "english_stop": {"type": "stop", "stopwords": "_english_"},
            },
        },
    },
    "mappings": {
        "properties": {
            # core fields (kept stable for backward compat with statute_lookup callers)
            "number": {"type": "keyword"},
            "name": {
                "type": "text",
                "analyzer": "legal_english",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "chapter_number": {"type": "keyword"},
            "edition": {"type": "integer"},
            "kind": {"type": "keyword"},
            "text_plain": {"type": "text", "analyzer": "legal_english"},
            "text_html": {"type": "text", "index": False},
            "amendment_history": {"type": "text", "index": False},
            "cross_references": {"type": "keyword"},
            # SSO-specific provenance + structural metadata
            "act_title": {"type": "text", "analyzer": "legal_english"},
            "part": {"type": "keyword"},
            "division": {"type": "keyword"},
            "source_url": {"type": "keyword", "index": False},
            "version_id": {"type": "keyword"},
            "valid_start_date": {"type": "keyword"},
            "section_id": {"type": "keyword"},
            LEGIS_ID_FIELD: {"type": "keyword"},
            SORT_DATE_FIELD: {"type": "date"},
        }
    },
}

HTML_TAG_RE = re.compile(r"<[^>]+>")


def _optional_import(module_name: str, attr_name: str | None = None) -> Any:
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
        return None
    if attr_name is None:
        return module
    return getattr(module, attr_name, None)


AsyncElasticsearch = _optional_import("elasticsearch", "AsyncElasticsearch")
QdrantClient = _optional_import("qdrant_client", "QdrantClient")
Distance = _optional_import("qdrant_client.models", "Distance")
PointStruct = _optional_import("qdrant_client.models", "PointStruct")
VectorParams = _optional_import("qdrant_client.models", "VectorParams")
SentenceTransformer = _optional_import("sentence_transformers", "SentenceTransformer")


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                yield json.loads(text)
            except json.JSONDecodeError as exc:
                logger.warning("skipping malformed JSONL line: %s", exc)


def _id_for(row: dict[str, Any]) -> str:
    """Stable ES doc id. Uses ``section_id`` (``version_id:number``) if
    present, falls back to ``chapter_number:number`` for back-compat."""
    sid = row.get("section_id")
    if sid:
        return str(sid)
    return f"{row.get('chapter_number', '')}:{row.get('number', '')}"


def _legis_id_for(row: dict[str, Any]) -> str:
    value = str(row.get(LEGIS_ID_FIELD) or "").strip()
    if value:
        return value
    chapter = str(row.get("chapter_number") or "").strip()
    number = str(row.get("number") or "").strip()
    return f"{chapter}:{number}" if chapter and number else str(row.get("section_id") or "").strip()


def _sort_date_for(row: dict[str, Any]) -> str:
    return str(row.get(SORT_DATE_FIELD) or row.get("valid_start_date") or "").strip()


def _source_for_es(row: dict[str, Any]) -> dict[str, Any]:
    source = dict(row)
    source[LEGIS_ID_FIELD] = _legis_id_for(source)
    sort_date = _sort_date_for(source)
    if sort_date:
        source[SORT_DATE_FIELD] = sort_date
    return source


@task
async def create_es_index(es: Any) -> None:
    if await es.indices.exists(index=INDEX_NAME):
        await es.indices.delete(index=INDEX_NAME)
    await es.indices.create(index=INDEX_NAME, body=MAPPING)


@task
async def index_es_batch(es: Any, batch: list[dict[str, Any]]) -> int:
    operations: list[dict[str, Any]] = []
    for row in batch:
        operations.append({"index": {"_index": INDEX_NAME, "_id": _id_for(row)}})
        operations.append(_source_for_es(row))
    if operations:
        await es.bulk(operations=operations, refresh=False)
    return len(batch)


def _strip(value: str) -> str:
    return HTML_TAG_RE.sub(" ", value or "").strip()


def _paragraph_chunks(row: dict[str, Any]) -> list[str]:
    text_plain = str(row.get("text_plain", ""))
    if len(text_plain) <= MAX_EMBED_CHARS:
        return [text_plain]
    raw_parts = re.split(r"</p>", str(row.get("text_html", "")))
    parts = [_strip(part) for part in raw_parts if part]
    parts = [part for part in parts if part]
    if not parts:
        return [text_plain[:MAX_EMBED_CHARS]]
    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = (current + " " + part).strip() if current else part
        if len(candidate) <= MAX_EMBED_CHARS:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = part[:MAX_EMBED_CHARS]
    if current:
        chunks.append(current)
    return chunks


def _build_qdrant_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        for chunk_index, chunk_text in enumerate(_paragraph_chunks(row)):
            out.append(
                {
                    "number": row.get("number", ""),
                    "name": row.get("name", ""),
                    "chapter_number": row.get("chapter_number", ""),
                    LEGIS_ID_FIELD: _legis_id_for(row),
                    SORT_DATE_FIELD: _sort_date_for(row),
                    "chunk_index": chunk_index,
                    "text": chunk_text,
                    "text_snippet": chunk_text[:200],
                }
            )
    return out


def _index_qdrant(rows: list[dict[str, Any]]) -> int:
    if QdrantClient is None or VectorParams is None or Distance is None or PointStruct is None:
        raise RuntimeError("qdrant client is not installed")
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers is not installed")

    client = QdrantClient(url="http://localhost:6333")
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    total = 0
    id_counter = count(start=1)

    for start in range(0, len(rows), QDRANT_BATCH_SIZE):
        batch = rows[start : start + QDRANT_BATCH_SIZE]
        texts = [row["text"] for row in batch]
        embeddings = model.encode(texts, batch_size=64, show_progress_bar=False)
        points = []
        for i, row in enumerate(batch):
            points.append(
                PointStruct(
                    id=next(id_counter),
                    vector=embeddings[i].tolist(),
                    payload={
                        "number": row["number"],
                        "name": row["name"],
                        "chapter_number": row["chapter_number"],
                        LEGIS_ID_FIELD: row[LEGIS_ID_FIELD],
                        SORT_DATE_FIELD: row[SORT_DATE_FIELD],
                        "chunk_index": row["chunk_index"],
                        "text_snippet": row["text_snippet"],
                    },
                )
            )
        client.upsert(collection_name=COLLECTION_NAME, points=points)
        total += len(points)
    client.close()
    return total


@flow(name="ingest-sso")
async def ingest_sso(jsonl_path: str | Path | None = None) -> int:
    """Index SSO statutes JSONL into ES + Qdrant.

    If ``jsonl_path`` is missing, the SSO scraper is invoked first.
    """
    if AsyncElasticsearch is None:
        raise RuntimeError("elasticsearch client is not installed")
    path = Path(jsonl_path) if jsonl_path else SSO_JSONL_DEFAULT
    if not path.exists():
        logger.info("SSO JSONL not found at %s; running scraper", path)
        sso_ingest_run(path)
    rows = list(iter_jsonl(path))
    logger.info("SSO loaded %d rows from %s", len(rows), path)

    es = AsyncElasticsearch("http://localhost:9200")
    await create_es_index(es)
    for start in range(0, len(rows), ES_BATCH_SIZE):
        batch = rows[start : start + ES_BATCH_SIZE]
        await index_es_batch(es, batch)
    await es.indices.refresh(index=INDEX_NAME)
    await es.close()

    qdrant_rows = _build_qdrant_rows(rows)
    _index_qdrant(qdrant_rows)
    return len(rows)


def run(jsonl_path: str | Path | None = None) -> int:
    return asyncio.run(ingest_sso(jsonl_path))


def run_scraper_only(output_path: Path | str = SSO_JSONL_DEFAULT, force: bool = False) -> int:
    """Invoke the scraper only, no ES/Qdrant indexing. Used by ``make ingest-sso``
    when no infra is running locally."""
    return sso_ingest_run(output_path, force=force)


if __name__ == "__main__":
    print(run())
