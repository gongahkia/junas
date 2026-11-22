"""Person-name candidates anchored by roles, personal fields or linked contacts."""

from __future__ import annotations

import re
from bisect import bisect_left, bisect_right

from junas.review.conjunctive_mnpi import ORG_NAME_RE

TOKEN = r"[^\W\d_]{1,40}(?:[’'-][^\W\d_]{1,40}){0,2}"
TOKENS = re.compile(rf"\b{TOKEN}\b")
ORG_WORD = re.compile(
    r"\b(?:Ltd|Limited|Pte|Corp|Inc|LLC|LLP|Holdings|Group|Services|Team|Department|"
    r"Advisory|Systems|Infrastructure|Secretariat|Bank|Legal|Notice|Memorandum|Singapore|"
    r"Government|Board|Company|Corporate|Client|Intake|General|Date|Private|Email|Ref|File|"
    r"Payroll|Operations|Service|Desk)\b",
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
        if text[start:end].endswith(("’s", "'s")):
            end -= 2
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
    org_starts = [a for a, _ in orgs]

    def in_org(a: int, b: int) -> bool:
        index = bisect_right(org_starts, a) - 1
        return index >= 0 and b <= orgs[index][1]

    candidates = [(a, b) for a, b in candidates if not in_org(a, b)]
    starts = [m.start() for m in tokens]
    occupied = set()
    for a, b in candidates + orgs:
        occupied.update(range(bisect_left(starts, a), bisect_left(starts, b)))
    aliases = set()
    for value in {text[a:b] for a, b in candidates}:
        parts = tuple(m.group() for m in TOKENS.finditer(value))
        for width in range(1, len(parts) + 1):
            for offset in range(len(parts) - width + 1):
                aliases.add(parts[offset : offset + width])
    # scan tokens once; repeated names must not trigger repeated full-document searches.
    for i in range(len(tokens)):
        if i in occupied:
            continue
        for width in range(min(5, len(tokens) - i), 0, -1):
            run = tokens[i : i + width]
            if any(j in occupied for j in range(i, i + width)):
                continue
            values = tuple(m.group()[:-2] if m.group().endswith(("’s", "'s")) else m.group() for m in run)
            if values not in aliases or any(
                not re.fullmatch(r"[ \t]+", text[x.end() : y.start()]) for x, y in zip(run, run[1:])
            ):
                continue
            a, b = run[0].start(), run[-1].end()
            if text[a:b].endswith(("’s", "'s")):
                b -= 2
            if width == 1 and not (
                re.search(r"\b(?:names?|named|contact is)\s*$", text[max(0, a - 25) : a], re.I)
                or HONORIFIC.search(text[max(0, a - 10) : a])
                or re.match(r"(?:[’']s\b|\s+(?:says|holds|asked|requested|works|submitted)\b)", text[b:])
            ):
                continue
            candidates.append((a, b))
            occupied.update(range(i, i + width))
            break
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
    ]
