"""Person-name candidates anchored by roles, personal fields or linked contacts."""

from __future__ import annotations

import re

from junas.review.conjunctive_mnpi import ORG_NAME_RE

TOKEN = r"[^\W\d_]{1,40}(?:[’'-][^\W\d_]{1,40}){0,2}"
TOKENS = re.compile(rf"\b{TOKEN}\b")
ORG_WORD = re.compile(
    r"\b(?:Ltd|Limited|Pte|Corp|Inc|LLC|LLP|Holdings|Group|Services|Team|Department|"
    r"Advisory|Systems|Infrastructure|Secretariat|Bank|Legal|Notice|Memorandum|Singapore|"
    r"Government|Board|Company|Corporate|Client|Intake|General|Date|Private|Email|Ref|File)\b",
    re.I,
)
PREFIX = re.compile(
    r"\b(?:name|client|applicant|beneficiary|claimant|patient|account holder|contact person|"
    r"employee name|client name|from|to|board queries|issuer contact|backup contact)\s*:\s*$|"
    r"\b(?:Mr|Mrs|Ms|Mdm|Dr|Prof)\.?\s+$|"
    r"\b(?:director|shareholder|employee|patient|customer|client|beneficiary|claimant|"
    r"company secretary|registry liaison|contact|applicant)\s+(?:as\s+)?$",
    re.I,
)
SUFFIX = re.compile(
    r"^\s*\(\s*(?:NRIC|FIN|passport|staff|employee|client|customer|register|holder|"
    r"portal|secretariat|collection|correspondence|internal contact|contact record|email|"
    r"[\w.+-]+@[\w.-]+)\b|^\s*,\s*(?:Company Secretary|director|employee)\b|"
    r"^\s+(?:requested|submitted|asked|entered|confirmed|reported|seeks|holds|says|works)\b",
    re.I,
)
NONPERSON_FIELD = re.compile(r"\b(?:company|corporate|issuer|organization|department|fund)\s+name\s*:\s*$", re.I)
HONORIFIC = re.compile(r"\b(?:Mr|Mrs|Ms|Mdm|Dr|Prof)\.?\s*$", re.I)
LEADING = frozenset(
    {
        "The",
        "An",
        "A",
        "Mr",
        "Mrs",
        "Ms",
        "Mdm",
        "Dr",
        "Prof",
        "Director",
        "Shareholder",
        "Employee",
        "Client",
        "Patient",
        "Customer",
        "Applicant",
        "Beneficiary",
    }
)


def _capital(token: str) -> bool:
    return token[0].isupper() or (not token.isascii() and token.lower() == token.upper())


def person_names(text: str) -> list[dict]:
    tokens = list(TOKENS.finditer(text))
    candidates = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if not _capital(token.group()) or token.group() in LEADING:
            i += 1
            continue
        run = [token]
        j = i + 1
        while j < len(tokens) and len(run) < 5 and _capital(tokens[j].group()):
            gap = text[run[-1].end() : tokens[j].start()]
            if not gap or not re.fullmatch(r"[ \t]+", gap):
                break
            run.append(tokens[j])
            j += 1
        start, end = run[0].start(), run[-1].end()
        value = text[start:end]
        prefix, suffix = text[max(0, start - 65) : start], text[end : end + 100]
        if (
            not ORG_WORD.search(value)
            and not NONPERSON_FIELD.search(prefix)
            and (PREFIX.search(prefix) or (len(run) >= 2 and SUFFIX.search(suffix)))
        ):
            candidates.append((start, end))
        i = max(i + 1, j)
    orgs = [
        (line.start() + m.start(), line.start() + m.end())
        for line in re.finditer(r"[^\n]+", text)
        for m in ORG_NAME_RE.finditer(line.group())
    ]
    anchored = list(candidates)
    # shortened references must be grounded in an already anchored full name.
    for start, end in anchored:
        parts = list(TOKENS.finditer(text[start:end]))
        for width in range(1, len(parts) + 1):
            for offset in range(len(parts) - width + 1):
                name = text[start + parts[offset].start() : start + parts[offset + width - 1].end()]
                for match in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text):
                    a, b = match.span()
                    if any(x <= a and b <= y for x, y in candidates + orgs):
                        continue
                    # single-token mentions need an honorific, possessive or personal action.
                    if width == 1 and not (
                        HONORIFIC.search(text[max(0, a - 10) : a])
                        or re.match(r"(?:[’']s\b|\s+(?:says|holds|asked|requested|works|submitted)\b)", text[b:])
                    ):
                        continue
                    candidates.append((a, b))
    return [
        dict(
            label="PERSON_NAME",
            rule="contextual_person_name",
            start_char=a,
            end_char=b,
            matched_text=text[a:b],
            reason="person field, role, contact or anchored shortened reference",
        )
        for a, b in sorted(set(candidates))
        if not any(x <= a and b <= y for x, y in orgs)
    ]
