from __future__ import annotations

import re
from dataclasses import dataclass


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
