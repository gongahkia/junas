"""AustLII Singapore section adapter — free access."""
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


class AustliiSgAdapter(LegalSourceAdapter):
    metadata = SourceMetadata(
        source_id="austlii-sg",
        display_name="AustLII Singapore",
        base_url="http://www.austlii.edu.au/databases.html#SG",
        tier=AdapterTier.PUBLIC,
        licence_summary=(
            "AustLII publishes Singapore legal materials under the standard "
            "AustLII free-access policy. Attribution required; bulk crawling "
            "subject to AustLII's published acceptable-use terms."
        ),
        licence_url="http://www.austlii.edu.au/austlii/copyright.html",
        crawl_delay_seconds=5.0,
        requires_attribution=True,
    )

    doc_type: str = DocType.CASE.value

    extra_schema: dict[str, str] = {
        "citation": "str",
        "court_code": "str",
        "year": "int",
        "case_no": "int",
        "html_url": "str",
    }

    def fetch_all(self) -> Iterator[SourceDocument]:
        raise SourceAdapterError("AustliiSgAdapter.fetch_all() not implemented")

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        raise SourceAdapterError("AustliiSgAdapter.fetch_by_id() not implemented")
