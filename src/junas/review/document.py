from __future__ import annotations

import base64
import html
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Any
from xml.etree import ElementTree

import junas.input_limits as limits
from junas.input_limits import (
    check_analyzed_text,
    check_encoded_document,
    check_inline_text,
    check_source_bytes,
)
from junas.review.container_scan import (
    DOCX_MIME,
    EML_MIMES,
    HTML_MIMES,
    MARKDOWN_MIMES,
    PDF_MIME,
    PPTX_MIME,
    RTF_MIMES,
    SVG_MIMES,
    TAR_MIMES,
    XLSX_MIME,
    ZIP_MIMES,
    ContainerScanError,
    ContainerScanResult,
    _EmailBudget,
    is_container_mime,
    scan_container,
    validate_document_type,
)
from junas.review.container_scan import (
    infer_mime_type as infer_container_mime_type,
)
from junas.review.document_structure import (
    DocumentStructure,
    parse_document_structure,
    parse_docx_structure,
    parse_eml_structure,
    parse_pdf_structure,
    parse_pptx_structure,
    parse_xlsx_structure,
)
from junas.review.document_structure import clean_document_text as _clean_text
from junas.review.image_scan import (
    ImageCandidate,
    ImageScanError,
    _ImageBudget,
    _preflight_pdf_images,
    collect_docx_images,
    collect_pdf_images,
    collect_pdf_page_renders,
    image_mime_from_name,
    image_pixel_count,
    standalone_image_candidate,
)
from junas.review.metadata import inspect_metadata

SUPPORTED_DOCX_MIME = DOCX_MIME
SUPPORTED_XLSX_MIME = XLSX_MIME
SUPPORTED_PPTX_MIME = PPTX_MIME
SUPPORTED_PDF_MIME = PDF_MIME
SUPPORTED_TEXT_MIMES = {"text/plain", "text/markdown", "application/json"}
SUPPORTED_IMAGE_REVIEW_MIMES = {"image/jpeg", "image/png"}
SUPPORTED_CONTAINER_MIMES = {
    SUPPORTED_DOCX_MIME,
    SUPPORTED_XLSX_MIME,
    SUPPORTED_PPTX_MIME,
    SUPPORTED_PDF_MIME,
    *ZIP_MIMES,
    *TAR_MIMES,
    *HTML_MIMES,
    *SVG_MIMES,
    *RTF_MIMES,
    *EML_MIMES,
    *MARKDOWN_MIMES,
    "application/vnd.ms-outlook",
    "application/x-7z-compressed",
}


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    filename: str
    mime_type: str
    extraction_method: str
    original_data: bytes | None = None
    page_count: int | None = None
    extraction_quality: str = "accepted"
    extraction_warnings: list[str] | None = None
    metadata_findings: list[dict[str, str]] | None = None
    image_candidates: list[ImageCandidate] | None = None
    image_text_spans: list[Any] | None = None
    image_scan_provider: str = "none"
    document_structure: DocumentStructure | None = None


def _decode_base64(raw: str) -> bytes:
    check_encoded_document(raw)
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("document_base64 must be valid base64") from exc
    check_source_bytes(data)
    return data


def _fail_closed(ingest_settings: Any | None) -> bool:
    return bool(getattr(ingest_settings, "fail_closed", False))


def _fail_open_warning(reason: str) -> str:
    return f"fail-open: {reason}"


def _extract_docx(data: bytes) -> str:
    try:
        return parse_docx_structure(data).text
    except Exception:
        pass
    with zipfile.ZipFile(BytesIO(data)) as archive:
        try:
            document_xml = archive.read("word/document.xml")
        except KeyError as exc:
            raise ValueError("DOCX payload missing word/document.xml") from exc

    try:
        root = ElementTree.fromstring(document_xml)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs: list[str] = []
        for paragraph in root.findall(".//w:p", namespace):
            parts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
            text = "".join(parts).strip()
            if text:
                paragraphs.append(text)
        return "\n".join(paragraphs)
    except Exception:
        xml = document_xml.decode("utf-8", errors="replace")
        paragraph_xml = re.findall(r"<w:p\b.*?</w:p>", xml, flags=re.IGNORECASE | re.DOTALL) or [xml]
        paragraphs = []
        for paragraph in paragraph_xml:
            parts = re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", paragraph, flags=re.IGNORECASE | re.DOTALL)
            text = "".join(html.unescape(re.sub(r"<[^>]+>", "", part)) for part in parts).strip()
            if text:
                paragraphs.append(text)
        return "\n".join(paragraphs)


def _merge_text_blocks(*blocks: str) -> str:
    return "\n\n".join(block.strip() for block in blocks if block and block.strip())


def _docx_image_count(data: bytes) -> int:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            return sum(1 for name in archive.namelist() if name.startswith("word/media/"))
    except Exception:
        return 0


def _pdf_page_image_count(page: Any) -> int | None:
    try:
        budget = _ImageBudget()
        _preflight_pdf_images(page, budget)
        return budget.images
    except Exception:
        return None


def _pdf_metadata_text(reader: Any) -> str:
    metadata = reader.metadata or {}
    return " ".join(str(value) for value in metadata.values() if value)


def _extract_pdf(
    data: bytes,
    ingest_settings: Any | None = None,
    *,
    image_scan_enabled: bool = False,
    page_inventory: list[dict[str, Any]] | None = None,
) -> tuple[str, int | None, str, list[str]]:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise ValueError("PDF extraction requires the optional pypdf dependency") from exc

    reader = PdfReader(BytesIO(data))
    pages: list[str] = []
    page_text_lengths: list[int] = []
    image_count = 0
    retained_bytes = 0
    unknown_images = False
    min_chars_per_page = int(getattr(ingest_settings, "min_pdf_chars_per_page", 20) or 0)
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if pages:
            retained_bytes += 2
        retained_bytes += limits._utf8_size(text, limits.MAX_ANALYZED_TEXT_BYTES - retained_bytes, "analyzed text")
        pages.append(text)
        page_text_lengths.append(len(_clean_text(text)))
        page_images = _pdf_page_image_count(page)
        unknown_images |= page_images is None
        image_count += page_images or 0
        if page_inventory is not None:
            page_inventory.append(
                {
                    "page_number": page_number,
                    "text_chars": page_text_lengths[-1],
                    "images": page_images,
                    "needs_ocr": page_text_lengths[-1] < min_chars_per_page,
                }
            )

    page_count = len(reader.pages)
    extracted = "\n\n".join(page.strip() for page in pages if page.strip())
    cleaned = _clean_text(extracted)
    min_text_chars = int(getattr(ingest_settings, "min_pdf_text_chars", 20) or 0)
    min_chars_per_page = int(getattr(ingest_settings, "min_pdf_chars_per_page", 20) or 0)
    max_empty_ratio = float(getattr(ingest_settings, "max_empty_pdf_page_ratio", 0.2))
    reject_image_only = bool(getattr(ingest_settings, "reject_image_only_pdf", True))
    empty_pages = sum(1 for count in page_text_lengths if count < min_chars_per_page)
    empty_ratio = (empty_pages / page_count) if page_count else 1.0
    avg_chars_per_page = (sum(page_text_lengths) / page_count) if page_count else 0.0
    metadata_text = _pdf_metadata_text(reader).lower()
    scanner_hint = any(marker in metadata_text for marker in ("scanner", "scan", "ocr", "image capture"))
    warnings: list[str] = []
    if len(cleaned) < min_text_chars:
        warnings.append(f"PDF text layer is too sparse ({len(cleaned)} chars; minimum {min_text_chars})")
    if page_count and empty_ratio > max_empty_ratio:
        warnings.append(f"PDF has too many pages without a reliable text layer ({empty_pages}/{page_count})")
    if reject_image_only and image_count and avg_chars_per_page < min_chars_per_page:
        warnings.append("PDF appears image-heavy without enough extractable text")
    if scanner_hint and avg_chars_per_page < min_chars_per_page:
        warnings.append("PDF producer metadata suggests scanned/OCR content with insufficient text")
    if warnings and image_scan_enabled:
        warnings.append("PDF text layer is sparse; configured image OCR will scan images or rendered pages")
        return extracted, page_count, "ocr_pending", warnings
    if warnings and _fail_closed(ingest_settings):
        raise ValueError(
            "document extraction failed closed: "
            + "; ".join(warnings)
            + ". Convert/export the file to .docx or submit a PDF with a reliable text layer."
        )
    if warnings:
        return extracted, page_count, "degraded", [_fail_open_warning(w) for w in warnings]
    if empty_pages:
        warnings.append(f"PDF has {empty_pages} sparse page(s); reviewed text layer only")
    if image_count and not image_scan_enabled:
        warnings.append("PDF contains embedded images; reviewed text layer only")
    if unknown_images:
        warnings.append("PDF image inventory is unknown; reviewed text layer only")
    return extracted, page_count, "accepted", warnings


def _infer_mime_type(filename: str, mime_type: str | None) -> str:
    if mime_type:
        return mime_type.partition(";")[0].strip().lower()
    inferred = infer_container_mime_type(filename)
    if inferred != "text/plain":
        return inferred
    lower = filename.lower()
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".png"):
        return "image/png"
    return "text/plain"


def extract_review_document(
    payload: Any,
    ingest_settings: Any | None = None,
    *,
    image_scan_enabled: bool = False,
    image_scan_settings: Any | None = None,
) -> ExtractedDocument:
    text = getattr(payload, "text", None)
    filename = str(getattr(payload, "document_filename", "") or "inline.txt")
    mime_type = _infer_mime_type(filename, getattr(payload, "document_mime_type", None))

    if text:
        check_inline_text(text)
        cleaned = _clean_text(str(text))
        if not cleaned:
            raise ValueError("text must contain non-whitespace printable content")
        return ExtractedDocument(
            text=cleaned,
            filename=filename,
            mime_type="text/plain",
            extraction_method="inline_text",
            original_data=None,
            page_count=None,
            extraction_quality="accepted",
            extraction_warnings=[],
            metadata_findings=[],
            image_candidates=[],
            image_text_spans=[],
        )

    raw_base64 = getattr(payload, "document_base64", None)
    if not raw_base64:
        raise ValueError("either text or document_base64 is required")

    data = _decode_base64(raw_base64)
    fail_closed = _fail_closed(ingest_settings)
    budget = _EmailBudget(fail_closed=fail_closed)
    validate_document_type(data, filename=filename, mime_type=mime_type, email_budget=budget)
    fail_open_warnings: list[str] = []
    try:
        metadata_findings = [
            finding.to_dict() for finding in inspect_metadata(data, filename=filename, mime_type=mime_type)
        ]
    except Exception as exc:
        if fail_closed:
            raise ValueError(f"metadata inspection failed closed: {exc}") from exc
        metadata_findings = []
        fail_open_warnings.append(_fail_open_warning(f"metadata inspection skipped: {exc}"))
    container_text = ""
    document_structure: DocumentStructure | None = None
    container_findings: list[dict[str, str]] = []
    container_warnings: list[str] = []
    container_image_candidates: list[ImageCandidate] = []
    container_scan: ContainerScanResult | None = None
    if is_container_mime(mime_type):
        try:
            container_scan = scan_container(
                data,
                filename=filename,
                mime_type=mime_type,
                image_scan_enabled=image_scan_enabled,
                fail_closed=fail_closed,
                _budget=budget,
                _preflighted=True,
            )
        except ContainerScanError as exc:
            if fail_closed:
                raise ValueError(f"container scan failed closed: {exc}") from exc
            container_warnings.append(_fail_open_warning(f"container scan skipped: {exc}"))
        if container_scan is not None:
            container_text = container_scan.text
            container_findings = [finding.to_dict() for finding in container_scan.findings]
            container_warnings = list(container_scan.warnings)
            container_image_candidates = list(container_scan.image_candidates)
            metadata_findings.extend(container_findings)
    container_warnings.extend(fail_open_warnings)

    if mime_type in SUPPORTED_TEXT_MIMES:
        extracted = data.decode("utf-8", errors="replace")
        if mime_type == "text/markdown":
            extracted = _merge_text_blocks(extracted, container_text)
        method = "base64_text"
        page_count = None
        extraction_quality = "accepted"
        extraction_warnings = container_warnings
        image_candidates: list[ImageCandidate] = []
    elif mime_type == SUPPORTED_DOCX_MIME:
        if container_text:
            extracted = container_text
        else:
            document_structure = parse_docx_structure(data)
            extracted = document_structure.text
        method = "docx_container_xml"
        page_count = None
        extraction_quality = "accepted"
        image_count = _docx_image_count(data)
        extraction_warnings = (
            ["DOCX contains embedded images; reviewed text layer only"]
            if image_count and not image_scan_enabled
            else []
        )
        extraction_warnings.extend(container_warnings)
        image_candidates = container_image_candidates or (collect_docx_images(data) if image_scan_enabled else [])
    elif mime_type == SUPPORTED_PDF_MIME:
        page_inventory: list[dict[str, Any]] = []
        extracted, page_count, extraction_quality, extraction_warnings = _extract_pdf(
            data,
            ingest_settings,
            image_scan_enabled=image_scan_enabled,
            page_inventory=page_inventory,
        )
        extracted = _merge_text_blocks(extracted, container_text)
        try:
            document_structure = parse_pdf_structure(data)
            if document_structure.text.strip() and not container_text.strip():
                extracted = document_structure.text
        except Exception:
            document_structure = None
        extraction_warnings.extend(container_warnings)
        method = "pypdf"
        image_candidates = []
        if image_scan_enabled:
            required_pages = [p["page_number"] for p in page_inventory if p["needs_ocr"]]
            if not page_inventory and extraction_quality == "ocr_pending":
                required_pages = list(range(1, (page_count or 0) + 1))
            try:
                render_enabled = bool(getattr(image_scan_settings, "pdf_render_pages", True))
                max_pages = int(getattr(image_scan_settings, "pdf_render_max_pages", 8))
                if required_pages and not render_enabled:
                    raise ImageScanError(f"PDF OCR rendering disabled; pages {required_pages} require OCR")
                if len(required_pages) > max_pages:
                    reason = (
                        f"PDF OCR page limit {max_pages} would leave "
                        f"{len(required_pages) - max_pages} page(s) unreviewed"
                    )
                    if fail_closed:
                        raise ImageScanError(reason)
                    extraction_warnings.append(_fail_open_warning(reason))
                    extraction_quality = "degraded"
                selected = required_pages[:max_pages]
                image_candidates = collect_pdf_images(
                    data, exclude_pages=set(required_pages), settings=image_scan_settings
                )
                if selected:
                    render_budget = _ImageBudget(image_scan_settings)
                    for candidate in image_candidates:
                        render_budget.charge(
                            pixels=image_pixel_count(candidate.data), encoded_bytes=len(candidate.data)
                        )
                    rendered = collect_pdf_page_renders(
                        data,
                        max_pages=max_pages,
                        scale=float(getattr(image_scan_settings, "pdf_render_scale", 2.0)),
                        page_numbers=selected,
                        settings=image_scan_settings,
                        _budget=render_budget,
                    )
                    if len(rendered) != len(selected):
                        raise ImageScanError("PDF required page rendering returned incomplete coverage")
                    image_candidates.extend(rendered)
                    extraction_warnings.append(f"PDF rendered {len(rendered)} page(s) for configured image OCR")
                if required_pages and not image_candidates:
                    raise ImageScanError("PDF pages require OCR but no images were collected")
            except (ImageScanError, ValueError, RuntimeError, OSError) as exc:
                if fail_closed:
                    raise ImageScanError(f"PDF image collection failed closed: {exc}") from exc
                image_candidates = []
                extraction_quality = "degraded"
                extraction_warnings.append(_fail_open_warning(f"PDF image collection incomplete: {exc}"))
        image_candidates.sort(key=lambda c: (c.locator.page_number or 0, c.locator.image_index))
        for page in page_inventory:
            metadata_findings.append(
                {
                    "id": f"pdf-page-{page['page_number']}",
                    "source": "pdf_page_coverage",
                    "field": str(page["page_number"]),
                    "severity": "info",
                    "detail": (
                        f"text_chars={page['text_chars']}; images={page['images']}; requires_ocr={page['needs_ocr']}"
                    ),
                    "value_preview": "text_and_image_inventory",
                }
            )
    elif mime_type == SUPPORTED_XLSX_MIME:
        document_structure = parse_xlsx_structure(data)
        extracted = document_structure.text
        method = "xlsx_container"
        page_count = None
        extraction_quality = "accepted"
        extraction_warnings = container_warnings
        image_candidates = container_image_candidates
    elif mime_type == SUPPORTED_PPTX_MIME:
        document_structure = parse_pptx_structure(data)
        extracted = document_structure.text
        method = "pptx_container"
        page_count = None
        extraction_quality = "accepted"
        extraction_warnings = container_warnings
        image_candidates = container_image_candidates
    elif mime_type in EML_MIMES:
        document_structure = parse_eml_structure(data, container_scan=container_scan) if container_scan else None
        extracted = document_structure.text if document_structure else ""
        method = "eml_container"
        page_count = None
        extraction_quality = (
            "degraded"
            if any("fail-open:" in w or "reviewed text layer only" in w for w in container_warnings)
            else "accepted"
        )
        extraction_warnings = container_warnings
        image_candidates = container_image_candidates
    elif mime_type in SUPPORTED_CONTAINER_MIMES:
        extracted = container_text
        method = f"{mime_type.split('/')[-1]}_container"
        page_count = None
        extraction_quality = "accepted"
        extraction_warnings = container_warnings
        image_candidates = container_image_candidates
    elif (
        mime_type in SUPPORTED_IMAGE_REVIEW_MIMES
        or image_mime_from_name(filename, data) in SUPPORTED_IMAGE_REVIEW_MIMES
    ):
        if not image_scan_enabled:
            if fail_closed:
                raise ValueError(f"unsupported document_mime_type: {mime_type}")
            extracted = ""
            method = "unsupported_image"
            page_count = None
            extraction_quality = "degraded"
            extraction_warnings = container_warnings + [
                _fail_open_warning(f"image review skipped because OCR is disabled for {mime_type}")
            ]
            image_candidates = []
        else:
            extracted = ""
            method = "image_ocr"
            page_count = None
            extraction_quality = "ocr_pending"
            extraction_warnings = ["standalone image payload requires configured image OCR"]
            image_candidates = [standalone_image_candidate(data, filename=filename, mime_type=mime_type)]
    else:
        if fail_closed:
            raise ValueError(f"unsupported document_mime_type: {mime_type}")
        extracted = ""
        method = "unsupported_document"
        page_count = None
        extraction_quality = "degraded"
        extraction_warnings = container_warnings + [_fail_open_warning(f"unsupported document_mime_type: {mime_type}")]
        image_candidates = []

    if any("fail-open:" in warning or "reviewed text layer only" in warning for warning in extraction_warnings):
        extraction_quality = "degraded"
    check_analyzed_text(extracted)
    cleaned = _clean_text(extracted)
    if not cleaned and not image_candidates:
        if fail_closed:
            raise ValueError("document extraction produced no text")
        extraction_quality = "degraded"
        extraction_warnings = list(extraction_warnings)
        extraction_warnings.append(
            _fail_open_warning("document extraction produced no text; review continued with empty text")
        )
    if document_structure is not None and document_structure.text != cleaned:
        document_structure = parse_document_structure(cleaned)
    return ExtractedDocument(
        text=cleaned,
        filename=filename,
        mime_type=mime_type,
        extraction_method=method,
        original_data=data,
        page_count=page_count,
        extraction_quality=extraction_quality,
        extraction_warnings=extraction_warnings,
        metadata_findings=metadata_findings,
        image_candidates=image_candidates,
        image_text_spans=[],
        image_scan_provider="none",
        document_structure=document_structure,
    )
