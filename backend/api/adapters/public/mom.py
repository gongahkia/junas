"""MOM (Ministry of Manpower) adapter — public guidance + press releases."""
from __future__ import annotations

from typing import Iterator

from api.adapters.base import (
    AdapterTier,
    LegalSourceAdapter,
    SourceAdapterError,
    SourceDocument,
    SourceMetadata,
)


class MomAdapter(LegalSourceAdapter):
    metadata = SourceMetadata(
        source_id="mom",
        display_name="Ministry of Manpower (Singapore)",
        base_url="https://www.mom.gov.sg",
        tier=AdapterTier.PUBLIC,
        licence_summary=(
            "MOM publishes employment-practices guidance, FAQs, advisories, "
            "and enforcement press releases on its public website. Government "
            "publication; reproduction for analytical purposes is standard "
            "with attribution."
        ),
        licence_url="https://www.mom.gov.sg",
        crawl_delay_seconds=3.0,
        requires_attribution=True,
    )

    def fetch_all(self) -> Iterator[SourceDocument]:
        raise SourceAdapterError("MomAdapter.fetch_all() not implemented; see #59")

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        raise SourceAdapterError("MomAdapter.fetch_by_id() not implemented; see #59")
