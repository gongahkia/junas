from __future__ import annotations

import base64
import html
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Any
from xml.etree import ElementTree


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


def _extract_pdf(data: bytes) -> tuple[str, int | None]:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise ValueError("PDF extraction requires the optional pypdf dependency") from exc

    reader = PdfReader(BytesIO(data))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\n".join(page.strip() for page in pages if page.strip()), len(reader.pages)


def _infer_mime_type(filename: str, mime_type: str | None) -> str:
    if mime_type:
        return mime_type.strip().lower()
    lower = filename.lower()
    if lower.endswith(".docx"):
        return SUPPORTED_DOCX_MIME
    if lower.endswith(".pdf"):
        return SUPPORTED_PDF_MIME
    return "text/plain"


def extract_review_document(payload: Any) -> ExtractedDocument:
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
        )

    raw_base64 = getattr(payload, "document_base64", None)
    if not raw_base64:
        raise ValueError("either text or document_base64 is required")

    data = _decode_base64(str(raw_base64))
    if mime_type in SUPPORTED_TEXT_MIMES:
        extracted = data.decode("utf-8", errors="replace")
        method = "base64_text"
        page_count = None
    elif mime_type == SUPPORTED_DOCX_MIME:
        extracted = _extract_docx(data)
        method = "docx_xml"
        page_count = None
    elif mime_type == SUPPORTED_PDF_MIME:
        extracted, page_count = _extract_pdf(data)
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
    )
