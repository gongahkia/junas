"""IRAS (Inland Revenue Authority of Singapore) adapter — e-Tax guides."""
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


class IrasAdapter(LegalSourceAdapter):
    metadata = SourceMetadata(
        source_id="iras",
        display_name="Inland Revenue Authority of Singapore",
        base_url="https://www.iras.gov.sg",
        tier=AdapterTier.PUBLIC,
        licence_summary=(
            "IRAS publishes e-Tax Guides, advance rulings (redacted summaries), "
            "and FAQs on its public website. Government publication; "
            "attribution required."
        ),
        licence_url="https://www.iras.gov.sg",
        crawl_delay_seconds=3.0,
        requires_attribution=True,
        # IRAS coverage deferred to v0.3 per coverage-matrix.md §7.
        benchmark_eligible=False,
    )

    doc_type: str = DocType.GUIDELINE.value

    extra_schema: dict[str, str] = {
        "guide_category": "str",
        "title": "str",
        "tax_topic": "str",
        "file_urls": "list[str]",
    }

    def fetch_all(self) -> Iterator[SourceDocument]:
        raise SourceAdapterError("IrasAdapter.fetch_all() deferred to v0.3")

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        raise SourceAdapterError("IrasAdapter.fetch_by_id() deferred to v0.3")
