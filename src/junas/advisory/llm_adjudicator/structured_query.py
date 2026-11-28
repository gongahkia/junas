"""Closed-vocabulary metadata and hashed identifiers for optional AI requests.

Hashes are pseudonymous references, not anonymity or proof of source verification.
Unknown/custom rule and jurisdiction text is not forwarded to providers.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

STRUCTURED_CONTEXT_WINDOW_CHARS = 200
STRUCTURED_REASONS = frozenset(
    {
        "public_source_match",
        "no_public_source_match",
        "nonpublic_context_marker",
        "ambiguous_score_band",
        "embargo_marker_present",
        "deal_codename_present",
        "deterministic_high_floor",
        "ambiguous_unconstrained",
    }
)
STRUCTURED_RECOMMENDATIONS = frozenset({"ok", "no escalation", "see_audit_pack", "human_review_required"})
# a wire privacy vocabulary, not a detector registry. new/custom rules remain local
# until deliberately added here; unknown values carry no raw rule-name contents.
STRUCTURED_RULES = frozenset(
    """
    advertising_id ae_emirates_id ae_passport ae_trade_licence age_reference
    au_abn au_acn au_postal_address au_tfn bank_account
    bank_customer_reference biometric_identifier blackout_period_reference cn_passport cn_phone
    cn_resident_id cn_uscc conjunctive_mnpi consent_withdrawal_marker contingent_mnpi_language
    contract_discount_rate contract_unit_price cookie_id cross_border_transfer_marker crypto_wallet_address
    customer_account_number cyber_incident_pre_disclosure data_minimisation_marker date_of_birth definitive_agreement
    device_serial_number dpt_pre_listing_marker dpt_protocol_event_marker email_address embargo_marker
    employee_id energy_reserves_mnpi esg_climate_pre_disclosure esg_target_revision eu_national_id
    financial_amount financial_percentage financial_services_regulatory_mnpi genetic_data health_condition
    hk_cr_no hk_hkid id_nik imei in_aadhaar
    in_gstin in_pan in_voter_id information_barrier_marker insider_list_marker
    insurance_member_id internal_session_id ip_address jp_corporate_number jp_my_number
    jp_postal_code kr_business_registration kr_rrn large_number legal_proceeding_mnpi
    mac_address material_adverse_change material_event medical_record_number medical_treatment
    minor_data_reference my_mykad named_person nonpublic_marker passport_number
    ph_philsys ph_tin pharma_trial_mnpi phone_number political_opinion
    quasi_identifier_combination racial_ethnic_origin religious_belief royalty_rate sa_commercial_registration
    sa_iqama sa_national_id selective_disclosure_risk sex_life_reference sexual_orientation
    sg_acra_transaction_number sg_court_citation sg_hdb_reference sg_insurance_policy_number sg_ipos_tm_number
    sg_mas_licence sg_nric_fin sg_paynow sg_postal_address sg_sgx_counter
    sg_sla_lot_number sg_sla_title_plan_number sg_tribunal_reference sg_uen sg_ura_planning_reference
    th_national_id tipping_language total_contract_value trade_union_membership transaction_codename
    uk_nin us_driver_license us_ein us_itin us_ssn vn_cccd volume_commitment
""".split()
)
STRUCTURED_JURISDICTIONS = frozenset("SG US UK AU AE CN EU HK ID IN JP KR MY PH SA SEA TH VN".split())
STRUCTURED_DOCUMENT_TYPES = frozenset({"generic", "SPA", "NDA", "SHA", "term_sheet", "memo", "research_note"})
PUBLIC_EVIDENCE_STATUSES = frozenset({"queried", "skipped", "error", "disabled"})


def safe_document_type(value: Any) -> str:
    return value if isinstance(value, str) and value in STRUCTURED_DOCUMENT_TYPES else "generic"


def safe_finding_metadata(finding: Any) -> dict[str, str]:
    def get(key):
        return finding.get(key) if isinstance(finding, dict) else getattr(finding, key, None)

    category, severity = get("category"), get("severity")
    if category not in ("PII", "MNPI") or severity not in ("low", "medium", "high"):
        raise ValueError("invalid structured finding category/severity")
    rule, jurisdiction = get("rule"), get("jurisdiction")
    if not isinstance(rule, str) or not isinstance(jurisdiction, str):
        raise ValueError("structured finding labels must be strings")
    parts = jurisdiction.split("+")
    return {
        "rule": rule if rule in STRUCTURED_RULES else "unmapped_rule",
        "category": category,
        "severity": severity,
        "jurisdiction": jurisdiction if all(p in STRUCTURED_JURISDICTIONS for p in parts) else "custom",
    }


def validate_body_hash(value: Any) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("body hash must be SHA256 hexadecimal")


def build_structured_query(
    *,
    text: str,
    findings: list,
    entity_id: str | None,
    current_classification: str,
    public_evidence: dict | None,
) -> dict[str, Any]:
    if not isinstance(text, str) or (entity_id is not None and not isinstance(entity_id, str)):
        raise ValueError("structured text/identifier must be strings")
    if current_classification not in ("present", "not_detected", "unknown", "SAFE", "LOW_RISK", "HIGH_RISK"):
        raise ValueError("invalid current classification")
    if not isinstance(findings, list) or (public_evidence is not None and not isinstance(public_evidence, dict)):
        raise ValueError("invalid structured findings/public evidence")
    tokens = []
    for f in findings:
        item = safe_finding_metadata(f)
        start, end = f.start_char, f.end_char
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
            raise ValueError("structured finding has invalid evidence bounds")
        if text[start:end] != f.matched_text:
            raise ValueError("structured finding text does not match evidence")
        lo, hi = max(0, start - STRUCTURED_CONTEXT_WINDOW_CHARS), min(len(text), end + STRUCTURED_CONTEXT_WINDOW_CHARS)
        item["context_window_hash"] = hashlib.sha256(text[lo:hi].encode()).hexdigest()
        tokens.append(item)
    pe_summary: dict[str, Any] = {"status": "skipped", "source_count": 0, "blocked_query_count": 0}
    if public_evidence:
        status = public_evidence.get("status", "skipped")
        if not isinstance(status, str) or status not in PUBLIC_EVIDENCE_STATUSES:
            raise ValueError("invalid public evidence status")
        sources, queries = public_evidence.get("sources", []), public_evidence.get("queries", [])
        if (
            not isinstance(sources, list)
            or not isinstance(queries, list)
            or any(not isinstance(q, dict) for q in queries)
        ):
            raise ValueError("invalid public evidence arrays")
        pe_summary.update(
            status=status, source_count=len(sources), blocked_query_count=sum(q.get("blocked") is True for q in queries)
        )
    return {
        "mode": "structured_tokens",
        "current_classification": current_classification,
        "entity_id": "sha256:" + hashlib.sha256(entity_id.encode()).hexdigest() if entity_id else "",
        "body_hash": hashlib.sha256(text.encode()).hexdigest(),
        "findings": tokens,
        "public_evidence_summary": pe_summary,
    }


def clamp_structured_output(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if not isinstance(payload, dict):
        raise ValueError("structured output must be an object")
    clamped = dict(payload)
    reason = clamped.get("materiality_reason", "")
    was_clamped = False
    if not isinstance(reason, str) or reason.strip().lower() not in STRUCTURED_REASONS:
        clamped["materiality_reason"] = "ambiguous_unconstrained"
        was_clamped = True
    else:
        clamped["materiality_reason"] = reason.strip().lower()
    for key in ("matched_public_sources", "unverified_claims"):
        was_clamped |= bool(clamped.get(key))
        clamped[key] = []
    if clamped.get("review_recommendation") not in STRUCTURED_RECOMMENDATIONS:
        clamped["review_recommendation"] = "see_audit_pack"
        was_clamped = True
    return clamped, was_clamped
