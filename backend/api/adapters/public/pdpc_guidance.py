"""PDPC Advisory Guidelines adapter — public, regulator-published.

Distinct from ``PdpcAdapter`` which covers enforcement decisions. This
adapter covers the Advisory Guidelines on Key Concepts in the PDPA (and
sectoral guidelines), which contain worked examples used as ground truth
for SGLB-14 statutory entailment.
"""
from __future__ import annotations

from typing import Iterator

from api.adapters.base import (
    AdapterTier,
    LegalSourceAdapter,
    SourceAdapterError,
    SourceDocument,
    SourceMetadata,
)


class PdpcGuidanceAdapter(LegalSourceAdapter):
    metadata = SourceMetadata(
        source_id="pdpc-guidance",
        display_name="PDPC Advisory Guidelines",
        base_url="https://www.pdpc.gov.sg/guidelines-and-consultation",
        tier=AdapterTier.PUBLIC,
        licence_summary=(
            "PDPC publishes Advisory Guidelines (Key Concepts in the PDPA, "
            "Selected Topics, sectoral guidelines) as PDFs and HTML on its "
            "public website. Reproduction for analytical purposes is "
            "standard; attribution required."
        ),
        licence_url="https://www.pdpc.gov.sg",
        crawl_delay_seconds=3.0,
        requires_attribution=True,
    )

    def fetch_all(self) -> Iterator[SourceDocument]:
        raise SourceAdapterError("PdpcGuidanceAdapter.fetch_all() not implemented; see #60")

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        raise SourceAdapterError("PdpcGuidanceAdapter.fetch_by_id() not implemented; see #60")
