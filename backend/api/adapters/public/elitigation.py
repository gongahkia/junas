"""eLitigation public judgments adapter — TOS-gated per #34."""
from __future__ import annotations

from typing import Iterator

from api.adapters.base import (
    AdapterTier,
    LegalSourceAdapter,
    SourceAdapterError,
    SourceDocument,
    SourceMetadata,
)


class ElitigationAdapter(LegalSourceAdapter):
    metadata = SourceMetadata(
        source_id="elitigation-gd",
        display_name="eLitigation General Division (public judgments)",
        base_url="https://www.elitigation.sg/gd/",
        tier=AdapterTier.PUBLIC,
        licence_summary=(
            "Public judgments handed down by the Singapore Supreme Court are "
            "accessible via the eLitigation gd/ endpoint without login. The "
            "platform's terms of use must be reviewed before bulk ingestion; "
            "see #34 for the TOS pass and the CommonLII-only fallback path."
        ),
        licence_url="https://www.elitigation.sg/",
        crawl_delay_seconds=5.0,
        requires_attribution=True,
        # Conservative default until #34 TOS pass clears the source.
        benchmark_eligible=False,
    )

    def fetch_all(self) -> Iterator[SourceDocument]:
        raise SourceAdapterError(
            "ElitigationAdapter.fetch_all() gated; complete TOS pass in #34 first"
        )

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        raise SourceAdapterError(
            "ElitigationAdapter.fetch_by_id() gated; complete TOS pass in #34 first"
        )
