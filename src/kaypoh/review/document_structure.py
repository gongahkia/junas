from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
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
