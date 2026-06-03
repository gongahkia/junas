"""CommonLII SG section adapter — AustLII-hosted, free."""
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


class CommonliiSgAdapter(LegalSourceAdapter):
    metadata = SourceMetadata(
        source_id="commonlii-sg",
        display_name="CommonLII Singapore",
        base_url="http://www.commonlii.org/sg/",
        tier=AdapterTier.PUBLIC,
        licence_summary=(
            "CommonLII is the open-access common-law legal-information project "
            "hosted by AustLII. Singapore case-law materials are mirrored from "
            "judicial sources. Use under standard free-information terms with "
            "attribution."
        ),
        licence_url="http://www.commonlii.org/copyright.html",
        crawl_delay_seconds=5.0,
        requires_attribution=True,
    )

    doc_type: str = DocType.CASE.value

    extra_schema: dict[str, str] = {
        "citation": "str (neutral or report citation)",
        "court_code": "str (SGCA | SGHC | SGDC etc.)",
        "year": "int",
        "case_no": "int",
        "html_url": "str (canonical CommonLII page)",
    }

    def fetch_all(self) -> Iterator[SourceDocument]:
        raise SourceAdapterError("CommonliiSgAdapter.fetch_all() not implemented")

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        raise SourceAdapterError("CommonliiSgAdapter.fetch_by_id() not implemented")
