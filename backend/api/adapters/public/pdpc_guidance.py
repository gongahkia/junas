"""PDPC Advisory Guidelines adapter — public, regulator-published.

Distinct from ``PdpcAdapter`` which covers enforcement decisions. This
adapter covers the Advisory Guidelines on Key Concepts in the PDPA (and
sectoral guidelines), which contain worked examples used as ground truth
for SGLB-14 statutory entailment.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterator, Sequence

from api.adapters.base import (
    AdapterTier,
    DocType,
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

    doc_type: str = DocType.GUIDELINE.value

    extra_schema: dict[str, str] = {
        "category": "str (Advisory Guidelines)",
        "title": "str",
        "pdf_url": "str",
        "section_headings": "list[str]",
        "body_plain_chars": "int",
        "file_urls": "list[str] (PDF urls — primary content lives here)",
        "other_urls": "list[str]",
        "extracted_worked_examples": "list[{scenario, statute_section, label}]",
    }

    def __init__(
        self,
        *,
        jsonl_path: Path | None = None,
        source_urls: Sequence[str] | None = None,
    ) -> None:
        from data.ingestion import pdpc_guidelines  # noqa: WPS433

        self.jsonl_path = jsonl_path or pdpc_guidelines.DEFAULT_OUTPUT
        self.source_urls = tuple(source_urls or pdpc_guidelines.DEFAULT_SOURCE_URLS)

    def fetch_all(self) -> Iterator[SourceDocument]:
        from data.ingestion import pdpc_guidelines  # noqa: WPS433

        try:
            if not self.jsonl_path.exists():
                pdpc_guidelines.ingest(output_path=self.jsonl_path, source_urls=self.source_urls)
            for row in pdpc_guidelines.load_jsonl(self.jsonl_path):
                yield _row_to_document(row, self.metadata)
        except RuntimeError as exc:
            raise SourceAdapterError(f"PDPC guidance fetch failed: {exc}") from exc

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        for doc in self.fetch_all():
            if doc.document_id == document_id:
                return doc
        return None


def _row_to_document(row: dict[str, object], metadata: SourceMetadata) -> SourceDocument:
    from data.ingestion.pdpc_guidelines import parse_pub_date  # noqa: WPS433

    body = str(row.get("body_plain") or "")
    pdf_url = str(row.get("pdf_url") or "")
    title = str(row.get("title") or "")
    section_headings = row.get("section_headings") or []
    if not isinstance(section_headings, list):
        section_headings = []
    return SourceDocument(
        document_id=str(row.get("doc_id") or ""),
        source_url=str(row.get("source_url") or pdf_url),
        title=title,
        body=body,
        published_date=parse_pub_date(str(row.get("pub_date") or "")),
        fetched_date=date.today(),
        source_metadata=metadata,
        doc_type=DocType.GUIDELINE.value,
        extra={
            "category": "Advisory Guidelines",
            "title": title,
            "pdf_url": pdf_url,
            "section_headings": section_headings,
            "body_plain_chars": len(body),
            "file_urls": [pdf_url] if pdf_url else [],
            "other_urls": [],
            "extracted_worked_examples": [],
        },
    )
