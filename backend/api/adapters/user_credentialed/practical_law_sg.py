"""Practical Law SG adapter — Phase 3 placeholder."""
from __future__ import annotations

from typing import Iterator

from api.adapters.base import (
    AdapterTier,
    DocType,
    LegalSourceAdapter,
    SourceAdapterError,
    SourceDocument,
    SourceMetadata,
)


class PracticalLawSgAdapter(LegalSourceAdapter):
    doc_type: str = DocType.GUIDELINE.value
    extra_schema: dict[str, str] = {}

    metadata = SourceMetadata(
        source_id="practical-law-sg",
        display_name="Practical Law Singapore (Thomson Reuters)",
        base_url="https://uk.practicallaw.thomsonreuters.com",
        tier=AdapterTier.USER_CREDENTIALED,
        licence_summary=(
            "Practical Law SG is a Thomson Reuters paid subscription. Access "
            "requires user credentials and an official API tier; "
            "session-cookie scraping is prohibited."
        ),
        licence_url="https://uk.practicallaw.thomsonreuters.com",
        crawl_delay_seconds=5.0,
        requires_attribution=True,
        benchmark_eligible=False,
    )

    def fetch_all(self) -> Iterator[SourceDocument]:
        raise SourceAdapterError(
            "PracticalLawSgAdapter is a phase-3 placeholder; requires TR API."
        )

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        raise SourceAdapterError(
            "PracticalLawSgAdapter is a phase-3 placeholder; requires TR API."
        )
