"""LexisNexis SG adapter — Phase 3 placeholder."""
from __future__ import annotations

from typing import Iterator

from api.adapters.base import (
    AdapterTier,
    LegalSourceAdapter,
    SourceAdapterError,
    SourceDocument,
    SourceMetadata,
)


class LexisNexisSgAdapter(LegalSourceAdapter):
    metadata = SourceMetadata(
        source_id="lexisnexis-sg",
        display_name="LexisNexis Singapore",
        base_url="https://www.lexisnexis.com.sg",
        tier=AdapterTier.USER_CREDENTIALED,
        licence_summary=(
            "LexisNexis SG is a paid subscription service. Access requires "
            "user credentials and an official API tier; session-cookie "
            "scraping is prohibited."
        ),
        licence_url="https://www.lexisnexis.com.sg",
        crawl_delay_seconds=5.0,
        requires_attribution=True,
        benchmark_eligible=False,
    )

    def fetch_all(self) -> Iterator[SourceDocument]:
        raise SourceAdapterError(
            "LexisNexisSgAdapter is a phase-3 placeholder; requires LN API."
        )

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        raise SourceAdapterError(
            "LexisNexisSgAdapter is a phase-3 placeholder; requires LN API."
        )
