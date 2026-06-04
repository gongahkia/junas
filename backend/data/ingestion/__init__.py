"""SG public-source ingestion modules (port of kevanwee/* scrapers).

Each module here downloads from a SG public legal source, applies rate
limiting per the source's terms of use, retries on transient failure, and
writes a section-level JSONL into ``vendor-data/<source>/``. Outputs are
consumed by ``backend/ml/pipelines/ingest_*`` for ES + Qdrant indexing
and by ``backend/api/adapters/public/*`` for benchmark dataset builds.
"""
