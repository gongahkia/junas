"""CommonLII SG case adapter — AustLII-hosted, free.

The B1 ingester owns CommonLII crawling and writes raw judgment rows to
JSONL. This adapter only materialises that ingester output into the
``SourceDocument`` envelope required by ``LegalSourceAdapter`` callers.
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
        "case_id": "str (stable CommonLII URL hash)",
        "citation": "str (neutral or report citation)",
        "court_code": "str (SGCA | SGHC | SGDC etc.)",
        "year": "int",
        "case_no": "int",
        "decision_date": "str (YYYY-MM-DD or empty)",
        "source_url": "str (canonical CommonLII page)",
        "html_url": "str (canonical CommonLII page)",
        "body_html": "str (raw CommonLII judgment HTML)",
        "body_plain": "str (parser-normalised judgment text; may be empty before B2)",
        "jurisdiction_statements": "list[dict] (parser-enriched; optional)",
        "question": "str (parser-enriched; optional)",
        "catchwords": "str (parser-enriched; optional)",
        "extraction_rule_sha": "str",
    }

    def __init__(
        self,
        output_path: Path | str | None = None,
        *,
        court: str | None = None,
        year: int | None = None,
        limit: int | None = None,
        force: bool = False,
    ) -> None:
        self.output_path = Path(output_path) if output_path is not None else None
        self.court = court
        self.year = year
        self.limit = limit
        self.force = force

    def fetch_all(self) -> Iterator[SourceDocument]:
        output_path = self._ensure_ingested()
        for row in self._read_rows(output_path):
            yield self._row_to_document(row)

    def fetch_by_id(self, document_id: str) -> SourceDocument | None:
        needle = document_id.strip()
        if not needle:
            return None
        output_path = self._ensure_ingested()
        for row in self._read_rows(output_path):
            identifiers = {
                str(row.get("case_id") or ""),
                str(row.get("source_url") or ""),
                str(row.get("html_url") or ""),
            }
            if needle in identifiers:
                return self._row_to_document(row)
        return None

    def _ensure_ingested(self) -> Path:
        from data.ingestion.commonlii_sg import DEFAULT_OUTPUT, ingest  # noqa: WPS433

        output_path = self.output_path or DEFAULT_OUTPUT
        try:
            ingest(
                output_path,
                court=self.court,
                year=self.year,
                limit=self.limit,
                crawl_delay=self.metadata.crawl_delay_seconds,
                force=self.force,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            raise SourceAdapterError(f"CommonLII SG ingest failed: {exc}") from exc
        return Path(output_path)

    def _read_rows(self, output_path: Path) -> Iterator[dict[str, Any]]:
        if not output_path.exists():
            raise SourceAdapterError(f"CommonLII SG output missing after ingest: {output_path}")
        try:
            with output_path.open(encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise SourceAdapterError(
                            f"invalid CommonLII SG JSONL at {output_path}:{line_number}"
                        ) from exc
                    if not isinstance(row, dict):
                        raise SourceAdapterError(
                            f"invalid CommonLII SG row at {output_path}:{line_number}"
                        )
                    yield row
        except OSError as exc:
            raise SourceAdapterError(f"cannot read CommonLII SG output: {output_path}") from exc

    def _row_to_document(self, row: dict[str, Any]) -> SourceDocument:
        case_id = str(row.get("case_id") or "").strip()
        if not case_id:
            raise SourceAdapterError("CommonLII SG row missing case_id")
        source_url = str(row.get("source_url") or row.get("html_url") or "").strip()
        if not source_url:
            raise SourceAdapterError(f"CommonLII SG row {case_id} missing source_url")
        body_plain = str(row.get("body_plain") or "").strip()
        body_html = str(row.get("body_html") or "")
        body = body_plain or _html_text(body_html)
        return SourceDocument(
            document_id=case_id,
            source_url=source_url,
            title=_title(row),
            body=body,
            published_date=normalise_date(row.get("decision_date")),
            fetched_date=date.today(),
            source_metadata=self.metadata,
            doc_type=self.doc_type,
            extra=dict(row),
        )


def _title(row: dict[str, Any]) -> str:
    body_html = str(row.get("body_html") or "")
    html_title = _first_html_text(body_html, ("h1", "title"))
    return html_title or str(row.get("citation") or row.get("case_id") or "").strip()


def _html_text(html: str) -> str:
    return _first_html_text(html, ("body",)) or _first_html_text(html, ("html",))


def _first_html_text(html: str, selectors: tuple[str, ...]) -> str:
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup  # noqa: WPS433
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise SourceAdapterError("beautifulsoup4 not installed; cannot parse CommonLII HTML") from exc
    soup = BeautifulSoup(html, "html.parser")
    for selector in selectors:
        node = soup.find(selector)
        if node is not None:
            text = " ".join(node.get_text(" ", strip=True).split())
            if text:
                return text
    return ""
