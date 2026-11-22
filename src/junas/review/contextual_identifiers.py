"""Explicit person-linked fields, including sparse synthetic evaluation strata."""

from __future__ import annotations

import re

FIELD_PATTERNS = {
    "BANK_ACCOUNT": re.compile(
        r"(?i:\b(?:personal\s+)?bank\s+account\s*(?:number|no\.?|ID)?\s*[:#=]\s*)"
        r"(?P<value>[A-Z]{0,2}\d(?:[A-Z0-9 -]{3,30}[A-Z0-9]))\b"
    ),
    "GOVERNMENT_ID": re.compile(
        r"(?i:\b(?:passport|national\s+ID|NRIC|FIN|taxpayer\s+ID)\s*(?:number|no\.?)?\s*[:#=]\s*)"
        r"(?P<value>[A-Z0-9][A-Z0-9-]{4,19})\b"
    ),
    "PHONE": re.compile(
        r"(?i:\b(?:personal\s+(?:mobile|phone)|mobile|telephone|direct\s+(?:line|extension))\s*(?:number)?\s*[:#=]?\s*)"
        r"(?P<value>\+?\d[\d ()-]{1,20}\d)\b"
    ),
    "POSTAL_ADDRESS": re.compile(
        r"(?i:\b(?:home|residential|mailing|correspondence)\s+address\s*[:=]\s*)"
        r"(?P<value>\d[^\n;]{5,100})"
    ),
}
LINK = re.compile(
    r"\b(?:personal|individual|employee|patient|customer|client|resident|staff|holder|home|residential)\b", re.I
)
BUSINESS = re.compile(r"\b(?:company|corporate|business|office|public|hotline)\b", re.I)
QUASI_FIELDS = (
    re.compile(r"\bAge\s*:\s*\d{1,3}\b", re.I),
    re.compile(r"\b(?:postcode|postal code)\s*:\s*[A-Z0-9 -]{3,10}\b", re.I),
    re.compile(r"\b(?:occupation|job title)\s*:\s*[^;\n.]{2,50}", re.I),
)


def identifier_fields(text: str) -> list[dict]:
    spans = []
    for label, pattern in FIELD_PATTERNS.items():
        for match in pattern.finditer(text):
            value = match.group("value").rstrip()
            line = text[
                text.rfind("\n", 0, match.start()) + 1 : text.find("\n", match.end())
                if "\n" in text[match.end() :]
                else len(text)
            ]
            context = text[max(0, match.start() - 100) : match.end()]
            if BUSINESS.search(line) or (label in {"BANK_ACCOUNT", "PHONE"} and not LINK.search(context)):
                continue
            if label == "GOVERNMENT_ID" and not any(c.isdigit() for c in value):
                continue
            if label == "PHONE" and not 3 <= sum(c.isdigit() for c in value) <= 15:
                continue
            if label == "BANK_ACCOUNT" and not 6 <= sum(c.isdigit() for c in value) <= 22:
                continue
            start, end = match.start("value"), match.start("value") + len(value)
            spans.append(
                dict(
                    label=label,
                    rule="contextual_" + label.lower(),
                    start_char=start,
                    end_char=end,
                    matched_text=text[start:end],
                    reason="explicit personal field context",
                )
            )
    for block in re.finditer(r"[^\n]+", text):
        value = block.group()
        fields = [p.search(value) for p in QUASI_FIELDS]
        if all(fields) and LINK.search(value) and re.search(r"\b(?:only|unique|identif\w+)\b", value, re.I):
            matches = [m for m in fields if m is not None]
            start = block.start() + min(m.start() for m in matches)
            end = block.start() + max(m.end() for m in matches)
            spans.append(
                dict(
                    label="QUASI_IDENTIFIER_COMBINATION",
                    rule="contextual_quasi_identifier",
                    start_char=start,
                    end_char=end,
                    matched_text=text[start:end],
                    reason="three quasi-identifier fields with explicit singling-out claim; unverified",
                )
            )
    return spans
