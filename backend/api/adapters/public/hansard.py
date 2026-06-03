"""Singapore Parliament Hansard adapter — public debates.

Bronze schema reference: hansard items are JSON topic payloads from the
sprs API. Each topic carries reportType, sittingDate, and content. The
adapter preserves the JSON payload on ``extra.payload`` so downstream
consumers can apply their own structure (e.g. per-speaker snapshots).
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


class HansardAdapter(LegalSourceAdapter):
    metadata = SourceMetadata(
        source_id="hansard-sg",
        display_name="Singapore Parliament Hansard",
        base_url="https://sprs.parl.gov.sg",
        tier=AdapterTier.PUBLIC,
        licence_summary=(
            "Singapore Parliament Reports (Hansard) are publicly accessible at "
            "sprs.parl.gov.sg. Reproduction for analytical purposes is "
            "standard; attribution required."
        ),
        licence_url="https://sprs.parl.gov.sg",
        crawl_delay_seconds=3.0,
        requires_attribution=True,
        # Hansard-grounded benchmark task deferred to v0.3 per
        # coverage-matrix.md §7.
        benchmark_eligible=False,
    )

    doc_type: str = DocType.HANSARD_TOPIC.value

    extra_schema: dict[str, str] = {
        "topic_id": "str",
        "topic_version": "str",
        "report_type": "str",
        "sitting_date": "str",
        "payload": "dict (raw sprs topic JSON)",
    }

    def fetch_all(self) -> Iterator[SourceDocument]:
        raise SourceAdapterError("HansardAdapter.fetch_all() deferred to v0.3")

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        raise SourceAdapterError("HansardAdapter.fetch_by_id() deferred to v0.3")
