"""SSO (Singapore Statutes Online) adapter — public, AGC-published.

Bronze schema reference: an SSO Act/SL instrument observed in practice
yields a record keyed by ``unique_id = "{doc_no}-{validStartDate}"`` with
fields drawn from the SSO `data-json` blob. The fragment HTML is base64
+ zlib compressed to keep row sizes manageable on big Acts.

This adapter delegates the actual HTML fetch + parse to
``backend.data.ingestion.sso``; the adapter layer adds the bronze envelope
(``SourceDocument`` + provenance) that benchmark dataset builders expect.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterator

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
        # imported lazily to keep adapter import cheap when offline
        from data.ingestion.sso import ACT_CODES, ingest_act  # noqa: WPS433

        try:
            import httpx  # noqa: F401  # sanity check; ingest_act raises otherwise
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise SourceAdapterError("httpx not installed; cannot fetch SSO") from exc

        fetched_today = date.today()
        for code, kind, path_template in ACT_CODES:
            try:
                act = ingest_act(code, kind=kind, path_template=path_template)
            except RuntimeError as exc:
                raise SourceAdapterError(f"SSO fetch failed for {code}: {exc}") from exc
            for section in act.sections:
                yield SourceDocument(
                    document_id=f"{section.version_id}:{section.number}",
                    source_url=section.source_url,
                    title=f"{section.act_title}, s {section.number} ({section.name})",
                    body=section.text_plain,
                    published_date=_parse_iso(section.valid_start_date),
                    fetched_date=fetched_today,
                    source_metadata=self.metadata,
                    doc_type=DocType.LEGISLATION.value if section.kind == "act" else DocType.SUBSIDIARY_LEGISLATION.value,
                    extra={
                        "unique_id": f"{section.chapter_number}-{section.valid_start_date}",
                        "doc_no": section.chapter_number,
                        "valid_start_date": section.valid_start_date,
                        "legis_title": section.act_title,
                        "law_type": "act" if section.kind == "act" else "sl",
                        "law_status": "current",
                        "part": section.part,
                        "division": section.division,
                        "section_number": section.number,
                        "section_name": section.name,
                        "amendment_history": section.amendment_history,
                        "cross_references": section.cross_references,
                        "version_id": section.version_id,
                        "text_html": section.text_html,
                    },
                )

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        # document_id is "<version_id>:<number>". Re-fetch the whole act
        # and filter; SSO has no per-section endpoint.
        if ":" not in document_id:
            return None
        version_id, _, section_number = document_id.rpartition(":")
        chapter_number = version_id.split("@", 1)[0]
        from data.ingestion.sso import ACT_CODES, ingest_act  # noqa: WPS433

        kind = "act"
        path_template = "/Act/{code}?WholeDoc=1"
        for code, k, tpl in ACT_CODES:
            if code == chapter_number:
                kind, path_template = k, tpl
                break
        try:
            act = ingest_act(chapter_number, kind=kind, path_template=path_template)
        except RuntimeError as exc:
            raise SourceAdapterError(str(exc)) from exc
        for section in act.sections:
            if section.number == section_number:
                fetched_today = date.today()
                return SourceDocument(
                    document_id=document_id,
                    source_url=section.source_url,
                    title=f"{section.act_title}, s {section.number} ({section.name})",
                    body=section.text_plain,
                    published_date=_parse_iso(section.valid_start_date),
                    fetched_date=fetched_today,
                    source_metadata=self.metadata,
                    doc_type=DocType.LEGISLATION.value if section.kind == "act" else DocType.SUBSIDIARY_LEGISLATION.value,
                    extra={"version_id": section.version_id, "section_number": section.number},
                )
        return None


def _parse_iso(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
