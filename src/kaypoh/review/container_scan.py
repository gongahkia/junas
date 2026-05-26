"""Recursive container traversal and hidden-content extraction.

The scanner is intentionally stdlib-first so kaypoh-local does not gain heavy parser
dependencies. Unsupported risky containers fail closed rather than pretending we reviewed
their hidden surfaces.
"""

from __future__ import annotations

import email
import html
import mimetypes
import re
import tarfile
import zipfile
from dataclasses import dataclass, field
from email import policy
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any
from xml.etree import ElementTree

from kaypoh.review.image_scan import ImageCandidate, ImageLocator, image_mime_from_name

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
PDF_MIME = "application/pdf"
ZIP_MIMES = {"application/zip", "application/x-zip-compressed"}
TAR_MIMES = {"application/x-tar", "application/gzip", "application/x-gzip"}
HTML_MIMES = {"text/html", "application/xhtml+xml"}
SVG_MIMES = {"image/svg+xml", "application/svg+xml"}
RTF_MIMES = {"application/rtf", "text/rtf"}
EML_MIMES = {"message/rfc822"}
MARKDOWN_MIMES = {"text/markdown"}
IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/tiff", "image/bmp"}

MAX_DEPTH = 3
MAX_ENTRIES = 256
MAX_MEMBER_BYTES = 25 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100.0
MAX_PREVIEW_CHARS = 160

_DOCX_TEXT_PART_RE = re.compile(
    r"^word/(?:document|comments|footnotes|endnotes|header\d+|footer\d+)\.xml$"
)
_PPTX_TEXT_PART_RE = re.compile(
    r"^ppt/(?:slides/slide\d+|notesSlides/notesSlide\d+|slideMasters/slideMaster\d+|"
    r"slideLayouts/slideLayout\d+|comments/comment\d+)\.xml$"
)
_XLSX_TEXT_PART_RE = re.compile(
    r"^xl/(?:sharedStrings|workbook|comments\d*|worksheets/sheet\d+|pivotCache/pivotCacheDefinition\d+|"
    r"pivotCache/pivotCacheRecords\d+)\.xml$"
)


class ContainerScanError(ValueError):
    """Raised when a submitted container cannot be traversed safely."""


@dataclass(frozen=True)
class ContainerFinding:
    source: str
    field: str
    severity: str
    detail: str
    value_preview: str = ""

    @property
    def id(self) -> str:
        raw = f"container:{self.source}:{self.field}:{self.value_preview}"
        return re.sub(r"[^A-Za-z0-9_.:-]+", "_", raw).strip("_")[:220]

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "source": self.source,
            "field": self.field,
            "severity": self.severity,
            "detail": self.detail,
            "value_preview": self.value_preview,
        }


@dataclass
class ContainerScanResult:
    text_blocks: list[str] = field(default_factory=list)
    findings: list[ContainerFinding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    image_candidates: list[ImageCandidate] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(block for block in self.text_blocks if block.strip())

    def extend(self, other: "ContainerScanResult", *, prefix: str | None = None) -> None:
        if prefix:
            self.text_blocks.extend(f"[Container: {prefix}]\n{block}" for block in other.text_blocks if block.strip())
        else:
            self.text_blocks.extend(other.text_blocks)
        self.findings.extend(other.findings)
        self.warnings.extend(other.warnings)
        self.image_candidates.extend(other.image_candidates)


def scan_container(
    data: bytes,
    *,
    filename: str,
    mime_type: str,
    image_scan_enabled: bool = False,
) -> ContainerScanResult:
    normalized = (mime_type or infer_mime_type(filename, data)).lower()
    return _scan_by_type(
        data,
        filename=filename or "document",
        mime_type=normalized,
        image_scan_enabled=image_scan_enabled,
        depth=0,
        container_prefix="",
    )


def infer_mime_type(filename: str, data: bytes | None = None) -> str:
    lower = filename.lower()
    if lower.endswith(".docx"):
        return DOCX_MIME
    if lower.endswith(".xlsx"):
        return XLSX_MIME
    if lower.endswith(".pptx"):
        return PPTX_MIME
    if lower.endswith(".pdf"):
        return PDF_MIME
    if lower.endswith(".eml"):
        return "message/rfc822"
    if lower.endswith(".msg"):
        return "application/vnd.ms-outlook"
    if lower.endswith(".zip"):
        return "application/zip"
    if lower.endswith(".tar"):
        return "application/x-tar"
    if lower.endswith((".tgz", ".tar.gz")):
        return "application/gzip"
    if lower.endswith(".7z"):
        return "application/x-7z-compressed"
    if lower.endswith((".html", ".htm")):
        return "text/html"
    if lower.endswith(".svg"):
        return "image/svg+xml"
    if lower.endswith(".rtf"):
        return "application/rtf"
    if lower.endswith(".md"):
        return "text/markdown"
    guessed = (mimetypes.guess_type(filename)[0] or "").lower()
    if guessed:
        return guessed
    if data:
        if data.startswith(b"%PDF"):
            return PDF_MIME
        if data.startswith(b"PK\x03\x04"):
            return "application/zip"
    return "text/plain"


def is_container_mime(mime_type: str) -> bool:
    normalized = mime_type.lower()
    return normalized in {
        DOCX_MIME,
        XLSX_MIME,
        PPTX_MIME,
        PDF_MIME,
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


def _scan_by_type(
    data: bytes,
    *,
    filename: str,
    mime_type: str,
    image_scan_enabled: bool,
    depth: int,
    container_prefix: str,
) -> ContainerScanResult:
    if depth > MAX_DEPTH:
        raise ContainerScanError(f"container recursion depth exceeds maximum {MAX_DEPTH}")
    _check_magic_bytes(data, filename=filename, mime_type=mime_type)
    lower = filename.lower()
    if lower.endswith((".docm", ".xlsm", ".pptm")):
        raise ContainerScanError("macro-enabled Office containers are refused by default")
    if mime_type == DOCX_MIME:
        return _scan_docx(data, image_scan_enabled=image_scan_enabled, container_prefix=container_prefix)
    if mime_type == XLSX_MIME:
        return _scan_xlsx(data, image_scan_enabled=image_scan_enabled, container_prefix=container_prefix)
    if mime_type == PPTX_MIME:
        return _scan_pptx(data, image_scan_enabled=image_scan_enabled, container_prefix=container_prefix)
    if mime_type == PDF_MIME:
        return _scan_pdf(data, image_scan_enabled=image_scan_enabled, depth=depth, container_prefix=container_prefix)
    if mime_type in ZIP_MIMES:
        return _scan_zip_archive(
            data,
            image_scan_enabled=image_scan_enabled,
            depth=depth,
            container_prefix=container_prefix,
        )
    if mime_type in TAR_MIMES:
        return _scan_tar_archive(
            data,
            image_scan_enabled=image_scan_enabled,
            depth=depth,
            container_prefix=container_prefix,
        )
    if mime_type in EML_MIMES:
        return _scan_eml(data, image_scan_enabled=image_scan_enabled, depth=depth, container_prefix=container_prefix)
    if mime_type == "application/vnd.ms-outlook":
        raise ContainerScanError("MSG containers require an optional safe parser and are refused by default")
    if mime_type == "application/x-7z-compressed":
        raise ContainerScanError("7z archive traversal requires an optional safe parser and is refused by default")
    if mime_type in HTML_MIMES:
        return _scan_html(data, source="html")
    if mime_type in SVG_MIMES:
        return _scan_svg(data)
    if mime_type in RTF_MIMES:
        return _scan_rtf(data)
    if mime_type in MARKDOWN_MIMES:
        return _scan_markdown(data)
    if mime_type in IMAGE_MIMES and image_scan_enabled:
        return ContainerScanResult(
            image_candidates=[
                ImageCandidate(
                    data=data,
                    mime_type=image_mime_from_name(filename, data),
                    locator=ImageLocator(
                        container_path=container_prefix or filename,
                        image_index=0,
                        source_type="embedded_image",
                    ),
                )
            ]
        )
    if mime_type.startswith("text/"):
        return ContainerScanResult(text_blocks=[data.decode("utf-8", errors="replace")])
    return ContainerScanResult()


def _preview(value: Any) -> str:
    text = str(value or "").replace("\x00", "").strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) <= MAX_PREVIEW_CHARS:
        return text
    return text[:MAX_PREVIEW_CHARS] + "...[truncated]"


def _finding(source: str, field: str, value: Any, detail: str, *, severity: str = "medium") -> ContainerFinding:
    return ContainerFinding(
        source=source,
        field=field,
        severity=severity,
        detail=detail,
        value_preview=_preview(value),
    )


def _dedupe_findings(findings: list[ContainerFinding]) -> list[ContainerFinding]:
    seen: set[tuple[str, str, str]] = set()
    out: list[ContainerFinding] = []
    for finding in findings:
        key = (finding.source, finding.field, finding.value_preview)
        if key in seen:
            continue
        seen.add(key)
        out.append(finding)
    return out


def _safe_xml_root(xml_bytes: bytes, *, label: str) -> ElementTree.Element:
    prefix = xml_bytes[:4096].lower()
    if b"<!doctype" in prefix or b"<!entity" in prefix:
        raise ContainerScanError(f"unsafe XML DTD/entity declaration in {label}")
    try:
        return ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise ContainerScanError(f"malformed XML in {label}: {exc}") from exc


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _xml_text(xml_bytes: bytes, *, label: str, tags: set[str] | None = None) -> str:
    root = _safe_xml_root(xml_bytes, label=label)
    wanted = tags or {"t", "delText", "title", "desc", "metadata", "text", "v"}
    parts: list[str] = []
    for node in root.iter():
        local = _local_name(node.tag)
        if local in wanted and node.text and node.text.strip():
            parts.append(node.text.strip())
    return "\n".join(parts)


def _zip_archive(data: bytes) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(BytesIO(data), "r")
    except zipfile.BadZipFile as exc:
        raise ContainerScanError("container is not a valid ZIP package") from exc


def _validate_zip(archive: zipfile.ZipFile) -> None:
    infos = archive.infolist()
    if len(infos) > MAX_ENTRIES:
        raise ContainerScanError(f"container has {len(infos)} entries; maximum is {MAX_ENTRIES}")
    total = 0
    for info in infos:
        name = info.filename
        _validate_member_path(name)
        if info.flag_bits & 0x1:
            raise ContainerScanError(f"encrypted ZIP member refused: {name}")
        if info.file_size > MAX_MEMBER_BYTES:
            raise ContainerScanError(f"container member {name} exceeds {MAX_MEMBER_BYTES} bytes")
        if info.compress_size and info.file_size / max(1, info.compress_size) > MAX_COMPRESSION_RATIO:
            raise ContainerScanError(f"container member {name} exceeds compression-ratio cap")
        total += info.file_size
        if total > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise ContainerScanError("container uncompressed size exceeds safety cap")


def _validate_member_path(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"..", ""} for part in path.parts):
        raise ContainerScanError(f"unsafe archive member path refused: {name}")


def _read_zip_member(archive: zipfile.ZipFile, name: str) -> bytes | None:
    try:
        return archive.read(name)
    except KeyError:
        return None


def _read_zip_text_parts(
    archive: zipfile.ZipFile,
    *,
    matcher: re.Pattern[str],
    source: str,
    detail: str,
) -> tuple[list[str], list[ContainerFinding]]:
    blocks: list[str] = []
    findings: list[ContainerFinding] = []
    for name in sorted(archive.namelist()):
        if not matcher.match(name):
            continue
        xml = archive.read(name)
        text = _xml_text(xml, label=name)
        if text:
            blocks.append(f"[{name}]\n{text}")
            if name != "word/document.xml":
                findings.append(_finding(source, name, text, detail))
    return blocks, findings


def _collect_zip_images(
    archive: zipfile.ZipFile,
    *,
    prefix: str,
    source_type: str,
    container_prefix: str,
) -> list[ImageCandidate]:
    candidates: list[ImageCandidate] = []
    media_names = sorted(name for name in archive.namelist() if name.startswith(prefix))
    for index, name in enumerate(media_names):
        image_data = archive.read(name)
        mime_type = image_mime_from_name(name, image_data)
        if mime_type not in IMAGE_MIMES:
            continue
        path = f"{container_prefix}/{name}" if container_prefix else name
        candidates.append(
            ImageCandidate(
                data=image_data,
                mime_type=mime_type,
                locator=ImageLocator(container_path=path, image_index=index, source_type=source_type),
            )
        )
    return candidates


def _scan_docx(data: bytes, *, image_scan_enabled: bool, container_prefix: str) -> ContainerScanResult:
    with _zip_archive(data) as archive:
        _validate_zip(archive)
        names = set(archive.namelist())
        if "word/document.xml" not in names:
            raise ContainerScanError("DOCX payload missing word/document.xml")
        _refuse_macros(names)
        blocks, findings = _read_zip_text_parts(
            archive,
            matcher=_DOCX_TEXT_PART_RE,
            source="docx_hidden_part",
            detail="DOCX hidden or secondary XML part contains reviewable text",
        )
        if any(name.startswith("word/embeddings/") for name in names):
            findings.append(
                _finding(
                    "docx_embedded_object",
                    "word/embeddings",
                    "[present]",
                    "DOCX embedded OLE object present",
                    severity="high",
                )
            )
        if any(name.startswith("word/fonts/") for name in names):
            findings.append(
                _finding("docx_embedded_font", "word/fonts", "[present]", "DOCX embedded font present", severity="low")
            )
        for rel_name in sorted(name for name in names if name.endswith(".rels")):
            rel_xml = archive.read(rel_name)
            if b"TargetMode=\"External\"" in rel_xml or b"TargetMode='External'" in rel_xml:
                findings.append(
                    _finding(
                        "external_reference",
                        rel_name,
                        "[external target]",
                        "DOCX external relationship can leak tracking or remote content",
                        severity="high",
                    )
                )
        images = _collect_zip_images(
            archive,
            prefix="word/media/",
            source_type="docx_embedded_image",
            container_prefix=container_prefix,
        ) if image_scan_enabled else []
    return ContainerScanResult(blocks, _dedupe_findings(findings), image_candidates=images)


def _scan_xlsx(data: bytes, *, image_scan_enabled: bool, container_prefix: str) -> ContainerScanResult:
    with _zip_archive(data) as archive:
        _validate_zip(archive)
        names = set(archive.namelist())
        if "xl/workbook.xml" not in names:
            raise ContainerScanError("XLSX payload missing xl/workbook.xml")
        _refuse_macros(names)
        blocks, findings = _read_zip_text_parts(
            archive,
            matcher=_XLSX_TEXT_PART_RE,
            source="xlsx_hidden_content",
            detail="XLSX workbook, comments, hidden sheet, defined-name, or pivot-cache text is present",
        )
        workbook = _read_zip_member(archive, "xl/workbook.xml")
        if workbook:
            root = _safe_xml_root(workbook, label="xl/workbook.xml")
            for node in root.iter():
                sheet_hidden = str(node.attrib.get("state", "")).lower() in {"hidden", "veryhidden"}
                if _local_name(node.tag) == "sheet" and sheet_hidden:
                    findings.append(
                        _finding(
                            "xlsx_hidden_sheet",
                            "sheet",
                            node.attrib.get("name", ""),
                            "XLSX hidden sheet is present",
                            severity="high",
                        )
                    )
                if _local_name(node.tag) == "definedName" and (node.text or "").strip():
                    findings.append(
                        _finding(
                            "xlsx_defined_name",
                            node.attrib.get("name", "definedName"),
                            node.text,
                            "XLSX defined name can retain sensitive ranges",
                        )
                    )
        for name in sorted(names):
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                xml = archive.read(name)
                if b'hidden="1"' in xml or b"hidden='1'" in xml:
                    findings.append(
                        _finding(
                            "xlsx_hidden_row_col",
                            name,
                            "[hidden]",
                            "XLSX hidden row or column is present",
                            severity="medium",
                        )
                    )
        images = _collect_zip_images(
            archive,
            prefix="xl/media/",
            source_type="xlsx_embedded_image",
            container_prefix=container_prefix,
        ) if image_scan_enabled else []
    return ContainerScanResult(blocks, _dedupe_findings(findings), image_candidates=images)


def _scan_pptx(data: bytes, *, image_scan_enabled: bool, container_prefix: str) -> ContainerScanResult:
    with _zip_archive(data) as archive:
        _validate_zip(archive)
        names = set(archive.namelist())
        if "ppt/presentation.xml" not in names:
            raise ContainerScanError("PPTX payload missing ppt/presentation.xml")
        _refuse_macros(names)
        blocks, findings = _read_zip_text_parts(
            archive,
            matcher=_PPTX_TEXT_PART_RE,
            source="pptx_hidden_content",
            detail="PPTX slide, note, master, layout, or comment text is present",
        )
        for name in sorted(names):
            if name.startswith("ppt/notesSlides/"):
                findings.append(_finding("pptx_speaker_notes", name, "[present]", "PPTX speaker notes are present"))
            if name.startswith("ppt/slideMasters/"):
                findings.append(
                    _finding(
                        "pptx_slide_master",
                        name,
                        "[present]",
                        "PPTX slide master text is present",
                        severity="low",
                    )
                )
            if name.endswith(".xml") and b'show="0"' in archive.read(name)[:10000]:
                findings.append(
                    _finding(
                        "pptx_hidden_slide",
                        name,
                        "[hidden]",
                        "PPTX hidden slide flag is present",
                        severity="high",
                    )
                )
        images = _collect_zip_images(
            archive,
            prefix="ppt/media/",
            source_type="pptx_embedded_image",
            container_prefix=container_prefix,
        ) if image_scan_enabled else []
    return ContainerScanResult(blocks, _dedupe_findings(findings), image_candidates=images)


def _refuse_macros(names: set[str]) -> None:
    if any(name.lower().endswith("vbaproject.bin") for name in names):
        raise ContainerScanError("macro-enabled Office container refused by default")


def _scan_pdf(
    data: bytes,
    *,
    image_scan_enabled: bool,
    depth: int,
    container_prefix: str,
) -> ContainerScanResult:
    del image_scan_enabled
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise ContainerScanError("PDF container scan requires pypdf") from exc
    try:
        reader = PdfReader(BytesIO(data))
    except Exception as exc:
        raise ContainerScanError(f"PDF container parse failed: {exc}") from exc
    if getattr(reader, "is_encrypted", False):
        raise ContainerScanError("password-protected or encrypted PDF refused")
    result = ContainerScanResult()
    root = getattr(reader, "trailer", {}).get("/Root", {}) if hasattr(reader, "trailer") else {}
    root = root.get_object() if hasattr(root, "get_object") else root
    if _pdf_has_javascript(root):
        result.findings.append(
            _finding(
                "pdf_javascript",
                "JavaScript",
                "[present]",
                "PDF JavaScript action is present and refused",
                severity="high",
            )
        )
    form = _pdf_get(root, "/AcroForm")
    if form:
        result.findings.append(_finding("pdf_acroform", "AcroForm", "[present]", "PDF AcroForm fields are present"))
        result.text_blocks.extend(_pdf_form_text(form))
    embedded = _pdf_embedded_files(root)
    for name, payload in embedded:
        result.findings.append(
            _finding("pdf_embedded_file", name, "[embedded]", "PDF embedded file is present", severity="high")
        )
        nested_mime = infer_mime_type(name, payload)
        nested = _scan_by_type(
            payload,
            filename=name,
            mime_type=nested_mime,
            image_scan_enabled=True,
            depth=depth + 1,
            container_prefix=f"{container_prefix}/{name}" if container_prefix else name,
        )
        result.extend(nested, prefix=name)
    for page_index, page in enumerate(reader.pages):
        annots = _pdf_get(page, "/Annots") or []
        if hasattr(annots, "get_object"):
            annots = annots.get_object()
        for annot_ref in annots:
            annot = annot_ref.get_object() if hasattr(annot_ref, "get_object") else annot_ref
            values: list[str] = []
            for key in ("/Contents", "/T", "/Subj"):
                value = _pdf_get(annot, key)
                if value:
                    values.append(str(value))
            uri = _pdf_get(_pdf_get(annot, "/A") or {}, "/URI")
            if uri:
                result.findings.append(
                    _finding(
                        "external_reference",
                        f"page_{page_index + 1}",
                        uri,
                        "PDF URI action can leak external navigation",
                        severity="high",
                    )
                )
            if values:
                text = "\n".join(values)
                result.text_blocks.append(f"[PDF annotation page {page_index + 1}]\n{text}")
                result.findings.append(
                    _finding("pdf_annotation", f"page_{page_index + 1}", text, "PDF annotation text is present")
                )
    result.findings = _dedupe_findings(result.findings)
    return result


def _pdf_get(obj: Any, key: str) -> Any:
    try:
        value = obj.get(key)
    except Exception:
        return None
    return value.get_object() if hasattr(value, "get_object") else value


def _pdf_has_javascript(root: Any) -> bool:
    if not root:
        return False
    names = _pdf_get(root, "/Names")
    if names and _pdf_get(names, "/JavaScript"):
        return True
    open_action = _pdf_get(root, "/OpenAction")
    if open_action and (_pdf_get(open_action, "/JS") or _pdf_get(open_action, "/S") == "/JavaScript"):
        return True
    return False


def _pdf_form_text(form: Any) -> list[str]:
    blocks: list[str] = []
    fields = _pdf_get(form, "/Fields") or []
    for field_ref in fields:
        field = field_ref.get_object() if hasattr(field_ref, "get_object") else field_ref
        values: list[str] = []
        for key in ("/T", "/TU", "/V"):
            value = _pdf_get(field, key)
            if value:
                values.append(str(value))
        if values:
            blocks.append("[PDF form field]\n" + "\n".join(values))
    return blocks


def _pdf_embedded_files(root: Any) -> list[tuple[str, bytes]]:
    embedded: list[tuple[str, bytes]] = []
    names = _pdf_get(root, "/Names")
    embedded_files = _pdf_get(names or {}, "/EmbeddedFiles")
    raw_names = _pdf_get(embedded_files or {}, "/Names") or []
    for index in range(0, len(raw_names), 2):
        name = str(raw_names[index])
        raw_spec = raw_names[index + 1]
        spec = raw_spec.get_object() if hasattr(raw_spec, "get_object") else raw_spec
        ef = _pdf_get(spec, "/EF") or {}
        file_obj = _pdf_get(ef, "/F") or _pdf_get(ef, "/UF")
        if not file_obj:
            continue
        try:
            payload = file_obj.get_data()
        except Exception as exc:
            raise ContainerScanError(f"PDF embedded file {name} could not be read: {exc}") from exc
        embedded.append((name, bytes(payload)))
    return embedded


def _scan_zip_archive(
    data: bytes,
    *,
    image_scan_enabled: bool,
    depth: int,
    container_prefix: str,
) -> ContainerScanResult:
    result = ContainerScanResult()
    with _zip_archive(data) as archive:
        _validate_zip(archive)
        for info in archive.infolist():
            if info.is_dir():
                continue
            payload = archive.read(info.filename)
            mime_type = infer_mime_type(info.filename, payload)
            nested_prefix = f"{container_prefix}/{info.filename}" if container_prefix else info.filename
            nested = _scan_by_type(
                payload,
                filename=info.filename,
                mime_type=mime_type,
                image_scan_enabled=image_scan_enabled,
                depth=depth + 1,
                container_prefix=nested_prefix,
            )
            result.extend(nested, prefix=info.filename)
    return result


def _scan_tar_archive(
    data: bytes,
    *,
    image_scan_enabled: bool,
    depth: int,
    container_prefix: str,
) -> ContainerScanResult:
    result = ContainerScanResult()
    try:
        archive = tarfile.open(fileobj=BytesIO(data), mode="r:*")
    except tarfile.TarError as exc:
        raise ContainerScanError(f"TAR archive parse failed: {exc}") from exc
    with archive:
        members = archive.getmembers()
        if len(members) > MAX_ENTRIES:
            raise ContainerScanError(f"TAR archive has {len(members)} entries; maximum is {MAX_ENTRIES}")
        total = 0
        for member in members:
            _validate_member_path(member.name)
            if member.issym() or member.islnk():
                raise ContainerScanError(f"TAR link member refused: {member.name}")
            if not member.isfile():
                continue
            total += member.size
            if member.size > MAX_MEMBER_BYTES or total > MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise ContainerScanError("TAR archive uncompressed size exceeds safety cap")
            extracted = archive.extractfile(member)
            if extracted is None:
                continue
            payload = extracted.read(MAX_MEMBER_BYTES + 1)
            if len(payload) > MAX_MEMBER_BYTES:
                raise ContainerScanError(f"TAR member {member.name} exceeds safety cap")
            mime_type = infer_mime_type(member.name, payload)
            nested_prefix = f"{container_prefix}/{member.name}" if container_prefix else member.name
            nested = _scan_by_type(
                payload,
                filename=member.name,
                mime_type=mime_type,
                image_scan_enabled=image_scan_enabled,
                depth=depth + 1,
                container_prefix=nested_prefix,
            )
            result.extend(nested, prefix=member.name)
    return result


def _scan_eml(
    data: bytes,
    *,
    image_scan_enabled: bool,
    depth: int,
    container_prefix: str,
) -> ContainerScanResult:
    message = email.message_from_bytes(data, policy=policy.default)
    result = ContainerScanResult()
    for header in ("from", "to", "cc", "bcc", "subject", "reply-to"):
        value = message.get(header)
        if value:
            result.text_blocks.append(f"[Email {header}]\n{value}")
            result.findings.append(_finding("eml_header", header, value, "Email header can contain personal data"))
    for part in message.walk():
        if part.is_multipart():
            continue
        content_type = part.get_content_type()
        filename = part.get_filename() or ""
        payload = part.get_payload(decode=True) or b""
        disposition = str(part.get_content_disposition() or "")
        if content_type == "text/plain":
            result.text_blocks.append(part.get_content())
            continue
        if content_type == "text/html":
            result.extend(_scan_html(payload, source="eml_html"))
            continue
        if content_type.startswith("image/") and image_scan_enabled:
            path = filename or f"inline-image-{len(result.image_candidates)}"
            nested_path = f"{container_prefix}/{path}" if container_prefix else path
            result.image_candidates.append(
                ImageCandidate(
                    data=payload,
                    mime_type=content_type,
                    locator=ImageLocator(
                        container_path=nested_path,
                        image_index=len(result.image_candidates),
                        source_type="eml_inline_image" if disposition != "attachment" else "eml_attachment_image",
                    ),
                )
            )
            continue
        if filename:
            result.findings.append(
                _finding(
                    "eml_attachment",
                    filename,
                    content_type,
                    "Email attachment recursively scanned",
                    severity="medium",
                )
            )
            nested_mime = infer_mime_type(filename, payload)
            nested_prefix = f"{container_prefix}/{filename}" if container_prefix else filename
            nested = _scan_by_type(
                payload,
                filename=filename,
                mime_type=nested_mime,
                image_scan_enabled=image_scan_enabled,
                depth=depth + 1,
                container_prefix=nested_prefix,
            )
            result.extend(nested, prefix=filename)
    result.findings = _dedupe_findings(result.findings)
    return result


def _decode_text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _scan_html(data: bytes, *, source: str) -> ContainerScanResult:
    text = _decode_text(data)
    result = ContainerScanResult()
    for match in re.finditer(r"<!--(.*?)-->", text, flags=re.DOTALL):
        comment = html.unescape(match.group(1).strip())
        if comment:
            result.text_blocks.append(f"[HTML comment]\n{comment}")
            result.findings.append(
                _finding(source, "comment", comment, "HTML comment text is hidden from normal rendering")
            )
    for match in re.finditer(
        r"<(?P<tag>[A-Za-z0-9]+)\b(?P<attrs>[^>]*)style=['\"][^'\"]*display\s*:\s*none[^'\"]*['\"][^>]*>(?P<body>.*?)</(?P=tag)>",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        hidden = _strip_tags(match.group("body"))
        if hidden:
            result.text_blocks.append(f"[HTML display:none]\n{hidden}")
            result.findings.append(
                _finding(source, "display_none", hidden, "HTML display:none text is present", severity="high")
            )
    for attr, value in re.findall(
        r"\b(data-[\w:-]+|alt|title|aria-label)=['\"]([^'\"]+)['\"]",
        text,
        re.IGNORECASE,
    ):
        decoded = html.unescape(value)
        if decoded.strip():
            result.text_blocks.append(f"[HTML attribute {attr}]\n{decoded}")
            result.findings.append(
                _finding(source, attr, decoded, "HTML attribute text can contain hidden reviewable data")
            )
    visible = _strip_tags(re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL))
    if visible:
        result.text_blocks.append(visible)
    result.findings = _dedupe_findings(result.findings)
    return result


def _strip_tags(text: str) -> str:
    stripped = re.sub(r"<script\b.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    stripped = re.sub(r"<style\b.*?</style>", " ", stripped, flags=re.IGNORECASE | re.DOTALL)
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    stripped = html.unescape(stripped)
    stripped = re.sub(r"\s+", " ", stripped)
    return stripped.strip()


def _scan_svg(data: bytes) -> ContainerScanResult:
    root = _safe_xml_root(data, label="svg")
    blocks: list[str] = []
    findings: list[ContainerFinding] = []
    for node in root.iter():
        local = _local_name(node.tag)
        text = (node.text or "").strip()
        if local in {"metadata", "title", "desc", "text"} and text:
            blocks.append(f"[SVG {local}]\n{text}")
            findings.append(_finding("svg_hidden_content", local, text, "SVG text/metadata is reviewable content"))
    return ContainerScanResult(blocks, _dedupe_findings(findings))


def _scan_rtf(data: bytes) -> ContainerScanResult:
    text = _decode_text(data)
    findings: list[ContainerFinding] = []
    if r"\object" in text:
        findings.append(
            _finding("rtf_object", "object", "[present]", "RTF embedded object marker is present", severity="high")
        )
    if r"\pict" in text:
        findings.append(
            _finding("rtf_picture", "pict", "[present]", "RTF embedded picture marker is present", severity="medium")
        )
    plain = re.sub(r"\\'[0-9a-fA-F]{2}", " ", text)
    plain = re.sub(r"\\[A-Za-z]+-?\d* ?", " ", plain)
    plain = plain.replace("{", " ").replace("}", " ")
    plain = re.sub(r"\s+", " ", plain).strip()
    return ContainerScanResult([plain] if plain else [], findings)


def _scan_markdown(data: bytes) -> ContainerScanResult:
    text = _decode_text(data)
    result = ContainerScanResult(text_blocks=[text])
    for comment in re.findall(r"<!--(.*?)-->", text, flags=re.DOTALL):
        if comment.strip():
            result.findings.append(
                _finding(
                    "markdown_comment",
                    "comment",
                    comment,
                    "Markdown HTML comment is hidden from normal rendering",
                )
            )
    for alt in re.findall(r"!\[([^\]]+)\]\([^)]+\)", text):
        result.text_blocks.append(f"[Markdown image alt]\n{alt}")
        result.findings.append(
            _finding("markdown_image_alt", "alt", alt, "Markdown image alt text is reviewable content")
        )
    return result


def _check_magic_bytes(data: bytes, *, filename: str, mime_type: str) -> None:
    if mime_type in {DOCX_MIME, XLSX_MIME, PPTX_MIME, *ZIP_MIMES} and not data.startswith(b"PK\x03\x04"):
        raise ContainerScanError(f"magic-byte mismatch for ZIP-based document {filename}")
    if mime_type == PDF_MIME and not data.lstrip().startswith(b"%PDF"):
        raise ContainerScanError(f"magic-byte mismatch for PDF document {filename}")
    if mime_type in TAR_MIMES:
        return
    if mime_type in SVG_MIMES and b"<svg" not in data[:2048].lower():
        raise ContainerScanError(f"magic-byte mismatch for SVG document {filename}")
    if mime_type in RTF_MIMES and not data.lstrip().startswith(b"{\\rtf"):
        raise ContainerScanError(f"magic-byte mismatch for RTF document {filename}")
