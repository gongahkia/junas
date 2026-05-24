"""Per-finding statute-cited rationales for the /review and /anonymize suggestion field.

Each suggestion's `rationale` should be forwardable verbatim by a compliance reviewer to
internal audit. The text below names the statutory hook (PDPA, SFA, GDPR, MAR, Reg FD…) so
the reviewer is not the one editorialising — they're attaching a system-generated artefact
that already cites the underlying rule.

References here are intentionally short and load-bearing. They are not legal advice.
"""

from __future__ import annotations

from typing import Iterable


# rule -> short PII rationale used when no jurisdiction-specific override applies.
_PII_DEFAULT_RATIONALE = {
    "sg_nric_fin": (
        "PDPA s13 and PDPC NRIC Advisory (effective 31 Dec 2026): NRIC/FIN must not be "
        "collected, used, or disclosed without explicit purpose and consent. Mask before send."
    ),
    "sg_uen": (
        "UEN paired with named individuals can re-identify directors/officers. Mask unless "
        "the recipient and purpose are documented under PDPA s18 (notification of purpose)."
    ),
    "sg_postal_address": (
        "PDPA s2 personal data includes residential address. Disclose only when the purpose "
        "is documented and consented."
    ),
    "email_address": (
        "PDPA s2 personal data includes work/personal email. Mask unless the recipient is "
        "intended and the purpose is documented."
    ),
    "phone_number": (
        "PDPA s2 personal data includes phone number. Mask unless the recipient is intended "
        "and the purpose is documented."
    ),
    "passport_number": (
        "PDPA s2 + PDPC NRIC Advisory: passport-like identifiers must not be disclosed "
        "without explicit purpose and consent. Mask before send."
    ),
    "bank_account": (
        "Bank account / IBAN / SWIFT references are financial identifiers. Mask unless the "
        "disclosure is to the bona-fide counterparty and the purpose is documented."
    ),
    "named_person": (
        "Named persons are personal data under PDPA s2. For counterparty principals in a "
        "definitive agreement, treat as high sensitivity and mask before any external send."
    ),
}

# rule -> short MNPI rationale (the citation is jurisdiction-specific so we layer on a suffix)
_MNPI_DEFAULT_RATIONALE = {
    "material_event": (
        "Material corporate-event language detected. Confirm public-disclosure status before "
        "sending; if not yet public, hold until announcement."
    ),
    "nonpublic_marker": (
        "Explicit non-public / confidentiality marker detected. Treat the surrounding passage "
        "as MNPI unless the marker has been formally lifted."
    ),
    "financial_amount": (
        "Specific monetary value may be material non-public information. Verify the value is "
        "publicly disclosed; otherwise generalise or redact."
    ),
    "financial_percentage": (
        "Specific percentage figure may be material non-public information. Verify the value "
        "is publicly disclosed; otherwise generalise or redact."
    ),
    "large_number": (
        "Large numeric value may be material non-public information. Verify or generalise."
    ),
}

# jurisdiction-pack -> statute suffix appended to PII rationales for that jurisdiction.
_PII_JURISDICTION_SUFFIX = {
    "SG": "Reference: Personal Data Protection Act 2012.",
    "SEA": "Reference: ASEAN cross-border privacy baseline.",
    "EU": "Reference: GDPR Article 4 (personal data) and Article 5 (data-minimisation principle).",
    "UK": "Reference: UK GDPR Article 4 and the UK Data Protection Act 2018.",
    "US": "Reference: applicable US sectoral privacy law (state-level + sector-specific).",
}

# jurisdiction-pack -> MNPI statute suffix.
_MNPI_JURISDICTION_SUFFIX = {
    "SG": "Reference: Securities and Futures Act 2001 ss215, 218, 219 (insider trading / "
    "generally available information).",
    "SEA": "Reference: ASEAN-baseline market-abuse principles.",
    "US": "Reference: SEC insider-trading guidance and Regulation FD (selective disclosure).",
    "UK": "Reference: UK Market Abuse Regulation (UK MAR) Article 7 (inside information).",
    "EU": "Reference: EU Market Abuse Regulation (EU MAR) Article 7 (inside information).",
}


def _split_jurisdictions(jurisdiction_field: str) -> list[str]:
    return [code.strip() for code in jurisdiction_field.split("+") if code.strip()]


def _join_suffixes(codes: Iterable[str], lookup: dict[str, str]) -> str:
    seen: set[str] = set()
    parts: list[str] = []
    for code in codes:
        suffix = lookup.get(code)
        if suffix and suffix not in seen:
            parts.append(suffix)
            seen.add(suffix)
    return " ".join(parts)


def pii_rationale(*, rule: str, jurisdiction: str) -> str:
    base = _PII_DEFAULT_RATIONALE.get(
        rule,
        "Personal data should be masked unless the recipient and purpose are documented.",
    )
    suffix = _join_suffixes(_split_jurisdictions(jurisdiction), _PII_JURISDICTION_SUFFIX)
    return f"{base} {suffix}".strip()


def mnpi_rationale(*, rule: str, jurisdiction: str, severity: str) -> str:
    base = _MNPI_DEFAULT_RATIONALE.get(
        rule,
        "Material non-public information detected. Hold until publicly disclosed or generalise the claim.",
    )
    suffix = _join_suffixes(_split_jurisdictions(jurisdiction), _MNPI_JURISDICTION_SUFFIX)
    if severity == "low":
        # public-context evidence already detected; soften the directive but keep the citation.
        base = base.rstrip(".") + " — appears public; verify the disclosing source before relying on it."
    return f"{base} {suffix}".strip()
