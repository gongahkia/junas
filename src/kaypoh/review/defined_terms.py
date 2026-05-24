"""Extract contract-defined terms so downstream entity rules can suppress them.

Legal contracts repeatedly use terms like `the "Purchaser"`, `the "Vendor"`, or `the "Company"`
as stand-ins for actual parties. A naive PERSON/ORG detector will flag these tokens as named
entities and false-positive. We parse the contract's own defined-terms block once per document
and let the engine suppress later candidates whose matched text equals a defined term.
"""

from __future__ import annotations

import re


# matches the two most common defined-term introduction patterns:
#   (the "Purchaser") | ("Vendor") | (collectively, the "Sellers")
#   "Company" means | "Buyer" shall mean | "Parties" has the meaning
_DEFINED_TERM_PATTERN = re.compile(
    r'\(\s*(?:the\s+|collectively,?\s+(?:the\s+)?)?["“‘]([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)["”’]\s*\)'
    r'|["“‘]([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)["”’]\s+(?:means|shall\s+mean|has\s+the\s+meaning|refers\s+to|will\s+mean)',
    re.IGNORECASE,
)

# honorifics to strip when comparing a named_person match against the defined-term set.
# kept here (not in entity_linker) so suppression has no cross-module coupling at import time.
_HONORIFIC_PREFIX = re.compile(r"^(?:mr|ms|mrs|mdm|dr|prof|sir|dame)\.?\s+", re.IGNORECASE)


def extract_defined_terms(text: str) -> set[str]:
    """Return casefolded defined terms parsed from contract preamble patterns."""
    terms: set[str] = set()
    for match in _DEFINED_TERM_PATTERN.finditer(text):
        for group in match.groups():
            if group:
                terms.add(group.strip().casefold())
    return terms


def is_defined_term(matched_text: str, defined_terms: set[str]) -> bool:
    """True when matched_text or its honorific-stripped form is a defined term."""
    if not defined_terms or not matched_text:
        return False
    cleaned = _HONORIFIC_PREFIX.sub("", matched_text).strip().casefold()
    return cleaned in defined_terms
