from __future__ import annotations

import base64
import html
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Any
from xml.etree import ElementTree

from kaypoh.review.metadata import inspect_metadata

SUPPORTED_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SUPPORTED_PDF_MIME = "application/pdf"
SUPPORTED_TEXT_MIMES = {"text/plain", "text/markdown", "application/json"}


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    filename: str
    mime_type: str
    extraction_method: str
    page_count: int | None = None
    extraction_quality: str = "accepted"
    extraction_warnings: list[str] | None = None
    metadata_findings: list[dict[str, str]] | None = None


def _clean_text(text: str) -> str:
    cleaned = text.replace("\x00", "")
    cleaned = "".join(ch for ch in cleaned if ch.isprintable() or ch in ("\n", "\r", "\t"))
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _decode_base64(raw: str) -> bytes:
    try:
        return base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("document_base64 must be valid base64") from exc


def _extract_docx(data: bytes) -> str:
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


def _pdf_page_image_count(page: Any) -> int:
    try:
        resources = page.get("/Resources") or {}
        xobjects = resources.get("/XObject") or {}
        if hasattr(xobjects, "get_object"):
            xobjects = xobjects.get_object()
        count = 0
        for item in xobjects.values():
            obj = item.get_object() if hasattr(item, "get_object") else item
            if obj.get("/Subtype") == "/Image":
                count += 1
        return count
    except Exception:
        return 0


def _pdf_metadata_text(reader: Any) -> str:
    metadata = reader.metadata or {}
    return " ".join(str(value) for value in metadata.values() if value)


def _extract_pdf(data: bytes, ingest_settings: Any | None = None) -> tuple[str, int | None, str, list[str]]:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise ValueError("PDF extraction requires the optional pypdf dependency") from exc

    reader = PdfReader(BytesIO(data))
    pages: list[str] = []
    page_text_lengths: list[int] = []
    image_count = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
        page_text_lengths.append(len(_clean_text(text)))
        image_count += _pdf_page_image_count(page)

    page_count = len(reader.pages)
    extracted = "\n\n".join(page.strip() for page in pages if page.strip())
    cleaned = _clean_text(extracted)
    if not bool(getattr(ingest_settings, "fail_closed", True)):
        return extracted, page_count, "accepted", []

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
        warnings.append(
            f"PDF text layer is too sparse ({len(cleaned)} chars; minimum {min_text_chars})"
        )
    if page_count and empty_ratio > max_empty_ratio:
        warnings.append(
            f"PDF has too many pages without a reliable text layer ({empty_pages}/{page_count})"
        )
    if reject_image_only and image_count and avg_chars_per_page < min_chars_per_page:
        warnings.append("PDF appears image-heavy without enough extractable text")
    if scanner_hint and avg_chars_per_page < min_chars_per_page:
        warnings.append("PDF producer metadata suggests scanned/OCR content with insufficient text")
    if warnings:
        raise ValueError(
            "document extraction failed closed: "
            + "; ".join(warnings)
            + ". Convert/export the file to .docx or submit a PDF with a reliable text layer."
        )
    if image_count:
        warnings.append("PDF contains embedded images; reviewed text layer only")
    return extracted, page_count, "accepted", warnings


def _infer_mime_type(filename: str, mime_type: str | None) -> str:
    if mime_type:
        return mime_type.strip().lower()
    lower = filename.lower()
    if lower.endswith(".docx"):
        return SUPPORTED_DOCX_MIME
    if lower.endswith(".pdf"):
        return SUPPORTED_PDF_MIME
    return "text/plain"


def extract_review_document(payload: Any, ingest_settings: Any | None = None) -> ExtractedDocument:
    text = getattr(payload, "text", None)
    filename = str(getattr(payload, "document_filename", "") or "inline.txt")
    mime_type = _infer_mime_type(filename, getattr(payload, "document_mime_type", None))

    if text:
        cleaned = _clean_text(str(text))
        if not cleaned:
            raise ValueError("text must contain non-whitespace printable content")
        return ExtractedDocument(
            text=cleaned,
            filename=filename,
            mime_type="text/plain",
            extraction_method="inline_text",
            page_count=None,
            extraction_quality="accepted",
            extraction_warnings=[],
            metadata_findings=[],
        )

    raw_base64 = getattr(payload, "document_base64", None)
    if not raw_base64:
        raise ValueError("either text or document_base64 is required")

    data = _decode_base64(str(raw_base64))
    try:
        metadata_findings = [
            finding.to_dict()
            for finding in inspect_metadata(data, filename=filename, mime_type=mime_type)
        ]
    except ValueError:
        metadata_findings = []
    if mime_type in SUPPORTED_TEXT_MIMES:
        extracted = data.decode("utf-8", errors="replace")
        method = "base64_text"
        page_count = None
        extraction_quality = "accepted"
        extraction_warnings: list[str] = []
    elif mime_type == SUPPORTED_DOCX_MIME:
        extracted = _extract_docx(data)
        method = "docx_xml"
        page_count = None
        extraction_quality = "accepted"
        extraction_warnings = []
    elif mime_type == SUPPORTED_PDF_MIME:
        extracted, page_count, extraction_quality, extraction_warnings = _extract_pdf(data, ingest_settings)
        method = "pypdf"
    else:
        raise ValueError(f"unsupported document_mime_type: {mime_type}")

    cleaned = _clean_text(extracted)
    if not cleaned:
        raise ValueError("document extraction produced no text")
    return ExtractedDocument(
        text=cleaned,
        filename=filename,
        mime_type=mime_type,
        extraction_method=method,
        page_count=page_count,
        extraction_quality=extraction_quality,
        extraction_warnings=extraction_warnings,
        metadata_findings=metadata_findings,
    )
