"""PDPC enforcement decisions adapter — public, regulator-published.

Bronze schema reference: PDPC content is heterogeneous; the spider yields
items differentiated by ``resource_type``. For SGLB-01 (PDPA-Outcome) the
adapter focuses on ``resource_type == "decision"``; ``undertaking`` rows
are an adjacent enforcement form and can feed counterfactual tasks.
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


class PdpcAdapter(LegalSourceAdapter):
    metadata = SourceMetadata(
        source_id="pdpc-enforcement",
        display_name="PDPC Enforcement Decisions",
        base_url="https://www.pdpc.gov.sg/enforcement-decisions",
        tier=AdapterTier.PUBLIC,
        licence_summary=(
            "PDPC publishes enforcement decisions on its public website as "
            "regulator guidance. Reproduction for analytical and educational "
            "purposes is standard; attribution required."
        ),
        licence_url="https://www.pdpc.gov.sg",
        crawl_delay_seconds=3.0,
        requires_attribution=True,
    )

    doc_type: str = DocType.ENFORCEMENT_DECISION.value

    extra_schema: dict[str, str] = {
        "resource_type": "str (decision | undertaking | guideline | help_and_resources)",
        "decision_title": "str (for resource_type=decision)",
        "dp_obligations": "list[str] (PDPC obligation tags as published)",
        "decision": "str (PDPC outcome verbiage)",
        "pub_date": "str (publication date in PDPC's format)",
        "blurb": "str | None",
        "tags": "list[str]",
        "file_urls": "list[str] (PDF attachments)",
    }

    def fetch_all(self) -> Iterator[SourceDocument]:
        raise SourceAdapterError("PdpcAdapter.fetch_all() not implemented; see #27")

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        raise SourceAdapterError("PdpcAdapter.fetch_by_id() not implemented; see #27")
