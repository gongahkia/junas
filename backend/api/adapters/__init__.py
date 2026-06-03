"""Legal source adapters.

Two-tier architecture:

- ``public/``: free, public-domain SG legal sources. Benchmark ingestion
  may use these.
- ``user_credentialed/``: optional copilot-only adapters that require user
  credentials to a paid source. Benchmark ingestion **must not** use these.

See ``base.py`` for the protocol and ``BENCHMARK_ALLOWED_TIERS`` for the
enforced tier filter. See ``base.py`` ``DocType`` for canonical doc_type
values aligned to adjacent SG legal ingestion envelopes.
"""

from api.adapters.base import (
    BENCHMARK_ALLOWED_TIERS,
    AdapterTier,
    DocType,
    LegalSourceAdapter,
    SourceAdapterError,
    SourceDocument,
    SourceMetadata,
    benchmark_safe_adapters,
    derive_legis_id,
    normalise_date,
)

__all__ = [
    "BENCHMARK_ALLOWED_TIERS",
    "AdapterTier",
    "DocType",
    "LegalSourceAdapter",
    "SourceAdapterError",
    "SourceDocument",
    "SourceMetadata",
    "benchmark_safe_adapters",
    "derive_legis_id",
    "normalise_date",
]
