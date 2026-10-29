"""Document metadata leakage detection and best-effort scrubbing."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Mapping
from xml.etree import ElementTree

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MIME = "application/pdf"
IMAGE_MIMES = {"image/jpeg", "image/jpg", "image/png"}

MAX_PREVIEW_CHARS = 160


@dataclass(frozen=True)
class MetadataFinding:
    id: str
    source: str
    field: str
    severity: str
    detail: str
    value_preview: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "source": self.source,
            "field": self.field,
            "severity": self.severity,
            "detail": self.detail,
            "value_preview": self.value_preview,
        }


def _preview(value: Any) -> str:
    text = str(value or "").replace("\x00", "").strip()
    if len(text) <= MAX_PREVIEW_CHARS:
        return text
    return text[:MAX_PREVIEW_CHARS] + "...[truncated]"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _finding(source: str, field: str, value: Any, detail: str, *, severity: str = "medium") -> MetadataFinding:
    raw_id = f"metadata:{source}:{field}"
    safe_id = re.sub(r"[^A-Za-z0-9_.:-]+", "_", raw_id).strip("_")
    return MetadataFinding(
        id=safe_id,
        source=source,
        field=field,
        severity=severity,
        detail=detail,
        value_preview=_preview(value),
    )


def _dedupe(findings: list[MetadataFinding]) -> list[MetadataFinding]:
    seen: set[tuple[str, str, str]] = set()
    out: list[MetadataFinding] = []
    for finding in findings:
        key = (finding.source, finding.field, finding.value_preview)
        if key in seen:
            continue
        seen.add(key)
        out.append(finding)
    return out


def _read_zip_member(archive: zipfile.ZipFile, name: str) -> bytes | None:
    try:
        return archive.read(name)
    except KeyError:
        return None


def _docx_xml_findings(xml_bytes: bytes, *, source: str, detail: str) -> list[MetadataFinding]:
    findings: list[MetadataFinding] = []
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError:
        return findings
    for node in root.iter():
        text = (node.text or "").strip()
        if text:
            findings.append(_finding(source, _local_name(node.tag), text, detail))
        for attr_name, attr_value in node.attrib.items():
            if attr_value:
                findings.append(_finding(source, _local_name(attr_name), attr_value, detail))
    return findings


def _inspect_docx(data: bytes) -> list[MetadataFinding]:
    findings: list[MetadataFinding] = []
    with zipfile.ZipFile(BytesIO(data)) as archive:
        for name, source in (
            ("docProps/core.xml", "docx_core_properties"),
            ("docProps/app.xml", "docx_app_properties"),
            ("docProps/custom.xml", "docx_custom_properties"),
        ):
            xml = _read_zip_member(archive, name)
            if xml:
                findings.extend(_docx_xml_findings(xml, source=source, detail=f"DOCX metadata part {name} is present"))

        comments = _read_zip_member(archive, "word/comments.xml")
        if comments:
            findings.extend(
                _docx_xml_findings(
                    comments,
                    source="docx_comments",
                    detail="DOCX comments can leak reviewer names, initials, timestamps, or comment text",
                )
            )

        document_xml = _read_zip_member(archive, "word/document.xml")
        if document_xml:
            try:
                root = ElementTree.fromstring(document_xml)
            except ElementTree.ParseError:
                root = None
            if root is not None:
                for node in root.iter():
                    local = _local_name(node.tag)
                    if local not in {"ins", "del", "moveFrom", "moveTo"}:
                        continue
                    for attr_name, attr_value in node.attrib.items():
                        attr_local = _local_name(attr_name)
                        if attr_local in {"author", "date", "initials"} and attr_value:
                            findings.append(
                                _finding(
                                    "docx_track_changes",
                                    attr_local,
                                    attr_value,
                                    "DOCX track-change metadata can leak editor identity or timestamps",
                                    severity="high",
                                )
                            )
    return _dedupe(findings)


def _inspect_pdf(data: bytes) -> list[MetadataFinding]:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise ValueError("PDF metadata inspection requires the optional pypdf dependency") from exc

    reader = PdfReader(BytesIO(data))
    findings: list[MetadataFinding] = []
    metadata: Mapping[str, Any] = reader.metadata or {}
    for raw_key, raw_value in metadata.items():
        key = str(raw_key).lstrip("/")
        value = _preview(raw_value)
        if not value:
            continue
        if key.lower() == "producer" and value.lower().startswith("pypdf"):
            continue
        findings.append(_finding("pdf_info", key, value, "PDF document metadata is present"))
    return _dedupe(findings)


def _inspect_image(data: bytes, mime_type: str) -> list[MetadataFinding]:
    try:
        from PIL import ExifTags, Image
    except Exception as exc:
        raise ValueError("image metadata inspection requires Pillow") from exc

    findings: list[MetadataFinding] = []
    with Image.open(BytesIO(data)) as image:
        exif = image.getexif()
        for tag_id, raw_value in exif.items():
            tag = ExifTags.TAGS.get(tag_id, str(tag_id))
            if tag == "GPSInfo":
                findings.append(
                    _finding(
                        "image_exif",
                        "GPSInfo",
                        "[present]",
                        "Image GPS EXIF metadata is present",
                        severity="high",
                    )
                )
                continue
            findings.append(_finding("image_exif", str(tag), raw_value, "Image EXIF metadata is present"))
        for key, value in image.info.items():
            if str(key).lower() in {"exif", "icc_profile"}:
                continue
            findings.append(
                _finding("image_info", str(key), value, "Image container metadata is present", severity="low")
            )
    return _dedupe(findings)


def inspect_metadata(data: bytes, *, filename: str, mime_type: str) -> list[MetadataFinding]:
    del filename
    normalized = mime_type.lower()
    if normalized == DOCX_MIME:
        return _inspect_docx(data)
    if normalized == PDF_MIME:
        return _inspect_pdf(data)
    if normalized in IMAGE_MIMES:
        return _inspect_image(data, normalized)
    return []
