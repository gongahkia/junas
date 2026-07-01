"""Deterministic Layer-2 conjunctive MNPI element detector.

The detector does not introduce a new legal standard. It joins existing Layer-1
signals into a review-required finding when the record has an entity/deal element
and a non-public element, then records whether materiality is lexicalised,
quantitative, implied, or still undetermined.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

SOURCE_VERIFICATION_NOT_CHECKED = "not_checked"
SOURCE_VERIFICATION_PUBLIC_SOURCE_MATCHED = "public_source_matched"
SOURCE_VERIFICATION_NO_PUBLIC_SOURCE_FOUND = "no_public_source_found"
SOURCE_VERIFICATION_AMBIGUOUS = "ambiguous"

MATERIALITY_LEXICAL_RULES = frozenset({
    "material_event",
    "material_adverse_change",
    "transaction_codename",
    "definitive_agreement",
    "embargo_marker",
    "dpt_pre_listing_marker",
    "dpt_protocol_event_marker",
    "esg_climate_pre_disclosure",
    "esg_target_revision",
    "cyber_incident_pre_disclosure",
})
MATERIALITY_QUANT_RULES = frozenset({"financial_amount", "financial_percentage"})
MATERIALITY_IMPLIED_RULES = frozenset({
    "contingent_mnpi_language",
    "tipping_language",
    "selective_disclosure_risk",
    "insider_list_marker",
    "information_barrier_marker",
    "blackout_period_reference",
})
NON_PUBLIC_RULES = frozenset({
    "nonpublic_marker",
    "embargo_marker",
    "transaction_codename",
    "definitive_agreement",
    "material_adverse_change",
    "insider_list_marker",
    "information_barrier_marker",
    "blackout_period_reference",
})
NON_PUBLIC_SOURCE_STATES = frozenset({
    SOURCE_VERIFICATION_NOT_CHECKED,
    SOURCE_VERIFICATION_NO_PUBLIC_SOURCE_FOUND,
    SOURCE_VERIFICATION_AMBIGUOUS,
})
ENTITY_FINDING_RULES = frozenset({
    "named_person",
    "sg_uen",
    "sg_sgx_counter",
    "sg_mas_licence",
    "sg_acra_transaction_number",
    "hk_cr_no",
    "au_abn",
    "au_acn",
    "jp_corporate_number",
    "kr_business_registration",
    "us_ein",
    "uk_company_number",
    "in_pan",
    "in_gstin",
    "cn_uscc",
})
POSSESSION_DUTY_RULES = frozenset({
    "tipping_language",
    "selective_disclosure_risk",
    "insider_list_marker",
    "information_barrier_marker",
})

ORG_NAME_RE = re.compile(
    r"\b[A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,5}\s+"
    r"(?:Pte\.?\s+Ltd\.?|Pvt\.?\s+Ltd\.?|Sdn\.?\s+Bhd\.?|Ltd\.?|Limited|"
    r"Corp\.?|Corporation|Inc\.?|LLC|LLP|PLC|GmbH|AG|Holdings|Group|Capital|Partners)\b"
)
ISSUER_CONTEXT_RE = re.compile(
    r"\b(?:issuer|counterparty|target|vendor|purchaser|listed\s+issuer|SGX\s+counter|ticker|stock\s+code)\b",
    re.IGNORECASE,
)
SECURITY_CODE_RE = re.compile(
    r"\b(?:ticker|symbol|stock\s+code|ISIN|CUSIP|security\s+code|deal\s+code|project\s+tag|code)\s+"
    r"(?-i:[A-Z0-9][A-Z0-9.-]{2,})\b",
    re.IGNORECASE,
)
RAW_NON_PUBLIC_RE = re.compile(
    r"\b(?:NDA-side|clean[- ]team|counsel-only|data[- ]room|pre-clearance\s+hold|"
    r"NDA\s+queue|cleansing\s+memo|private-side|advisor\s+room|named-recipient|"
    r"not\s+for\s+street|hold\s+for\s+cleans(?:e|ing)|no\s+street\s+readout|"
    r"keep\s+to\s+named\s+recipients|keep\s+off\s+chat|do\s+not\s+brief\s+street|"
    r"release\s+packet)\b",
    re.IGNORECASE,
)
RAW_MATERIALITY_RE = re.compile(
    r"\b(?:bookings\s+cut|margin\s+reset|churn\s+spike|ARR\s+miss|supplier\s+loss|"
    r"same-store\s+sales\s+down|loan-loss\s+reserve\s+build|outage\s+cost\s+above\s+covenant\s+basket|"
    r"trial\s+halt|customer\s+loss\s+removes\s+pipeline|backlog\s+reversal|"
    r"pricing\s+reset\s+below\s+board\s+case|run-rate|milestone\s+receipt)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ConjunctiveMNPIFindingSpec:
    severity: str
    matched_text: str
    start_char: int
    end_char: int
    reason: str
    source_verification: str
    metadata: dict[str, Any]


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _as_rule(finding: Any) -> str:
    return str(_attr(finding, "rule", "") or "")


def _source_state(finding: Any) -> str:
    return str(_attr(finding, "source_verification", SOURCE_VERIFICATION_NOT_CHECKED) or "")


def _non_public_finding(finding: Any) -> bool:
    rule = _as_rule(finding)
    if rule == "conjunctive_mnpi":
        return False
    if rule in NON_PUBLIC_RULES:
        return True
    if str(_attr(finding, "category", "")).upper() != "MNPI":
        return False
    if _source_state(finding) == SOURCE_VERIFICATION_PUBLIC_SOURCE_MATCHED:
        return False
    return _source_state(finding) in NON_PUBLIC_SOURCE_STATES


def _entity_element(text: str, findings: list[Any], entity_id: str | None) -> dict[str, Any] | None:
    for finding in findings:
        if _as_rule(finding) in ENTITY_FINDING_RULES:
            return {
                "rule": _as_rule(finding),
                "start": int(_attr(finding, "start_char", 0) or 0),
                "end": int(_attr(finding, "end_char", 0) or 0),
                "matched_text": str(_attr(finding, "matched_text", "") or ""),
            }
    if entity_id:
        match = re.search(re.escape(entity_id.strip()), text, re.IGNORECASE)
        if match:
            return {
                "rule": "entity_id",
                "start": match.start(),
                "end": match.end(),
                "matched_text": match.group(),
            }
    for pattern, rule in ((ORG_NAME_RE, "org_name"), (ISSUER_CONTEXT_RE, "issuer_context")):
        match = pattern.search(text)
        if match:
            return {
                "rule": rule,
                "start": match.start(),
                "end": match.end(),
                "matched_text": match.group(),
            }
    match = SECURITY_CODE_RE.search(text)
    if match:
        return {
            "rule": "security_code_context",
            "start": match.start(),
            "end": match.end(),
            "matched_text": match.group(),
        }
    return None


def _raw_elements(text: str, pattern: re.Pattern[str], rule: str) -> list[dict[str, Any]]:
    return [
        {
            "rule": rule,
            "start": match.start(),
            "end": match.end(),
            "matched_text": match.group(),
        }
        for match in pattern.finditer(text)
    ]


def _materiality_state(findings: list[Any]) -> tuple[str, list[str]]:
    rules = [_as_rule(finding) for finding in findings if _as_rule(finding) != "conjunctive_mnpi"]
    lexical = [rule for rule in rules if rule in MATERIALITY_LEXICAL_RULES]
    if lexical:
        return "lexicalised", sorted(set(lexical))

    quantitative: list[str] = []
    for finding in findings:
        rule = _as_rule(finding)
        if rule not in MATERIALITY_QUANT_RULES:
            continue
        reason = str(_attr(finding, "reason", "") or "")
        severity = str(_attr(finding, "severity", "") or "")
        if severity == "high" or "entity-relative" in reason or "SAB 99" in reason or "ASX GN8" in reason:
            quantitative.append(rule)
    if quantitative:
        return "quantitative", sorted(set(quantitative))

    implied: list[str] = []
    for finding in findings:
        rule = _as_rule(finding)
        severity = str(_attr(finding, "severity", "") or "")
        if rule in MATERIALITY_IMPLIED_RULES and severity in {"medium", "high"}:
            implied.append(rule)
    if implied:
        return "implied", sorted(set(implied))

    return "undetermined", []


def _context_span(text: str, start: int, end: int) -> tuple[int, int, str]:
    left = text.rfind("\n", 0, start) + 1
    right = text.find("\n", end)
    if right < 0:
        right = len(text)
    matched = text[left:right].strip()
    if len(matched) > 320:
        center_left = max(left, start - 140)
        center_right = min(right, end + 140)
        matched = text[center_left:center_right].strip()
        left = center_left
        right = center_right
    return left, right, matched


def _severity_for_elements(materiality_state: str, possession_or_duty: bool) -> str:
    if possession_or_duty and materiality_state in {"lexicalised", "quantitative", "implied"}:
        return "high"
    return "medium"


def detect_conjunctive_mnpi(
    *,
    text: str,
    findings: list[Any],
    jurisdiction: str,
    legal_basis: str,
    entity_id: str | None = None,
) -> list[ConjunctiveMNPIFindingSpec]:
    del jurisdiction, legal_basis  # carried by the engine-created ReviewFinding.
    if any(_as_rule(finding) == "conjunctive_mnpi" for finding in findings):
        return []

    entity = _entity_element(text, findings, entity_id)
    non_public = [finding for finding in findings if _non_public_finding(finding)]
    raw_non_public = _raw_elements(text, RAW_NON_PUBLIC_RE, "raw_nonpublic_possession_marker")
    if entity is None or (not non_public and not raw_non_public):
        return []

    materiality_state, materiality_rules = _materiality_state(findings)
    raw_materiality = _raw_elements(text, RAW_MATERIALITY_RE, "raw_materiality_marker")
    if materiality_state == "undetermined" and raw_materiality:
        materiality_state = "lexicalised"
        materiality_rules = ["raw_materiality_marker"]
    possession_or_duty = [
        {
            "rule": _as_rule(finding),
            "start": int(_attr(finding, "start_char", 0) or 0),
            "end": int(_attr(finding, "end_char", 0) or 0),
            "matched_text": str(_attr(finding, "matched_text", "") or ""),
        }
        for finding in findings
        if _as_rule(finding) in POSSESSION_DUTY_RULES
    ]
    possession_or_duty.extend(raw_non_public)
    starts = [int(entity["start"])]
    ends = [int(entity["end"])]
    element_rules = {
        "entity": [str(entity["rule"])],
        "non_public": sorted(
            {_as_rule(finding) for finding in non_public} | {str(item["rule"]) for item in raw_non_public}
        ),
        "materiality": materiality_rules,
        "possession_or_duty": sorted({str(item["rule"]) for item in possession_or_duty}),
    }
    for finding in non_public:
        starts.append(int(_attr(finding, "start_char", 0) or 0))
        ends.append(int(_attr(finding, "end_char", 0) or 0))
    for item in [*raw_non_public, *raw_materiality, *possession_or_duty]:
        starts.append(int(item["start"]))
        ends.append(int(item["end"]))

    start, end, matched = _context_span(text, min(starts), max(ends))
    source_states = {_source_state(finding) for finding in non_public}
    if SOURCE_VERIFICATION_NO_PUBLIC_SOURCE_FOUND in source_states:
        source_verification = SOURCE_VERIFICATION_NO_PUBLIC_SOURCE_FOUND
    elif SOURCE_VERIFICATION_AMBIGUOUS in source_states:
        source_verification = SOURCE_VERIFICATION_AMBIGUOUS
    else:
        source_verification = SOURCE_VERIFICATION_NOT_CHECKED

    metadata: dict[str, Any] = {
        "layer": "layer2",
        "materiality_state": materiality_state,
        "non_public_element_satisfied": True,
        "entity_element_satisfied": True,
        "possession_or_duty_element_satisfied": bool(possession_or_duty),
        "element_rules": element_rules,
        "element_count": 2 + int(materiality_state != "undetermined") + int(bool(possession_or_duty)),
        "review_required": True,
        "internal_note": (
            "Deterministic conjunctive MNPI element check; materiality may require "
            "lawyer review or audit_grade adjudication."
        ),
    }
    reason = (
        "Layer-2 conjunctive MNPI: entity/deal and non-public elements co-occur; "
        f"materiality is {materiality_state}. Review under SFA s218/s219, MAR Art 7/14, "
        "Reg FD 17 CFR 243.100, and local inside-information rules before sending."
    )
    return [
        ConjunctiveMNPIFindingSpec(
            severity=_severity_for_elements(materiality_state, bool(possession_or_duty)),
            matched_text=matched,
            start_char=start,
            end_char=end,
            reason=reason,
            source_verification=source_verification,
            metadata=metadata,
        )
    ]
