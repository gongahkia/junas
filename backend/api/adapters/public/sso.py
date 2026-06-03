"""SSO (Singapore Statutes Online) adapter — public, AGC-published.

Bronze schema reference: an SSO Act/SL instrument observed in practice
yields a record keyed by ``unique_id = "{doc_no}-{validStartDate}"`` with
fields drawn from the SSO `data-json` blob. The fragment HTML is base64
+ zlib compressed to keep row sizes manageable on big Acts.
"""
from __future__ import annotations

from typing import Any, Iterator

from api.adapters.base import (
    AdapterTier,
    DocType,
    LegalSourceAdapter,
    SourceAdapterError,
    SourceDocument,
    SourceMetadata,
)


class SsoAdapter(LegalSourceAdapter):
    metadata = SourceMetadata(
        source_id="sso",
        display_name="Singapore Statutes Online",
        base_url="https://sso.agc.gov.sg",
        tier=AdapterTier.PUBLIC,
        licence_summary=(
            "AGC has granted permission to users of SSO to use/reproduce any "
            "Singapore legislation for the purposes of any print or electronic "
            "material or platform, subject to the SSO Terms of Use. SSO "
            "consolidates unofficial versions; the official text remains the "
            "Government Gazette."
        ),
        licence_url="https://sso.agc.gov.sg/Terms-of-Use",
        crawl_delay_seconds=3.0,
        requires_attribution=True,
    )

    doc_type: str = DocType.LEGISLATION.value

    # Field shapes that adapter implementations should populate in
    # SourceDocument.extra. Mirrors the SSO bronze envelope so a junas
    # corpus is drop-in compatible with adjacent downstream tooling.
    extra_schema: dict[str, str] = {
        "unique_id": "str ({doc_no}-{validStartDate})",
        "doc_no": "str",
        "valid_start_date": "int (unix seconds)",
        "legis_title": "str",
        "doc_status": "str",
        "law_type": "str (act | sl)",
        "law_status": "str (current | historical)",
        "entry_act_title": "str",
        "entry_act_url": "str",
        "timeline": "list[dict] (revision timeline entries)",
        "fragments_content": "dict | None (base64+zlib-compressed HTML)",
        "data_json": "dict (raw SSO data-json blob)",
    }

    def fetch_all(self) -> Iterator[SourceDocument]:
        raise SourceAdapterError("SsoAdapter.fetch_all() not implemented; see #28")

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        raise SourceAdapterError("SsoAdapter.fetch_by_id() not implemented; see #28")
