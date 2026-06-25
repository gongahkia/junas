from __future__ import annotations

import email
import html
import re
import zipfile
from dataclasses import dataclass
from email import policy
from io import BytesIO
from typing import Any
from xml.etree import ElementTree


@dataclass(frozen=True)
class StructuralUnit:
    kind: str
    start_char: int
    end_char: int
    text: str
    line_start: int
    line_end: int
    parent_index: int | None = None


@dataclass(frozen=True)
class DocumentStructure:
    text: str
    units: tuple[StructuralUnit, ...]

    def containing_span(self, start: int, end: int) -> StructuralUnit | None:
        candidates = [
            unit
            for unit in self.units
            if unit.start_char <= start and end <= unit.end_char and unit.kind != "document"
        ]
        if not candidates:
            return self.units[0] if self.units else None
        return min(candidates, key=lambda unit: (unit.end_char - unit.start_char, unit.start_char))

    def siblings(self, unit: StructuralUnit) -> tuple[StructuralUnit, ...]:
        return tuple(
            candidate
            for candidate in self.units
            if candidate is not unit
            and candidate.parent_index == unit.parent_index
            and candidate.kind == unit.kind
        )

    def nearby_units(self, start: int, end: int, *, max_distance: int = 1) -> tuple[StructuralUnit, ...]:
        unit = self.containing_span(start, end)
        if unit is None:
            return ()
        try:
            index = self.units.index(unit)
        except ValueError:
            return (unit,)
        left = max(0, index - max_distance)
        right = min(len(self.units), index + max_distance + 1)
        return self.units[left:right]


_HEADING_RE = re.compile(
    r"^(?:#{1,6}\s+\S|[A-Z][A-Z0-9 /&(),.'-]{5,}$|\d+(?:\.\d+)*[.)]\s+\S)"
)
_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)]|[a-zA-Z][.)])\s+\S")
_SIGNATURE_RE = re.compile(
    r"^\s*(?:signature|signed\s+by|authori[sz]ed\s+signatory|name|title|date)\s*[:#-]?",
    re.IGNORECASE,
)
_DEFINED_TERM_RE = re.compile(
    r'^\s*(?:"[^"]{2,80}"|“[^”]{2,80}”|[A-Z][A-Za-z0-9 /&().,\'-]{2,80})\s+means\b',
    re.IGNORECASE,
)
_DEFINITIONS_HEADING_RE = re.compile(r"^\s*(?:definitions|interpretation)\s*$", re.IGNORECASE)
_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_DRAWING_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_PRESENTATION_NS = "{http://schemas.openxmlformats.org/presentationml/2006/main}"


def _clean_block(text: str) -> str:
    text = html.unescape(str(text or "")).replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _structure_from_blocks(blocks: list[tuple[str, str, int | None]]) -> DocumentStructure:
    parts: list[str] = []
    units: list[StructuralUnit] = []
    offset = 0
    line_no = 1
    for kind, raw_text, parent_index in blocks:
        text = _clean_block(raw_text)
        if not text:
            continue
        if parts:
            parts.append("\n")
            offset += 1
            line_no += 1
        start = offset
        parts.append(text)
        units.append(
            StructuralUnit(
                kind=kind,
                start_char=start,
                end_char=start + len(text),
                text=text,
                line_start=line_no,
                line_end=line_no + text.count("\n"),
                parent_index=parent_index,
            )
        )
        offset += len(text)
        line_no += text.count("\n")
    text = "".join(parts)
    document = StructuralUnit(
        kind="document",
        start_char=0,
        end_char=len(text),
        text=text,
        line_start=1,
        line_end=max(1, text.count("\n") + 1),
        parent_index=None,
    )
    shifted_units: list[StructuralUnit] = []
    for unit in units:
        parent = unit.parent_index
        if parent is not None:
            parent += 1
        shifted_units.append(
            StructuralUnit(
                kind=unit.kind,
                start_char=unit.start_char,
                end_char=unit.end_char,
                text=unit.text,
                line_start=unit.line_start,
                line_end=unit.line_end,
                parent_index=parent,
            )
        )
    return DocumentStructure(text=text, units=(document, *shifted_units))


def _word_attr(node: ElementTree.Element, name: str) -> str:
    return str(node.attrib.get(f"{_WORD_NS}{name}") or node.attrib.get(name) or "")


def _docx_paragraph_text(paragraph: ElementTree.Element) -> str:
    parts: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{_WORD_NS}t":
            parts.append(node.text or "")
        elif node.tag == f"{_WORD_NS}tab":
            parts.append("\t")
        elif node.tag in {f"{_WORD_NS}br", f"{_WORD_NS}cr"}:
            parts.append("\n")
    return "".join(parts).strip()


def _docx_paragraph_style(paragraph: ElementTree.Element) -> str:
    p_pr = paragraph.find(f"{_WORD_NS}pPr")
    if p_pr is None:
        return ""
    style = p_pr.find(f"{_WORD_NS}pStyle")
    return _word_attr(style, "val") if style is not None else ""


def _docx_has_numbering(paragraph: ElementTree.Element) -> bool:
    p_pr = paragraph.find(f"{_WORD_NS}pPr")
    return p_pr is not None and p_pr.find(f"{_WORD_NS}numPr") is not None


def _docx_paragraph_kind(text: str, style: str, numbered: bool) -> str:
    style_key = re.sub(r"\s+", "", style).casefold()
    stripped = text.strip()
    if style_key.startswith("toc"):
        return "toc_reference"
    if style_key.startswith("heading") or style_key in {"title", "subtitle"}:
        return "heading"
    if numbered or style_key in {"listparagraph", "bulletlist", "numberedlist"}:
        return "list_item"
    if _DEFINITIONS_HEADING_RE.match(stripped) or _HEADING_RE.match(stripped):
        return "heading"
    if _DEFINED_TERM_RE.match(stripped):
        return "defined_term"
    if _SIGNATURE_RE.match(stripped):
        return "signature_block"
    if _LIST_RE.match(stripped):
        return "list_item"
    return "paragraph"


def parse_docx_structure(data: bytes) -> DocumentStructure:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        try:
            document_xml = archive.read("word/document.xml")
        except KeyError as exc:
            raise ValueError("DOCX payload missing word/document.xml") from exc

    root = ElementTree.fromstring(document_xml)
    body = root.find(f"{_WORD_NS}body")
    if body is None:
        body = root

    units: list[StructuralUnit] = []
    parts: list[str] = []
    offset = 0
    line_no = 1
    heading_index: int | None = None

    def append_separator() -> None:
        nonlocal offset, line_no
        if parts:
            parts.append("\n")
            offset += 1
            line_no += 1

    def add_unit(
        *,
        kind: str,
        text: str,
        parent_index: int | None,
        start_offset: int | None = None,
        line_start: int | None = None,
    ) -> int | None:
        nonlocal offset, line_no
        body_text = text.strip()
        if not body_text:
            return None
        start = offset if start_offset is None else start_offset
        unit_line_start = line_no if line_start is None else line_start
        unit = StructuralUnit(
            kind=kind,
            start_char=start,
            end_char=start + len(body_text),
            text=body_text,
            line_start=unit_line_start,
            line_end=unit_line_start + body_text.count("\n"),
            parent_index=parent_index,
        )
        units.append(unit)
        return len(units) - 1

    for child in list(body):
        if child.tag == f"{_WORD_NS}p":
            text = _docx_paragraph_text(child)
            if not text:
                continue
            append_separator()
            kind = _docx_paragraph_kind(text, _docx_paragraph_style(child), _docx_has_numbering(child))
            parent = 0 if kind == "heading" else heading_index
            index = add_unit(kind=kind, text=text, parent_index=parent)
            parts.append(text)
            offset += len(text)
            if kind == "heading" and index is not None:
                heading_index = index
        elif child.tag == f"{_WORD_NS}tbl":
            for row in child.findall(f".//{_WORD_NS}tr"):
                cell_texts: list[str] = []
                for cell in row.findall(f"{_WORD_NS}tc"):
                    paragraphs = [
                        _docx_paragraph_text(paragraph)
                        for paragraph in cell.findall(f".//{_WORD_NS}p")
                    ]
                    cell_text = " ".join(part for part in paragraphs if part).strip()
                    if cell_text:
                        cell_texts.append(cell_text)
                if not cell_texts:
                    continue
                append_separator()
                row_text = " | ".join(cell_texts)
                row_start = offset
                row_line = line_no
                row_index = add_unit(
                    kind="table_row",
                    text=row_text,
                    parent_index=heading_index,
                    start_offset=row_start,
                    line_start=row_line,
                )
                cursor = row_start
                for cell_text in cell_texts:
                    add_unit(
                        kind="table_cell",
                        text=cell_text,
                        parent_index=row_index,
                        start_offset=cursor,
                        line_start=row_line,
                    )
                    cursor += len(cell_text) + 3
                parts.append(row_text)
                offset += len(row_text)

    text = "".join(parts)
    document = StructuralUnit(
        kind="document",
        start_char=0,
        end_char=len(text),
        text=text,
        line_start=1,
        line_end=max(1, text.count("\n") + 1),
        parent_index=None,
    )
    shifted_units: list[StructuralUnit] = []
    for unit in units:
        parent = unit.parent_index
        if parent is not None and not (unit.kind == "heading" and parent == 0):
            parent += 1
        shifted_units.append(
            StructuralUnit(
                kind=unit.kind,
                start_char=unit.start_char,
                end_char=unit.end_char,
                text=unit.text,
                line_start=unit.line_start,
                line_end=unit.line_end,
                parent_index=parent,
            )
        )
    return DocumentStructure(text=text, units=(document, *shifted_units))


def _xml_root(xml_bytes: bytes, *, label: str) -> ElementTree.Element:
    prefix = xml_bytes[:4096].lower()
    if b"<!doctype" in prefix or b"<!entity" in prefix:
        raise ValueError(f"unsafe XML DTD/entity declaration in {label}")
    return ElementTree.fromstring(xml_bytes)


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = _xml_root(archive.read("xl/sharedStrings.xml"), label="xl/sharedStrings.xml")
    out: list[str] = []
    for item in root.findall(f".//{_SHEET_NS}si"):
        out.append("".join(node.text or "" for node in item.findall(f".//{_SHEET_NS}t")))
    return out


def _cell_value(cell: ElementTree.Element, shared: list[str]) -> str:
    value = cell.find(f"{_SHEET_NS}v")
    inline = cell.find(f".//{_SHEET_NS}t")
    if inline is not None and inline.text:
        return inline.text
    if value is None or value.text is None:
        return ""
    raw = value.text
    if cell.attrib.get("t") == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError):
            return ""
    return raw


def parse_xlsx_structure(data: bytes) -> DocumentStructure:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        names = set(archive.namelist())
        if "xl/workbook.xml" not in names:
            raise ValueError("XLSX payload missing xl/workbook.xml")
        shared = _shared_strings(archive)
        blocks: list[tuple[str, str, int | None]] = []
        sheet_parent: int | None = None
        workbook = _xml_root(archive.read("xl/workbook.xml"), label="xl/workbook.xml")
        sheet_names = [
            str(node.attrib.get("name") or "").strip()
            for node in workbook.iter()
            if node.tag.endswith("}sheet") and str(node.attrib.get("name") or "").strip()
        ]
        if sheet_names:
            blocks.append(("workbook", "Workbook: " + ", ".join(sheet_names), None))
        for node in workbook.iter():
            if node.tag.endswith("}definedName") and (node.text or "").strip():
                blocks.append(("defined_name", node.text or "", None))
        for index, name in enumerate(sorted(n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))):
            label = sheet_names[index] if index < len(sheet_names) else name.rsplit("/", 1)[-1]
            sheet_parent = len(blocks)
            blocks.append(("sheet", f"Sheet: {label}", None))
            root = _xml_root(archive.read(name), label=name)
            for row in root.findall(f".//{_SHEET_NS}row"):
                cells = [_cell_value(cell, shared).strip() for cell in row.findall(f"{_SHEET_NS}c")]
                values = [value for value in cells if value]
                if values:
                    blocks.append(("table_row", " | ".join(values), sheet_parent))
                    row_parent = len(blocks) - 1
                    for value in values:
                        blocks.append(("table_cell", value, row_parent))
        used_shared = {
            _cell_value(cell, shared).strip()
            for name in names
            if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
            for cell in _xml_root(archive.read(name), label=name).findall(f".//{_SHEET_NS}c")
            if _cell_value(cell, shared).strip()
        }
        unused_shared = [value for value in shared if value.strip() and value.strip() not in used_shared]
        if unused_shared:
            blocks.append(("shared_strings", "\n".join(unused_shared), None))
        for name in sorted(n for n in names if n.startswith("xl/comments") and n.endswith(".xml")):
            text = "\n".join(
                node.text or ""
                for node in _xml_root(archive.read(name), label=name).iter()
                if node.tag.endswith("}t") and node.text
            )
            blocks.append(("comment", text, None))
        for name in sorted(n for n in names if n.startswith("xl/pivotCache/") and n.endswith(".xml")):
            root = _xml_root(archive.read(name), label=name)
            text = "\n".join(
                value
                for node in root.iter()
                for value in ((node.text or "").strip(), str(node.attrib.get("v") or "").strip())
                if value
            )
            blocks.append(("pivot_cache", text, None))
    return _structure_from_blocks(blocks)


def _pptx_text(xml_bytes: bytes, *, label: str) -> str:
    root = _xml_root(xml_bytes, label=label)
    parts = [node.text or "" for node in root.iter() if node.tag in {f"{_DRAWING_NS}t", f"{_PRESENTATION_NS}text"}]
    return "\n".join(part.strip() for part in parts if part and part.strip())


def parse_pptx_structure(data: bytes) -> DocumentStructure:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        names = set(archive.namelist())
        if "ppt/presentation.xml" not in names:
            raise ValueError("PPTX payload missing ppt/presentation.xml")
        blocks: list[tuple[str, str, int | None]] = []
        matchers = (
            (r"ppt/slides/slide\d+\.xml", "slide"),
            (r"ppt/notesSlides/notesSlide\d+\.xml", "speaker_notes"),
            (r"ppt/comments/comment\d+\.xml", "comment"),
            (r"ppt/slideMasters/slideMaster\d+\.xml", "slide_master"),
            (r"ppt/slideLayouts/slideLayout\d+\.xml", "slide_layout"),
        )
        for pattern, kind in matchers:
            for name in sorted(n for n in names if re.fullmatch(pattern, n)):
                text = _pptx_text(archive.read(name), label=name)
                if text:
                    blocks.append((kind, f"[{name}]\n{text}", None))
    return _structure_from_blocks(blocks)


def _strip_html(text: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_eml_structure(data: bytes) -> DocumentStructure:
    message = email.message_from_bytes(data, policy=policy.default)
    blocks: list[tuple[str, str, int | None]] = []
    for header in ("from", "to", "cc", "bcc", "subject", "reply-to"):
        value = message.get(header)
        if value:
            blocks.append(("email_header", f"{header}: {value}", None))
    for part in message.walk():
        if part.is_multipart():
            continue
        content_type = part.get_content_type()
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if content_type == "text/plain":
            text = part.get_content()
            blocks.append(("email_body", text, None))
        elif content_type == "text/html":
            blocks.append(("email_html_body", _strip_html(payload.decode("utf-8", errors="replace")), None))
        elif filename:
            label = f"Attachment: {filename} ({content_type})"
            if content_type.startswith("text/"):
                body = payload.decode("utf-8", errors="replace")
                blocks.append(("email_attachment", f"{label}\n{body}", None))
            else:
                blocks.append(("email_attachment", label, None))
    return _structure_from_blocks(blocks)


def _pdf_get(obj: Any, key: str) -> Any:
    try:
        value = obj.get(key)
    except Exception:
        return None
    return value.get_object() if hasattr(value, "get_object") else value


def _pdf_form_blocks(form: Any) -> list[str]:
    fields = _pdf_get(form, "/Fields") or []
    out: list[str] = []
    for field_ref in fields:
        field = field_ref.get_object() if hasattr(field_ref, "get_object") else field_ref
        values = [str(value) for key in ("/T", "/TU", "/V") if (value := _pdf_get(field, key))]
        if values:
            out.append("\n".join(values))
    return out


def parse_pdf_structure(data: bytes) -> DocumentStructure:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise ValueError("PDF structure parsing requires pypdf") from exc
    reader = PdfReader(BytesIO(data))
    if getattr(reader, "is_encrypted", False):
        raise ValueError("password-protected or encrypted PDF refused")
    blocks: list[tuple[str, str, int | None]] = []
    root = getattr(reader, "trailer", {}).get("/Root", {}) if hasattr(reader, "trailer") else {}
    root = root.get_object() if hasattr(root, "get_object") else root
    form = _pdf_get(root, "/AcroForm")
    if form:
        for value in _pdf_form_blocks(form):
            blocks.append(("form_field", value, None))
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            blocks.append(("page", text, None))
        annots = _pdf_get(page, "/Annots") or []
        if hasattr(annots, "get_object"):
            annots = annots.get_object()
        for annot_ref in annots:
            annot = annot_ref.get_object() if hasattr(annot_ref, "get_object") else annot_ref
            values = [str(value) for key in ("/Contents", "/T", "/Subj") if (value := _pdf_get(annot, key))]
            if values:
                blocks.append(("annotation", "\n".join(values), None))
    return _structure_from_blocks(blocks)


def parse_document_structure(text: str) -> DocumentStructure:
    units: list[StructuralUnit] = [
        StructuralUnit(
            kind="document",
            start_char=0,
            end_char=len(text),
            text=text,
            line_start=1,
            line_end=max(1, text.count("\n") + 1),
            parent_index=None,
        )
    ]
    heading_index: int | None = 0
    paragraph_start: int | None = None
    paragraph_lines: list[tuple[int, int, int]] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_start, paragraph_lines
        if paragraph_start is None or not paragraph_lines:
            paragraph_start = None
            paragraph_lines = []
            return
        start = paragraph_start
        end = paragraph_lines[-1][1]
        body = text[start:end].strip()
        if body:
            units.append(
                StructuralUnit(
                    kind="paragraph",
                    start_char=start,
                    end_char=end,
                    text=text[start:end],
                    line_start=paragraph_lines[0][2],
                    line_end=paragraph_lines[-1][2],
                    parent_index=heading_index,
                )
            )
        paragraph_start = None
        paragraph_lines = []

    offset = 0
    for line_no, line in enumerate(text.splitlines(keepends=True), start=1):
        line_start = offset
        line_end = offset + len(line)
        stripped = line.strip()
        content_end = line_end - (len(line) - len(line.rstrip("\r\n")))
        offset = line_end

        if not stripped:
            flush_paragraph()
            continue

        kind: str | None = None
        if _DEFINITIONS_HEADING_RE.match(stripped) or _HEADING_RE.match(stripped):
            kind = "heading"
        elif _DEFINED_TERM_RE.match(stripped):
            kind = "defined_term"
        elif _SIGNATURE_RE.match(stripped):
            kind = "signature_block"
        elif _LIST_RE.match(stripped):
            kind = "list_item"
        elif "|" in stripped and stripped.count("|") >= 2:
            kind = "table_row"

        if kind:
            flush_paragraph()
            parent = heading_index if kind != "heading" else 0
            units.append(
                StructuralUnit(
                    kind=kind,
                    start_char=line_start + (len(line) - len(line.lstrip())),
                    end_char=content_end,
                    text=text[line_start:content_end],
                    line_start=line_no,
                    line_end=line_no,
                    parent_index=parent,
                )
            )
            if kind == "heading":
                heading_index = len(units) - 1
            continue

        if paragraph_start is None:
            paragraph_start = line_start
            paragraph_lines = []
        paragraph_lines.append((line_start, content_end, line_no))

    flush_paragraph()
    return DocumentStructure(text=text, units=tuple(units))
