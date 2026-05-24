"""Canonical-form helpers so entity variants collapse to a single anonymisation key.

`Dr Jane Tan`, `Jane Tan`, and (when explicitly anchored) `Tan` should share one `[PERSON_1]`.
`ACME Pte. Ltd.`, `Acme`, and `Acme Limited` should share one `[ORG_1]`. The fuzzy work is
intentionally deterministic: strip honorifics and corporate suffixes, normalise punctuation
and whitespace, casefold. No NER, no embeddings, no ML.
"""

from __future__ import annotations

import re


_HONORIFIC = re.compile(r"^(?:mr|ms|mrs|mdm|dr|prof|sir|dame)\.?\s+", re.IGNORECASE)

# common corporate suffixes across SG, SEA, US, UK, EU, JP. anchored at the trailing edge of
# the matched text after honorific strip + whitespace normalisation.
_CORP_SUFFIX = re.compile(
    r"\s*[,.]?\s*(?:"
    r"pte\.?\s+ltd\.?|pvt\.?\s+ltd\.?|sdn\.?\s+bhd\.?|"
    r"limited|ltd\.?|incorporated|inc\.?|corporation|corp\.?|company|co\.?|"
    r"llc|llp|plc|gmbh|s\.a\.|s\.a\.s\.|n\.v\.|b\.v\.|ag|k\.k\.|kabushiki\s+kaisha"
    r")\s*$",
    re.IGNORECASE,
)

_PUNCT_AND_SPACE = re.compile(r"[\s\.,&]+")


def strip_honorific(text: str) -> str:
    """Remove a leading honorific (`Dr `, `Mrs.`, etc.) from a person name."""
    return _HONORIFIC.sub("", text).strip()


def canonical_person(text: str) -> str:
    """Canonical key for PERSON variants: strip honorific + collapse punctuation + casefold."""
    return _PUNCT_AND_SPACE.sub(" ", strip_honorific(text)).strip().casefold()


def canonical_org(text: str) -> str:
    """Canonical key for ORG variants: strip corporate suffix + collapse punctuation + casefold."""
    stripped = _CORP_SUFFIX.sub("", text).strip()
    return _PUNCT_AND_SPACE.sub(" ", stripped).strip().casefold()
