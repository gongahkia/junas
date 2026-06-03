"""SSO (Singapore Statutes Online) adapter — public, AGC-published."""
from __future__ import annotations

from typing import Iterator

from api.adapters.base import (
    AdapterTier,
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

    def fetch_all(self) -> Iterator[SourceDocument]:
        # Implementation lives in #28 (SSO statute ingestion). Stubbed at
        # scaffold time; raising rather than returning empty so silent
        # benchmark builds against a non-implemented adapter are impossible.
        raise SourceAdapterError("SsoAdapter.fetch_all() not implemented; see #28")

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        raise SourceAdapterError("SsoAdapter.fetch_by_id() not implemented; see #28")
