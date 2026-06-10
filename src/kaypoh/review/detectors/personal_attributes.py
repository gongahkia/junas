from __future__ import annotations

import re
from typing import Any, Callable

_PERSON_NAME = (
    r"(?:[A-Z][a-z]+(?:[-\u2010-\u2015][A-Z][a-z]+)?"
    r"(?:\s+[A-Z][a-z]+(?:[-\u2010-\u2015][A-Z][a-z]+)?){1,3})"
)
_PERSONAL_ATTRIBUTE_SUBJECT_FP_RE = re.compile(
    r"\b(?:Project|Company|Limited|Pte|Ltd|LLC|Inc|Corp|Holdings|Capital|Fund|Trust|Bank)\b"
)
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
PERSONAL_ATTRIBUTE_ROLE_APPOSITIVE_RE = re.compile(
    r"\b(?P<subject>" + _PERSON_NAME + r")\s*,\s*"
    r"(?P<object>(?:(?:Chief\s+(?:Executive|Financial|Operating|Technology|Risk|Compliance)\s+Officer)|"
    r"General\s+Counsel|CFO|CEO|COO|CTO|CRO|CCO|Partner|Director|Manager|Actuary|Engineer|"
    r"Solicitor|Lawyer|Counsel|Doctor|Nurse|Analyst|Trader|Broker|Developer|Specialist)"
    r"(?:\s+(?:at|of|with)\s+[A-Z][A-Za-z0-9&.,' -]{2,80})?)\b",
    re.IGNORECASE,
)
PERSONAL_ATTRIBUTE_EMPLOYER_APPOSITIVE_RE = re.compile(
    r"\b(?P<subject>" + _PERSON_NAME + r")\s+(?P<attribute>of|from|with)\s+"
    r"(?P<object>[A-Z][A-Za-z0-9&.,' -]{2,80}?\b(?:Pte\s+Ltd|Ltd|Limited|LLC|Inc|Corp|Bank|"
    r"University|Hospital|Authority|Ministry|LLP|LP))\b",
)
PERSONAL_ATTRIBUTE_LOCATION_APPOSITIVE_RE = re.compile(
    r"\b(?P<subject>" + _PERSON_NAME + r")\s*,?\s+(?:resident\s+of|residing\s+in|based\s+in|domiciled\s+in)\s+"
    r"(?P<object>[A-Z][A-Za-z0-9&.,' -]{2,80})\b",
    re.IGNORECASE,
)
PERSONAL_ATTRIBUTE_SPECIAL_CATEGORY_RE = re.compile(
    r"\b(?P<subject>(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+"
    r"(?P<attribute>was\s+diagnosed\s+with|is\s+diagnosed\s+with|is\s+treated\s+for|"
    r"identifies\s+as|is\s+a\s+member\s+of|has\s+a\s+genetic\s+marker\s+for|"
    r"uses\s+a\s+fingerprint\s+template\s+for)\s+"
    r"(?P<object>[A-Z]?[A-Za-z0-9&.,' /+-]{2,80})\b",
    re.IGNORECASE,
)
SPECIAL_CATEGORY_ATTRIBUTE_RE = re.compile(
    r"\b(?:diagnosed\s+with|treated\s+for|takes\s+(?:insulin|metformin|sertraline)|"
    r"has\s+(?:diabetes|cancer|depression|HIV|Parkinson'?s|Alzheimer'?s|stroke)|"
    r"member\s+of\s+.+?\b(?:union|party)|"
    r"identifies\s+as\s+(?:gay|lesbian|bisexual|transgender)|ethnic\s+(?:Malay|Chinese|Indian)|"
    r"(?:fingerprint|iris|voiceprint|genetic|DNA|BRCA1|BRCA2|APOE|HLA[-\s]B|pathogenic\s+variant))\b",
    re.IGNORECASE,
)


def _trim_inferred_attribute_span(text: str, start: int, end: int) -> tuple[int, int]:
    line_end = text.find("\n", start, end)
    if line_end >= 0:
        end = line_end
    while end > start and text[end - 1] in " \t;:":
        end -= 1
    return start, end


def _special_category_attribute_type(value: str, full_match: str) -> str:
    probe = f"{value} {full_match}"
    if re.search(
        r"\b(?:diagnosed|treated|insulin|metformin|sertraline|diabetes|cancer|depression|HIV|"
        r"Parkinson'?s|Alzheimer'?s|stroke)\b",
        probe,
        re.I,
    ):
        return "health"
    if re.search(r"\b(?:union|party)\b", probe, re.I):
        return "political_or_union"
    if re.search(r"\b(?:gay|lesbian|bisexual|transgender)\b", probe, re.I):
        return "sexual_orientation"
    if re.search(r"\bethnic\b", probe, re.I):
        return "racial_ethnic_origin"
    if re.search(r"\b(?:fingerprint|iris|voiceprint)\b", probe, re.I):
        return "biometric"
    if re.search(r"\b(?:genetic|DNA|BRCA1|BRCA2|APOE|HLA[-\s]B|pathogenic\s+variant)\b", probe, re.I):
        return "genetic"
    return ""


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
        (
            PERSONAL_ATTRIBUTE_ROLE_APPOSITIVE_RE,
            "occupation",
            "Occupation or job-title attribute inferred from a named-person appositive",
        ),
        (
            PERSONAL_ATTRIBUTE_EMPLOYER_APPOSITIVE_RE,
            "employer",
            "Employer attribute inferred from a named-person appositive",
        ),
        (
            PERSONAL_ATTRIBUTE_LOCATION_APPOSITIVE_RE,
            "location",
            "Location/residence attribute inferred from a named-person appositive",
        ),
        (
            PERSONAL_ATTRIBUTE_SPECIAL_CATEGORY_RE,
            "special_category",
            "Special-category attribute inferred from a named-person statement",
        ),
    )
    for pattern, attribute_type, reason in specs:
        for match in pattern.finditer(text):
            if _PERSONAL_ATTRIBUTE_SUBJECT_FP_RE.search(match.group("subject")):
                continue
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
            special_type = _special_category_attribute_type(inferred_value, text[start:end])
            severity = "high" if special_type else "medium"
            if special_type:
                metadata["special_category_attribute"] = True
                metadata["special_category_type"] = special_type
            out.append(
                new_finding(
                    idx=idx,
                    category="PII",
                    rule="personal_attribute_inference",
                    jurisdiction=jurisdiction,
                    severity=severity,
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
