"""Adapter primitives for public and credentialed legal-source integrations."""

from sglb_tools.adapters.base import (
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
