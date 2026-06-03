"""LawNet adapter — Phase 3 placeholder (official-API access required)."""
from __future__ import annotations

from typing import Iterator

from api.adapters.base import (
    AdapterTier,
    LegalSourceAdapter,
    SourceAdapterError,
    SourceDocument,
    SourceMetadata,
)


class LawnetAdapter(LegalSourceAdapter):
    metadata = SourceMetadata(
        source_id="lawnet",
        display_name="LawNet (Singapore Academy of Law)",
        base_url="https://www.lawnet.sg",
        tier=AdapterTier.USER_CREDENTIALED,
        licence_summary=(
            "LawNet is a SAL paid subscription service. Access requires user "
            "credentials and must go through SAL's official partner/API "
            "programme. Session-cookie scraping is prohibited."
        ),
        licence_url="https://www.lawnet.sg",
        crawl_delay_seconds=5.0,
        requires_attribution=True,
        benchmark_eligible=False,
    )

    def fetch_all(self) -> Iterator[SourceDocument]:
        raise SourceAdapterError(
            "LawnetAdapter is a phase-3 placeholder; requires SAL partner API."
        )

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        raise SourceAdapterError(
            "LawnetAdapter is a phase-3 placeholder; requires SAL partner API."
        )
