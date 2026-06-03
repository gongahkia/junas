"""LegalSourceAdapter protocol + provenance dataclasses.

Two-tier architecture:

- ``AdapterTier.PUBLIC``: free, public-domain SG legal sources. Benchmark
  datasets may include items obtained from these adapters.
- ``AdapterTier.USER_CREDENTIALED``: optional copilot-only adapters that
  require user credentials for a paid source. Benchmark datasets must not
  include items obtained from these adapters.

The ``benchmark_safe_adapters()`` filter is the enforcement point: any
ingestion pipeline that produces benchmark datasets must route through it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Iterable, Iterator, Protocol, runtime_checkable


class AdapterTier(str, Enum):
    PUBLIC = "public"
    USER_CREDENTIALED = "user_credentialed"


BENCHMARK_ALLOWED_TIERS: frozenset[AdapterTier] = frozenset({AdapterTier.PUBLIC})


@dataclass(frozen=True)
class SourceMetadata:
    """Static metadata about an adapter's source.

    Attributes are deliberately small. Per-document fields go on
    ``SourceDocument.metadata`` so the per-source description stays stable
    across runs.
    """

    source_id: str  # stable slug, e.g. "sso", "pdpc-enforcement"
    display_name: str  # human-readable, e.g. "Singapore Statutes Online"
    base_url: str
    tier: AdapterTier
    licence_summary: str
    licence_url: str | None = None
    crawl_delay_seconds: float = 3.0
    requires_attribution: bool = True
    benchmark_eligible: bool = True  # may be overridden to False at runtime


@dataclass
class SourceDocument:
    """A single document retrieved from a source.

    The ``source_url`` and ``source_metadata`` together form the provenance
    record that must accompany every benchmark instance.
    """

    document_id: str  # stable per source (URL-keyed or content-hashed)
    source_url: str
    title: str
    body: str
    published_date: date | None
    fetched_date: date
    source_metadata: SourceMetadata
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def provenance(self) -> dict[str, Any]:
        return {
            "source_id": self.source_metadata.source_id,
            "source_url": self.source_url,
            "document_id": self.document_id,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "fetched_date": self.fetched_date.isoformat(),
            "licence_summary": self.source_metadata.licence_summary,
            "tier": self.source_metadata.tier.value,
        }


@runtime_checkable
class LegalSourceAdapter(Protocol):
    """Protocol for a public or credentialed legal source adapter.

    Implementations must:

    - expose ``metadata`` as a class-level constant or property,
    - yield ``SourceDocument`` items from ``fetch_all()`` / ``fetch_by_id()``,
    - record provenance on every emitted document,
    - be re-runnable: identifier-keyed dedupe is the caller's concern.
    """

    metadata: SourceMetadata

    def fetch_all(self) -> Iterator[SourceDocument]:
        """Yield all documents the adapter can produce.

        Implementations may stream rather than materialise, since corpora may
        be large. Network errors should be raised as ``SourceAdapterError``
        so callers can decide whether to retry, fall back, or abort.
        """
        ...

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        """Fetch a single document by its stable identifier."""
        ...


class SourceAdapterError(RuntimeError):
    """Raised when an adapter cannot complete a fetch operation."""


def benchmark_safe_adapters(adapters: Iterable[LegalSourceAdapter]) -> list[LegalSourceAdapter]:
    """Filter adapters down to the set eligible for benchmark dataset
    construction.

    An adapter is included iff:

    1. its tier is in ``BENCHMARK_ALLOWED_TIERS`` (PUBLIC), and
    2. its ``metadata.benchmark_eligible`` flag is True.

    Benchmark ingestion pipelines must call this filter before producing
    any dataset row. Bypassing this filter is a methodology violation.
    """
    return [
        adapter
        for adapter in adapters
        if adapter.metadata.tier in BENCHMARK_ALLOWED_TIERS
        and adapter.metadata.benchmark_eligible
    ]
