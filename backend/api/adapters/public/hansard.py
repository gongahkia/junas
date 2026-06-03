"""Singapore Parliament Hansard adapter — public debates."""
from __future__ import annotations

from typing import Iterator

from api.adapters.base import (
    AdapterTier,
    LegalSourceAdapter,
    SourceAdapterError,
    SourceDocument,
    SourceMetadata,
)


class HansardAdapter(LegalSourceAdapter):
    metadata = SourceMetadata(
        source_id="hansard-sg",
        display_name="Singapore Parliament Hansard",
        base_url="https://sprs.parl.gov.sg",
        tier=AdapterTier.PUBLIC,
        licence_summary=(
            "Singapore Parliament Reports (Hansard) are publicly accessible at "
            "sprs.parl.gov.sg. Reproduction for analytical purposes is "
            "standard; attribution required."
        ),
        licence_url="https://sprs.parl.gov.sg",
        crawl_delay_seconds=3.0,
        requires_attribution=True,
        # Hansard-grounded benchmark task deferred to v0.3 per
        # coverage-matrix.md §7.
        benchmark_eligible=False,
    )

    def fetch_all(self) -> Iterator[SourceDocument]:
        raise SourceAdapterError("HansardAdapter.fetch_all() deferred to v0.3")

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        raise SourceAdapterError("HansardAdapter.fetch_by_id() deferred to v0.3")
