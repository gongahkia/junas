"""LegalSourceAdapter protocol + provenance dataclasses.

Two-tier architecture:

- ``AdapterTier.PUBLIC``: free, public-domain SG legal sources. Benchmark
  datasets may include items obtained from these adapters.
- ``AdapterTier.USER_CREDENTIALED``: optional copilot-only adapters that
  require user credentials for a paid source. Benchmark datasets must not
  include items obtained from these adapters.

The ``benchmark_safe_adapters()`` filter is the enforcement point: any
ingestion pipeline that produces benchmark datasets must route through it.

Envelope alignment: ``SourceDocument`` carries the same core envelope
fields used by adjacent SG legal-AI ingestion pipelines — ``legis_id``
(stable per-document identifier slug), ``country``, ``doc_type``,
``sort_date``, ``year`` — so a junas-scraped corpus can be loaded into
the same downstream tooling without re-mapping. Per-source schema
variation lives on ``extra``.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Iterable, Iterator, Protocol, runtime_checkable


class AdapterTier(str, Enum):
    PUBLIC = "public"
    USER_CREDENTIALED = "user_credentialed"


BENCHMARK_ALLOWED_TIERS: frozenset[AdapterTier] = frozenset({AdapterTier.PUBLIC})


# Canonical doc_type values aligned to the SG bronze envelope downstream
# loaders normalise into. Per-adapter constants picked from this set.
class DocType(str, Enum):
    CASE = "case"
    LEGISLATION = "legislation"
    SUBSIDIARY_LEGISLATION = "subsidiary_legislation"
    ENFORCEMENT_DECISION = "enforcement_decision"
    UNDERTAKING = "undertaking"
    GUIDELINE = "guideline"
    PRESS_RELEASE = "press_release"
    HANSARD_TOPIC = "hansard_topic"
    GAZETTE_NOTICE = "gazette_notice"
    REGULATORY_NOTICE = "regulatory_notice"


@dataclass(frozen=True)
class SourceMetadata:
    """Static metadata about an adapter's source.

    Per-document fields go on ``SourceDocument.extra`` so the per-source
    description stays stable across runs.
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
    country: str = "SG"


_RE_NON_WORD_COLON_DASH = re.compile(r"[^\w:\-]+")
_RE_MULTI_DASH = re.compile(r"-{2,}")


def _slugify(value: str) -> str:
    """Conservative slugifier used for stable identifier derivation."""
    cleaned = _RE_NON_WORD_COLON_DASH.sub("-", str(value or "").strip())
    cleaned = _RE_MULTI_DASH.sub("-", cleaned).strip("-_")
    return cleaned.lower()


def derive_legis_id(
    *,
    country: str,
    doc_type: str,
    raw_identifier: str = "",
    title: str = "",
    extra: dict[str, Any] | None = None,
) -> str:
    """Derive a stable per-document identifier.

    Resolution order:

    1. ``raw_identifier`` if non-empty and not "unknown".
    2. ``title`` slug, prefixed with ``country-doc_type-``.
    3. Hash fallback over the sorted ``extra`` dict.

    Mirrors the envelope rule used by adjacent SG legal ingestion
    pipelines so junas-scraped corpora are drop-in compatible.
    """
    if raw_identifier and "unknown" not in raw_identifier.lower():
        return _slugify(raw_identifier)

    slug = _slugify(title)
    if slug:
        return f"{country.lower()}-{doc_type.lower()}-{slug}"

    blob = repr(sorted((extra or {}).items())).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()[:16]
    return f"{country.lower()}-{doc_type.lower()}-{digest}"


def normalise_date(value: Any) -> date | None:
    """Best-effort date parser. Accepts ``date``, ``datetime``, ``YYYY-MM-DD``
    strings, ISO datetimes, common SG date formats, and unix timestamps in
    seconds or milliseconds.
    """
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)):
        ts = float(value)
        # ms → s heuristic: > year 2100 in seconds
        if ts > 4_102_444_800:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts).date()
        except (ValueError, OSError, OverflowError):
            return None
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        # Already ISO?
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        except ValueError:
            pass
        for fmt in (
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%B %d, %Y",
            "%d %b %Y",
            "%d %B %Y",
        ):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
    return None


@dataclass
class SourceDocument:
    """A single document retrieved from a source.

    ``provenance`` carries the audit record that must accompany every
    benchmark instance: source_id, source_url, document_id, dates,
    licence summary, tier.

    Envelope fields (``legis_id``, ``country``, ``doc_type``,
    ``sort_date``, ``year``) mirror the loader contract adjacent SG legal
    ingestion pipelines normalise into. Adapters set them at fetch time;
    benchmark dataset builders read them.
    """

    document_id: str  # stable per source (URL-keyed or content-hashed)
    source_url: str
    title: str
    body: str
    published_date: date | None
    fetched_date: date
    source_metadata: SourceMetadata
    doc_type: str = ""  # canonical doc_type; see DocType enum
    legis_id: str = ""  # derived via derive_legis_id() when blank
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.legis_id:
            self.legis_id = derive_legis_id(
                country=self.source_metadata.country,
                doc_type=self.doc_type or self.source_metadata.source_id,
                raw_identifier=self.document_id,
                title=self.title,
                extra=self.extra,
            )

    @property
    def country(self) -> str:
        return self.source_metadata.country

    @property
    def sort_date(self) -> str | None:
        d = self.published_date or self.fetched_date
        return d.isoformat() if d else None

    @property
    def year(self) -> int | None:
        d = self.published_date or self.fetched_date
        return d.year if d else None

    @property
    def provenance(self) -> dict[str, Any]:
        return {
            "source_id": self.source_metadata.source_id,
            "source_url": self.source_url,
            "document_id": self.document_id,
            "legis_id": self.legis_id,
            "doc_type": self.doc_type,
            "country": self.country,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "fetched_date": self.fetched_date.isoformat(),
            "sort_date": self.sort_date,
            "year": self.year,
            "licence_summary": self.source_metadata.licence_summary,
            "tier": self.source_metadata.tier.value,
        }


@runtime_checkable
class LegalSourceAdapter(Protocol):
    """Protocol for a public or credentialed legal source adapter.

    Implementations must:

    - expose ``metadata`` as a class-level constant or property,
    - declare ``doc_type`` for the canonical document kind they produce,
    - declare an ``extra_schema`` (a frozen dict of field-name → type
      string) documenting the per-source ``extra`` fields,
    - yield ``SourceDocument`` items from ``fetch_all()`` /
      ``fetch_by_id()``,
    - record provenance on every emitted document,
    - be re-runnable: identifier-keyed dedupe is the caller's concern.
    """

    metadata: SourceMetadata
    doc_type: str
    extra_schema: dict[str, str]

    def fetch_all(self) -> Iterator[SourceDocument]:
        """Yield all documents the adapter can produce.

        Implementations may stream rather than materialise. Network errors
        should be raised as ``SourceAdapterError`` so callers can decide
        whether to retry, fall back, or abort.
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
