from __future__ import annotations

import re
from typing import Any, Callable

PERSONAL_ATTRIBUTE_RELATION_RE = re.compile(
    r"\b(?P<subject>(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})"
    r"'?s\s+(?P<attribute>wife|husband|spouse|partner|son|daughter|child|father|mother)\s+"
    r"(?P<object>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b"
)
PERSONAL_ATTRIBUTE_DIRECTED_RELATION_RE = re.compile(
    r"\b(?P<subject>(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+"
    r"(?P<attribute>reports\s+to|is\s+supervised\s+by|is\s+guardian\s+for|is\s+the\s+guardian\s+of|"
    r"is\s+emergency\s+contact\s+for|is\s+beneficial\s+owner\s+of)\s+"
    r"(?P<object>(?:(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4}|"
    r"[A-Z][A-Za-z0-9&.,' -]{2,80})\b",
    re.IGNORECASE,
)
PERSONAL_ATTRIBUTE_EMPLOYER_RE = re.compile(
    r"\b(?P<subject>(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+"
    r"(?:works\s+at|is\s+employed\s+by|is\s+seconded\s+to|joined)\s+"
    r"(?P<object>[A-Z][A-Za-z0-9&.,' -]{2,80})\b"
)
PERSONAL_ATTRIBUTE_LOCATION_RE = re.compile(
    r"\b(?P<subject>(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+"
    r"(?:lives\s+in|resides\s+in|is\s+based\s+in)\s+"
    r"(?P<object>[A-Z][A-Za-z0-9&.,' -]{2,80})\b"
)
PERSONAL_ATTRIBUTE_OCCUPATION_RE = re.compile(
    r"\b(?P<subject>(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+"
    r"(?:works\s+as|serves\s+as|is\s+employed\s+as|has\s+the\s+job\s+title\s+of|"
    r"holds\s+the\s+role\s+of|is\s+(?:an?\s+)?)"
    r"\s+(?P<object>[A-Z][A-Za-z0-9&.,' -]{0,60}\b(?:officer|director|manager|engineer|"
    r"lawyer|solicitor|doctor|nurse|accountant|analyst|partner|consultant|teacher|"
    r"professor|actuary|architect|secretary|counsel|trader|broker|developer|specialist))\b",
    re.IGNORECASE,
)
PERSONAL_ATTRIBUTE_EDUCATION_RE = re.compile(
    r"\b(?P<subject>(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+"
    r"(?:is\s+)?(?:enrolled\s+at|studies\s+at|graduated\s+from|attends)\s+"
    r"(?P<object>[A-Z][A-Za-z0-9&.,' -]{2,80})\b"
)
PERSONAL_ATTRIBUTE_NATIONALITY_RE = re.compile(
    r"\b(?P<subject>(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+"
    r"(?:is\s+(?:a\s+)?|holds\s+)(?P<object>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+"
    r"(?:citizen|national|citizenship|nationality|passport\s+holder))\b"
)
PERSONAL_ATTRIBUTE_LICENSE_RE = re.compile(
    r"\b(?P<subject>(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+"
    r"(?:holds|has|maintains)\s+(?:an?\s+)?(?P<object>[A-Z][A-Za-z' -]{2,40}\s+"
    r"(?:licen[cs]e|registration|practising\s+certificate))\b",
    re.IGNORECASE,
)
PERSONAL_ATTRIBUTE_DEPARTMENT_RE = re.compile(
    r"\b(?P<subject>(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+"
    r"(?:(?:works\s+in|is\s+assigned\s+to)\s+|reports\s+to\s+(?!(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+))"
    r"(?P<object>[A-Z][A-Za-z0-9&.,' -]{2,80})\b"
)
PERSONAL_ATTRIBUTE_SENIORITY_RE = re.compile(
    r"\b(?P<subject>(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+"
    r"(?:is\s+(?:a\s+)?|was\s+promoted\s+to\s+)(?P<object>(?:junior|senior|principal|lead|head\s+of|"
    r"specialist|consultant|associate|partner|director)[A-Za-z0-9&.,' -]{0,60})\b",
    re.IGNORECASE,
)


def _trim_inferred_attribute_span(text: str, start: int, end: int) -> tuple[int, int]:
    line_end = text.find("\n", start, end)
    if line_end >= 0:
        end = line_end
    while end > start and text[end - 1] in " \t;:":
        end -= 1
    return start, end


def detect_personal_attribute_inferences(
    text: str,
    *,
    jurisdiction: str,
    legal_basis: str,
    idx_start: int,
    document_structure: Any,
    new_finding: Callable[..., Any],
) -> list[Any]:
    out: list[Any] = []
    idx = idx_start
    specs = (
        (
            PERSONAL_ATTRIBUTE_RELATION_RE,
            "relationship",
            "Family or relationship attribute inferred from a named-person statement",
        ),
        (
            PERSONAL_ATTRIBUTE_DIRECTED_RELATION_RE,
            "relationship",
            "Directed relationship attribute inferred from a named-person statement",
        ),
        (PERSONAL_ATTRIBUTE_EMPLOYER_RE, "employer", "Employment attribute inferred from a named-person statement"),
        (
            PERSONAL_ATTRIBUTE_LOCATION_RE,
            "location",
            "Location/residence attribute inferred from a named-person statement",
        ),
        (
            PERSONAL_ATTRIBUTE_OCCUPATION_RE,
            "occupation",
            "Occupation or job-title attribute inferred from a named-person statement",
        ),
        (
            PERSONAL_ATTRIBUTE_EDUCATION_RE,
            "education",
            "Education/student attribute inferred from a named-person statement",
        ),
        (
            PERSONAL_ATTRIBUTE_NATIONALITY_RE,
            "nationality",
            "Citizenship or nationality attribute inferred from a named-person statement",
        ),
        (
            PERSONAL_ATTRIBUTE_LICENSE_RE,
            "professional_license",
            "Professional licence attribute inferred from a named-person statement",
        ),
        (
            PERSONAL_ATTRIBUTE_DEPARTMENT_RE,
            "department",
            "Department or team attribute inferred from a named-person statement",
        ),
        (
            PERSONAL_ATTRIBUTE_SENIORITY_RE,
            "seniority",
            "Seniority or specialty attribute inferred from a named-person statement",
        ),
    )
    for pattern, attribute_type, reason in specs:
        for match in pattern.finditer(text):
            attribute = match.group("attribute") if "attribute" in match.groupdict() else ""
            inferred_value = match.group("object").strip(" \t,.;:")
            if (
                pattern is PERSONAL_ATTRIBUTE_DIRECTED_RELATION_RE
                and re.search(r"\b(?:team|department|committee|board|unit|division|office)\b", inferred_value, re.I)
            ):
                continue
            start, end = _trim_inferred_attribute_span(text, match.start(), match.end())
            if end <= start:
                continue
            unit = document_structure.containing_span(start, end)
            metadata: dict[str, Any] = {
                "attribute_type": attribute_type,
                "subject": match.group("subject"),
                "inferred_value": inferred_value,
            }
            if attribute_type == "relationship":
                metadata["relation_type"] = re.sub(r"\s+", "_", attribute.strip().casefold())
            if unit is not None:
                metadata.update(
                    {
                        "structural_unit_kind": unit.kind,
                        "structural_unit_line_start": unit.line_start,
                        "structural_unit_line_end": unit.line_end,
                    }
                )
            out.append(
                new_finding(
                    idx=idx,
                    category="PII",
                    rule="personal_attribute_inference",
                    jurisdiction=jurisdiction,
                    severity="medium",
                    matched_text=text[start:end],
                    start=start,
                    end=end,
                    reason=reason,
                    legal_basis=legal_basis,
                    metadata=metadata,
                )
            )
            idx += 1
    return out
