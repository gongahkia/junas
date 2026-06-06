"""MOM (Ministry of Manpower) adapter — public guidance + press releases.

Bronze schema reference: MOM content splits across enforcement press
releases (mom.gov.sg/newsroom/press-releases), employment-practices FAQs,
and advisories. The adapter normalises each into the same envelope but
preserves source-specific fields on ``extra``.
"""
from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING, Iterator

from api.adapters.base import (
    AdapterTier,
    DocType,
    LegalSourceAdapter,
    SourceAdapterError,
    SourceDocument,
    SourceMetadata,
    normalise_date,
)

if TYPE_CHECKING:
    from data.ingestion.mom import MomRecord


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
        from data.ingestion.mom import iter_records  # noqa: WPS433

        try:
            for record in iter_records():
                yield self._source_document(record)
        except RuntimeError as exc:
            raise SourceAdapterError(f"MOM fetch failed: {exc}") from exc

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        from data.ingestion.mom import iter_records  # noqa: WPS433

        try:
            for record in iter_records():
                if record.doc_id == document_id or record.source_url == document_id:
                    return self._source_document(record)
        except RuntimeError as exc:
            raise SourceAdapterError(f"MOM fetch failed: {exc}") from exc
        return None

    def _source_document(self, record: "MomRecord") -> SourceDocument:
        body = record.raw_html or (record.raw_json and json.dumps(record.raw_json, ensure_ascii=False)) or record.body_plain
        doc_type = DocType.PRESS_RELEASE.value if record.subsource == "press_release" else DocType.GUIDELINE.value
        return SourceDocument(
            document_id=record.doc_id,
            source_url=record.source_url,
            title=record.title,
            body=body or "",
            published_date=normalise_date(record.pub_date),
            fetched_date=date.today(),
            source_metadata=self.metadata,
            doc_type=doc_type,
            extra={
                "subsource": record.subsource,
                "title": record.title,
                "published_date": record.pub_date,
                "act_references": list(record.act_references),
                "stated_breaches": list(record.stated_breaches),
                "penalty_info": None,
                "subject_organisation": record.subject_organisation,
                "candidate_reason": record.candidate_reason,
                "content_type": record.content_type,
            },
        )
