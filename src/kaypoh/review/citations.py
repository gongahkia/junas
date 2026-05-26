"""Per-finding statute-cited rationales for the /review and /anonymize suggestion field.

Each suggestion's `rationale` should be forwardable verbatim by a compliance reviewer to
internal audit. The text below names the statutory hook (PDPA, SFA, GDPR, MAR, Reg FD…) so
the reviewer is not the one editorialising — they're attaching a system-generated artefact
that already cites the underlying rule.

References here are intentionally short and load-bearing. They are not legal advice.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import tomllib

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
    # SEA jurisdictional ID rationales — kept short and statute-cited so the audit-pack
    # artefact stays scannable. Customers can override via KAYPOH_CITATIONS_OVERRIDE.
    "my_mykad": (
        "Malaysia MyKad is sensitive personal data under PDPA Malaysia 2010 sections 6-7. "
        "Mask unless explicit consent and documented purpose are on file."
    ),
    "id_nik": (
        "Indonesia NIK is civil-registry personal data under UU PDP 27/2022 articles 4-10. "
        "Disclose only with explicit consent and a documented lawful basis."
    ),
    "th_national_id": (
        "Thailand 13-digit national identifier is personal data under PDPA B.E. 2562 (2019) "
        "section 26. Mask unless lawful-basis documentation is on file."
    ),
    "ph_philsys": (
        "Philippines PhilSys PSN is sensitive personal information under the Data Privacy "
        "Act of 2012 (RA 10173) section 3(l). Mask unless explicit consent is on record."
    ),
    "ph_tin": (
        "Philippines TIN is a government-issued identifier classified as personal "
        "information under RA 10173. Mask unless tax-administration purpose is documented."
    ),
    "vn_cccd": (
        "Vietnam CCCD is personal data under Decree 13/2023/ND-CP articles 2-3. Mask "
        "unless explicit consent and documented purpose are on file."
    ),
    "hk_hkid": (
        "Hong Kong Identity Card number is personal data under PDPO Cap. 486 section 2. "
        "Mask unless collection/use is necessary for the documented purpose."
    ),
    "hk_cr_no": (
        "Hong Kong company / business registration identifiers can identify transaction "
        "parties and sole proprietors. Mask where the recipient and purpose are not documented."
    ),
    "au_tfn": (
        "Australian TFNs are high-risk government identifiers. Mask unless TFN handling is "
        "strictly required and authorised for the documented purpose."
    ),
    "au_abn": (
        "Australian ABNs identify entities and can identify sole traders. Mask unless the "
        "recipient and business purpose are documented."
    ),
    "au_acn": (
        "Australian ACNs identify registered companies. Mask in private deal context unless "
        "the recipient and purpose are documented."
    ),
    "jp_my_number": (
        "Japan My Number / Individual Number is a restricted identifier under the Number Act "
        "and personal information under APPI. Mask unless statutory handling authority is on file."
    ),
    "jp_corporate_number": (
        "Japan Corporate Number identifies legal entities and deal counterparties. Mask in "
        "private matter context unless disclosure is intended and documented."
    ),
    "kr_rrn": (
        "Korean resident registration numbers are restricted identifiers under PIPA Article "
        "24-2. Mask unless explicit statutory authority and purpose are documented."
    ),
    "kr_business_registration": (
        "Korean business registration numbers identify business counterparties. Mask in "
        "private deal context unless recipient and purpose are documented."
    ),
    "us_ssn": (
        "US Social Security Number is a high-risk federal identifier. Mask unless the "
        "disclosure is to a federally-authorised recipient and the purpose is documented "
        "(e.g. payroll, tax filing). State privacy law and HIPAA/GLBA sectoral rules apply."
    ),
    "us_ein": (
        "US Employer Identification Number identifies entities and may identify sole "
        "proprietors. Mask in private deal context unless the recipient and purpose are "
        "documented."
    ),
    "uk_nin": (
        "UK National Insurance Number is a restricted government identifier. Mask unless "
        "the recipient is statutorily authorised (HMRC, employer) and the purpose is "
        "documented under UK GDPR Art 6 lawful basis."
    ),
    "jp_postal_code": (
        "Japan postal codes can re-identify residential addresses when combined with name "
        "or building references. Mask unless the recipient and purpose are documented "
        "under APPI Art 18."
    ),
    "au_postal_address": (
        "Australian state + postcode pairings can re-identify residential addresses "
        "(combined with street/suburb). Treat as personal information under Privacy Act "
        "1988 APP 6 unless disclosure is authorised."
    ),
    "sg_paynow": (
        "Singapore PayNow identifier pairs a payee recipient with their UEN / NRIC / "
        "mobile number. Treat as sensitive disclosure under PDPA s13 + MAS PaymentServices "
        "Act 2019 + the PayNow service-provider undertakings. Mask before any external send."
    ),
    "sg_mas_licence": (
        "Singapore MAS-issued capital markets services (CMS) or financial adviser (FA) "
        "licence number identifies a regulated entity. Mask in private deal context "
        "unless the recipient and purpose are documented under the Securities and Futures "
        "Act 2001 / Financial Advisers Act 2001 disclosure framework."
    ),
    "sg_sgx_counter": (
        "SGX counter / cashtag identifies a listed issuer. Public information, but "
        "association with a counterparty / deal codename in a pre-send memo signals an "
        "embargo-window MNPI surface under SFA s218 (insider trading) and SGX Mainboard "
        "Rule 703 (continuous disclosure)."
    ),
    "employee_id": (
        "Employee identifier is pseudonymised-but-linkable personal data: the employer "
        "retains the re-identification key linking the ID to a named individual. GDPR "
        "Recital 26 + PDPC Anonymisation Advisory Guidelines treat such data as personal "
        "data when the controller can re-link. Mask before any external send unless "
        "internal-HR purpose is documented."
    ),
    "customer_account_number": (
        "Customer / member account identifier is pseudonymised-but-linkable personal data. "
        "GDPR Recital 26 + PDPC Anonymisation Advisory Guidelines apply when the "
        "organisation retains the linking key. Mask unless the recipient and purpose are "
        "documented under PDPA s18 / GDPR Art 6."
    ),
    "medical_record_number": (
        "Medical record number / patient identifier is special-category personal data "
        "linkable to a patient. HIPAA 45 CFR §164.514 (de-identification) + GDPR Art 9 "
        "(health data) + PDPC special-category guidance. Mask unless statutory authority "
        "and purpose are on file."
    ),
    "quasi_identifier_combination": (
        "Three or more distinct quasi-identifiers co-occur within a 500-character window. "
        "Under PDPA s2 ('identified from that data and other information'), GDPR Recital "
        "26 ('means reasonably likely to be used'), and CCPA §1798.140(v) ('reasonably "
        "capable of being associated'), the combination is personal data even when the "
        "individual attributes are not. Sweeney 2000: DOB + 5-digit ZIP + gender uniquely "
        "identifies ~87% of US adults. Generalise or aggregate before disclosure."
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
    "transaction_codename": (
        "Internal deal codename detected. Treat as MNPI until the underlying transaction is "
        "publicly announced; do not reference the codename in external communications."
    ),
    "definitive_agreement": (
        "Definitive-agreement reference detected (SPA / SHA / APA / MOU / term sheet). "
        "Existence of a binding deal document is itself MNPI before public announcement."
    ),
    "material_adverse_change": (
        "Material adverse change / effect language detected. MAC/MAE clauses are price-sensitive "
        "and signal MNPI-grade context; hold until disclosed."
    ),
    "embargo_marker": (
        "Embargo / signing-date / closing-date marker detected. Treat the surrounding passage as "
        "MNPI until the embargo lifts."
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
    "contingent_mnpi_language": (
        "Contingent / forward-looking language detected. Under Basic v. Levinson (US), "
        "SFA s215 (SG), and MAR Art 7(2-3) (EU/UK), probabilistic / hedged statements "
        "about a corporate event can be MNPI when materiality × probability is significant. "
        "Treat as MNPI when adjacent to a deal substrate (codename, definitive agreement, "
        "material event, MAC clause, embargo marker)."
    ),
    "tipping_language": (
        "Forwarding / distribution language detected. Under SFA s219 (SG), Rule 10b5-2 (US), "
        "MAR Art 14 (EU/UK), and SFO Part XIV (HK), passing on MNPI is co-extensive with "
        "trading on it. If the surrounding passage contains MNPI, confirm recipient "
        "authorisation before forwarding or distributing."
    ),
    "selective_disclosure_risk": (
        "Selective-disclosure language detected (Reg FD trigger). 17 CFR 243.100 prohibits "
        "issuers (or persons acting on their behalf) from disclosing material non-public "
        "information to brokers/dealers, investment advisers / 13F filers, investment "
        "companies, or holders of the issuer's securities reasonably foreseeable to trade, "
        "without simultaneous (intentional) or prompt (unintentional) public disclosure. "
        "If the surrounding passage contains MNPI, ensure simultaneous public disclosure or "
        "obtain a Reg FD §100(b)(2) confidentiality undertaking from the recipient."
    ),
}

# jurisdiction-pack -> statute suffix appended to PII rationales for that jurisdiction.
_PII_JURISDICTION_SUFFIX = {
    "SG": "Reference: Personal Data Protection Act 2012.",
    "SEA": "Reference: ASEAN cross-border privacy baseline.",
    "EU": "Reference: GDPR Article 4 (personal data) and Article 5 (data-minimisation principle).",
    "UK": "Reference: UK GDPR Article 4 and the UK Data Protection Act 2018.",
    "US": "Reference: applicable US sectoral privacy law (state-level + sector-specific).",
    "MY": "Reference: Malaysia Personal Data Protection Act 2010.",
    "ID": "Reference: Indonesia UU Perlindungan Data Pribadi (UU PDP) No. 27/2022.",
    "TH": "Reference: Thailand Personal Data Protection Act B.E. 2562 (2019).",
    "PH": "Reference: Philippines Data Privacy Act of 2012 (RA 10173).",
    "VN": "Reference: Vietnam Personal Data Protection Decree 13/2023/ND-CP.",
    "HK": "Reference: Hong Kong Personal Data (Privacy) Ordinance (Cap. 486) section 2.",
    "AU": "Reference: Australia Privacy Act 1988 and Australian Privacy Principles.",
    "JP": "Reference: Japan APPI Article 2 and My Number Act handling restrictions.",
    "KR": "Reference: Korea Personal Information Protection Act Articles 2 and 24-2.",
}

# jurisdiction-pack -> MNPI statute suffix.
_MNPI_JURISDICTION_SUFFIX = {
    "SG": "Reference: Securities and Futures Act 2001 ss215, 218, 219 (insider trading / "
    "generally available information).",
    "SEA": "Reference: ASEAN-baseline market-abuse principles.",
    "US": "Reference: SEC insider-trading guidance and Regulation FD (selective disclosure).",
    "UK": "Reference: UK Market Abuse Regulation (UK MAR) Article 7 (inside information).",
    "EU": "Reference: EU Market Abuse Regulation (EU MAR) Article 7 (inside information).",
    "MY": "Reference: Capital Markets and Services Act 2007 ss188-189 (insider trading).",
    "ID": "Reference: OJK capital-market disclosure regulation and Indonesia Law on Capital "
    "Market UU 8/1995 articles 95-99.",
    "TH": "Reference: Thailand Securities and Exchange Act B.E. 2535 ss241-243.",
    "PH": "Reference: Philippines Securities Regulation Code (RA 8799) section 27.",
    "VN": "Reference: Vietnam Law on Securities 2019 Article 12 (prohibited acts).",
    "HK": "Reference: Securities and Futures Ordinance (Cap. 571) Part XIV ss270-281.",
    "AU": "Reference: Corporations Act 2001 (Cth) ss1042A-1043O.",
    "JP": "Reference: Financial Instruments and Exchange Act Articles 166-167.",
    "KR": "Reference: Financial Investment Services and Capital Markets Act Articles 174-179.",
}


# customer override hook. an internal compliance team can point KAYPOH_CITATIONS_OVERRIDE at a
# `citations_override.toml` that re-routes (rule, jurisdiction) pairs to internal policy
# citations instead of the built-in PDPA/SFA/GDPR/MAR/Reg-FD references. consulted before the
# built-in lookup, so it can substitute *and* extend.
#
# TOML schema:
#     [pii.sg_nric_fin]
#     SG = "Internal Compliance Manual §4.2 — NRIC handling"
#     default = "Substitute citation when no jurisdiction-specific override is present"
#
#     [mnpi.transaction_codename]
#     SG = "Internal Trading Policy §7 — Deal codenames"
#
# The `default` key is consulted when no per-jurisdiction key matches the rationale's
# jurisdiction. Falls through to the built-in if no override key matches.
_CITATIONS_OVERRIDE_CACHE: dict[Path, tuple[dict[str, dict[str, dict[str, str]]], float]] = {}


class CitationOverrideError(ValueError):
    """Raised when configured citation overrides cannot be resolved safely."""


def _load_citations_override_path(path: Path) -> dict[str, dict[str, dict[str, str]]]:
    if not path.exists():
        raise CitationOverrideError(f"citation override file does not exist: {path}")
    try:
        stat = path.stat()
    except OSError as exc:
        raise CitationOverrideError(f"citation override file is not readable: {path}") from exc
    mtime = stat.st_mtime
    cached = _CITATIONS_OVERRIDE_CACHE.get(path)
    if cached and cached[1] == mtime:
        return cached[0]
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise CitationOverrideError(f"citation override TOML is malformed: {path}: {exc}") from exc
    except OSError as exc:
        raise CitationOverrideError(f"citation override file is not readable: {path}") from exc
    if not isinstance(raw, dict):
        raise CitationOverrideError(f"citation override TOML root must be a table: {path}")
    normalized: dict[str, dict[str, dict[str, str]]] = {"pii": {}, "mnpi": {}}
    for category in ("pii", "mnpi"):
        section = raw.get(category, {}) or {}
        if isinstance(section, dict):
            for rule, juris_map in section.items():
                if isinstance(juris_map, dict):
                    normalized[category][rule] = {
                        str(k).strip().upper(): str(v) for k, v in juris_map.items()
                    }
                else:
                    raise CitationOverrideError(
                        f"citation override section {category}.{rule} must be a jurisdiction table"
                    )
        else:
            raise CitationOverrideError(f"citation override section {category} must be a table")
    _CITATIONS_OVERRIDE_CACHE[path] = (normalized, mtime)
    return normalized


def _load_global_citations_override() -> dict[str, dict[str, dict[str, str]]]:
    override_env = os.environ.get("KAYPOH_CITATIONS_OVERRIDE", "").strip()
    if not override_env:
        return {}
    return _load_citations_override_path(Path(override_env).expanduser())


def _load_tenant_citations_override(tenant_id: str | None) -> dict[str, dict[str, dict[str, str]]]:
    override_dir = os.environ.get("KAYPOH_CITATIONS_OVERRIDE_DIR", "").strip()
    if not override_dir or not tenant_id:
        return {}
    if "/" in tenant_id or "\\" in tenant_id or tenant_id in {".", ".."}:
        raise CitationOverrideError("tenant_id is not safe for citation override path resolution")
    path = Path(override_dir).expanduser() / f"{tenant_id}.toml"
    if not path.exists():
        return {}
    return _load_citations_override_path(path)


def _lookup_in_override(
    override: dict[str, dict[str, dict[str, str]]],
    category: str,
    rule: str,
    codes: list[str],
) -> str | None:
    overrides = override.get(category, {}).get(rule)
    if not overrides:
        return None
    for code in codes:
        hit = overrides.get(code.upper())
        if hit:
            return hit
    return overrides.get("DEFAULT")


def _lookup_override(category: str, rule: str, codes: list[str], *, tenant_id: str | None = None) -> str | None:
    tenant_override = _load_tenant_citations_override(tenant_id)
    hit = _lookup_in_override(tenant_override, category, rule, codes)
    if hit:
        return hit
    return _lookup_in_override(_load_global_citations_override(), category, rule, codes)


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


# longest matched_text we'll inline into a rationale. anything longer is truncated with an
# ellipsis so the audit-pack artefact stays scannable.
_MATCHED_TEXT_INLINE_LIMIT = 80


def _format_matched_prefix(matched_text: str) -> str:
    if not matched_text:
        return ""
    cleaned = " ".join(matched_text.split())  # collapse whitespace/newlines for a tidy quote
    if len(cleaned) > _MATCHED_TEXT_INLINE_LIMIT:
        cleaned = cleaned[: _MATCHED_TEXT_INLINE_LIMIT - 1].rstrip() + "…"
    return f'"{cleaned}" detected → '


def pii_rationale(
    *,
    rule: str,
    jurisdiction: str,
    matched_text: str = "",
    tenant_id: str | None = None,
) -> str:
    codes = _split_jurisdictions(jurisdiction)
    override = _lookup_override("pii", rule, codes, tenant_id=tenant_id)
    if override:
        return f"{_format_matched_prefix(matched_text)}{override}".strip()
    base = _PII_DEFAULT_RATIONALE.get(
        rule,
        "Personal data should be masked unless the recipient and purpose are documented.",
    )
    suffix = _join_suffixes(codes, _PII_JURISDICTION_SUFFIX)
    return f"{_format_matched_prefix(matched_text)}{base} {suffix}".strip()


def mnpi_rationale(
    *,
    rule: str,
    jurisdiction: str,
    severity: str,
    matched_text: str = "",
    tenant_id: str | None = None,
) -> str:
    codes = _split_jurisdictions(jurisdiction)
    override = _lookup_override("mnpi", rule, codes, tenant_id=tenant_id)
    if override:
        # severity softening still applies to override text so the audit artefact stays coherent.
        if severity == "low":
            override = override.rstrip(".") + " — appears public; verify the disclosing source before relying on it."
        return f"{_format_matched_prefix(matched_text)}{override}".strip()
    base = _MNPI_DEFAULT_RATIONALE.get(
        rule,
        "Material non-public information detected. Hold until publicly disclosed or generalise the claim.",
    )
    suffix = _join_suffixes(codes, _MNPI_JURISDICTION_SUFFIX)
    if severity == "low":
        # public-context evidence already detected; soften the directive but keep the citation.
        base = base.rstrip(".") + " — appears public; verify the disclosing source before relying on it."
    return f"{_format_matched_prefix(matched_text)}{base} {suffix}".strip()
