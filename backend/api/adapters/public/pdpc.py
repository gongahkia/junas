"""PDPC enforcement decisions adapter — public, regulator-published."""
from __future__ import annotations

from typing import Iterator

from api.adapters.base import (
    AdapterTier,
    LegalSourceAdapter,
    SourceAdapterError,
    SourceDocument,
    SourceMetadata,
)


class PdpcAdapter(LegalSourceAdapter):
    metadata = SourceMetadata(
        source_id="pdpc-enforcement",
        display_name="PDPC Enforcement Decisions",
        base_url="https://www.pdpc.gov.sg/enforcement-decisions",
        tier=AdapterTier.PUBLIC,
        licence_summary=(
            "PDPC publishes enforcement decisions on its public website as "
            "regulator guidance. Reproduction for analytical and educational "
            "purposes is standard; attribution required."
        ),
        licence_url="https://www.pdpc.gov.sg",
        crawl_delay_seconds=3.0,
        requires_attribution=True,
    )

    def fetch_all(self) -> Iterator[SourceDocument]:
        raise SourceAdapterError("PdpcAdapter.fetch_all() not implemented; see #27")

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        raise SourceAdapterError("PdpcAdapter.fetch_by_id() not implemented; see #27")
