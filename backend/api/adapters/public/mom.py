"""MOM (Ministry of Manpower) adapter — public guidance + press releases.

Bronze schema reference: MOM content splits across enforcement press
releases (mom.gov.sg/newsroom/press-releases), employment-practices FAQs,
and advisories. The adapter normalises each into the same envelope but
preserves source-specific fields on ``extra``.
"""
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

    # MOM yields multiple doc_types depending on the page. Adapters emit
    # the more specific value on each SourceDocument; this default reflects
    # the bulk of items.
    doc_type: str = DocType.GUIDELINE.value

    extra_schema: dict[str, str] = {
        "subsource": "str (press_release | faq | advisory)",
        "title": "str",
        "published_date": "str",
        "act_references": "list[str] (e.g. 'Employment Act s.X')",
        "stated_breaches": "list[str] (mechanical extraction of regulator-stated contraventions)",
        "penalty_info": "str | None",
        "subject_organisation": "str | None (for press releases)",
    }

    def fetch_all(self) -> Iterator[SourceDocument]:
        raise SourceAdapterError("MomAdapter.fetch_all() not implemented; see #59")

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        raise SourceAdapterError("MomAdapter.fetch_by_id() not implemented; see #59")
