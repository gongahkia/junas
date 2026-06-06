"""MOM (Ministry of Manpower) adapter — public guidance + press releases.

Bronze schema reference: MOM content splits across enforcement press
releases (mom.gov.sg/newsroom/press-releases), employment-practices FAQs,
and advisories. The adapter normalises each into the same envelope but
preserves source-specific fields on ``extra``.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Iterator

from api.adapters.base import (
    AdapterTier,
    DocType,
    LegalSourceAdapter,
    SourceAdapterError,
    SourceDocument,
    SourceMetadata,
    normalise_date,
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
        "doc_id": "str",
        "source_url": "str",
        "subsource": "str (press_release | faq | advisory)",
        "title": "str",
        "body_plain": "str",
        "stated_breaches": "list[str] (mechanical extraction of regulator-stated contraventions)",
        "act_references": "list[str] (e.g. 'Employment Act s.X')",
        "subject_organisation": "str | None (for press releases)",
        "pub_date": "str",
    }

    def __init__(self, *, jsonl_path: Path | str | None = None) -> None:
        default_path = (
            Path(__file__).resolve().parents[3]
            / "vendor-data"
            / "mom"
            / "enforcement.jsonl"
        )
        self.jsonl_path = Path(jsonl_path) if jsonl_path is not None else default_path

    def fetch_all(self) -> Iterator[SourceDocument]:
        if not self.jsonl_path.exists():
            raise SourceAdapterError(
                f"MOM JSONL fixture not found at {self.jsonl_path}; run `make ingest-mom LIVE=1` "
                "or pass MomAdapter(jsonl_path=...)"
            )
        yield from self._records_from_jsonl()

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        for doc in self.fetch_all():
            if doc.document_id == document_id:
                return doc
        return None

    def _records_from_jsonl(self) -> Iterator[SourceDocument]:
        with self.jsonl_path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise SourceAdapterError(
                        f"MOM JSONL fixture row {line_number} invalid at {self.jsonl_path}: {exc}"
                    ) from exc
                if not isinstance(row, dict):
                    raise SourceAdapterError(
                        f"MOM JSONL fixture row {line_number} invalid at {self.jsonl_path}: not an object"
                    )
                yield self._source_document(row, line_number=line_number)

    def _source_document(self, record: dict[str, Any], *, line_number: int) -> SourceDocument:
        missing = [key for key in self.extra_schema if key not in record]
        if missing:
            raise SourceAdapterError(
                f"MOM JSONL fixture row {line_number} missing required keys: {', '.join(missing)}"
            )
        subsource = str(record.get("subsource") or "")
        doc_type = (
            DocType.PRESS_RELEASE.value
            if subsource == "press_release"
            else DocType.GUIDELINE.value
        )
        extra = {key: record.get(key) for key in self.extra_schema}
        return SourceDocument(
            document_id=str(record.get("doc_id") or ""),
            source_url=str(record.get("source_url") or ""),
            title=str(record.get("title") or ""),
            body=str(record.get("body_plain") or ""),
            published_date=normalise_date(record.get("pub_date")),
            fetched_date=date.today(),
            source_metadata=self.metadata,
            doc_type=doc_type,
            extra=extra,
        )
