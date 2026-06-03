"""Legal source adapters.

Two-tier architecture:

- ``public/``: free, public-domain SG legal sources. Benchmark ingestion
  may use these.
- ``user_credentialed/``: optional copilot-only adapters that require user
  credentials to a paid source. Benchmark ingestion **must not** use these.

See ``base.py`` for the protocol and ``BENCHMARK_ALLOWED_TIERS`` for the
enforced tier filter.
"""

from api.adapters.base import (
    BENCHMARK_ALLOWED_TIERS,
    AdapterTier,
    LegalSourceAdapter,
    SourceDocument,
    SourceMetadata,
    benchmark_safe_adapters,
)

__all__ = [
    "BENCHMARK_ALLOWED_TIERS",
    "AdapterTier",
    "LegalSourceAdapter",
    "SourceDocument",
    "SourceMetadata",
    "benchmark_safe_adapters",
]
