"""Shared statutory taxonomy for synthetic fixture generation and labeling."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JurisdictionTaxonomy:
    code: str
    name: str
    pii_definition: str
    mnpi_definition: str
    local_context: str


@dataclass(frozen=True)
class ConceptTaxonomy:
    key: str
    title: str
    description: str
    positive_guidance: str
    negative_guidance: str


JURISDICTIONS: dict[str, JurisdictionTaxonomy] = {
    "SG": JurisdictionTaxonomy(
        "SG", "Singapore",
        "PDPA: data about an individual identifiable from that data or likely-accessible context.",
        "SFA/SGX: not generally available information expected to materially affect securities price/value.",
        "SG law-firm, listed-company, M&A, employment, capital-markets, and PDPA/SGX workflows.",
    ),
    "MY": JurisdictionTaxonomy(
        "MY", "Malaysia",
        "PDPA: information relating directly or indirectly to an identified or identifiable data subject.",
        "CMSA/Bursa: non-public information likely to materially affect securities price/value.",
        "Malaysian listed-company, Bursa disclosure, employment, financing, and deal documents.",
    ),
    "ID": JurisdictionTaxonomy(
        "ID", "Indonesia",
        "UU PDP: data about an identified or identifiable natural person, alone or combined with other data.",
        "Capital Markets Law/OJK: material non-public issuer information affecting investors or securities price.",
        "Indonesian issuer, OJK disclosure, acquisition, employment, fintech, and board memo workflows.",
    ),
    "TH": JurisdictionTaxonomy(
        "TH", "Thailand",
        "PDPA: information relating to a person enabling direct or indirect identification.",
        "SEA/SEC: undisclosed information that may materially affect securities price.",
        "Thai listed-company, SEC disclosure, financing, employment, and cross-border legal documents.",
    ),
    "PH": JurisdictionTaxonomy(
        "PH", "Philippines",
        "Data Privacy Act: information from which identity is apparent or directly ascertainable with other data.",
        "SRC/SEC: material non-public information important to a reasonable investor.",
        "Philippines issuer, SEC disclosure, HR, tax, banking, and capital-markets documents.",
    ),
    "VN": JurisdictionTaxonomy(
        "VN", "Vietnam",
        "Decree 13: information associated with or helping identify a specific person.",
        "Securities Law: issuer/securities information not yet public with significant price impact.",
        "Vietnamese issuer, securities disclosure, employee, banking, and transaction documents.",
    ),
    "HK": JurisdictionTaxonomy(
        "HK", "Hong Kong",
        "PDPO: data relating to a living individual whose identity is directly/indirectly ascertainable.",
        "SFO: specific corporation information not generally known to likely securities dealers and price-material.",
        "Hong Kong listed-company, SFC/HKEX, M&A, fund, and employment workflows.",
    ),
    "AU": JurisdictionTaxonomy(
        "AU", "Australia",
        "Privacy Act: information or opinion about an identified or reasonably identifiable individual.",
        "Corporations Act/ASIC: not generally available information expected to materially affect financial products.",
        "Australian company, ASIC/ASX, employment, health, credit, and transaction documents.",
    ),
    "JP": JurisdictionTaxonomy(
        "JP", "Japan",
        "APPI/My Number: living-individual information identifying a person, including individual codes.",
        "FIEA: undisclosed enumerated material facts or tender-offer facts.",
        "Japanese issuer, APPI/My Number, board, acquisition, employee, and securities workflows.",
    ),
    "KR": JurisdictionTaxonomy(
        "KR", "Korea",
        "PIPA: living-individual information identifying directly or through combination with other data.",
        "FSCMA: important information not yet publicly disclosed.",
        "Korean issuer, FSC/FSS, employment, resident-number, deal, and investor-relations documents.",
    ),
    "US": JurisdictionTaxonomy(
        "US", "United States",
        "CCPA/HIPAA/GLBA patchwork: information reasonably linkable to a consumer, household, or patient.",
        "Rule 10b-5/Reg FD: material non-public information and selective disclosure to covered market actors.",
        "US issuer, Reg FD, healthcare, banking, employee, analyst, and securities workflows.",
    ),
    "UK": JurisdictionTaxonomy(
        "UK", "United Kingdom",
        "UK GDPR: information relating to an identified or identifiable natural person.",
        "UK MAR: precise non-public issuer/security information likely to significantly affect price.",
        "UK issuer, FCA, employment, financial-services, deal, and market-abuse workflows.",
    ),
    "EU": JurisdictionTaxonomy(
        "EU", "European Union",
        "GDPR: information relating to an identified or identifiable natural person, including indirect identifiers.",
        "EU MAR: precise non-public issuer/security information likely to significantly affect price.",
        "EU issuer, GDPR Art 9, cross-border transfer, CSRD/SFDR, and MAR workflows.",
    ),
    "IN": JurisdictionTaxonomy(
        "IN", "India",
        "DPDPA: data about an individual identifiable by or in relation to such data; child means under 18.",
        "SEBI PIT follow-up: unpublished price-sensitive information for listed securities.",
        "Indian DPDPA, Aadhaar/PAN/GSTIN, children, consent, and listed-company workflows.",
    ),
    "CN": JurisdictionTaxonomy(
        "CN", "China",
        "PIPL: information related to identified or identifiable natural persons; sensitive PI includes minors <14.",
        "Securities Law follow-up: inside information before public disclosure.",
        "China PIPL/CSL/DSL, resident ID, USCC, cross-border CAC, issuer, and employment workflows.",
    ),
    "AE": JurisdictionTaxonomy(
        "AE", "United Arab Emirates",
        "PDPL: data relating to an identified or indirectly identifiable natural person.",
        "UAE/SCA/ADGM/DIFC market-abuse follow-up: non-public market-sensitive issuer information.",
        "UAE PDPL, Emirates ID, trade licence, DIFC/ADGM, family-origin, and deal workflows.",
    ),
    "SA": JurisdictionTaxonomy(
        "SA", "Saudi Arabia",
        "KSA PDPL: information identifying a natural person directly or indirectly.",
        "CMA market-conduct follow-up: non-public issuer information relevant to securities markets.",
        "Saudi PDPL, national ID/Iqama, commercial registration, SDAIA transfer, and issuer workflows.",
    ),
}


CONCEPTS: dict[str, ConceptTaxonomy] = {
    "direct_identifiers": ConceptTaxonomy(
        "direct_identifiers", "Direct identifiers",
        "Local government, tax, company, passport, phone, email, account, and address identifiers.",
        "Use jurisdiction-local identifiers plus emails/phones/passports in legal or business context.",
        "Include invalid checksums, public helpline numbers, generic form labels, and role-only names.",
    ),
    "special_category": ConceptTaxonomy(
        "special_category", "Special-category personal data",
        "Health, treatment, biometric, genetic, sex-life, sexual-orientation, religion, union, and politics.",
        "Use anchored fields or named-subject clauses that clearly concern a fictional person.",
        "Include product names, metaphors, places, sports teams, policy names, and generic DEI prose.",
    ),
    "privacy_events": ConceptTaxonomy(
        "privacy_events", "Privacy handling events",
        "Cross-border transfer, consent withdrawal, DSAR, erasure, retention, and minimisation markers.",
        "Use compliance memos, DPA schedules, onboarding forms, and data-export approvals.",
        "Include negated or completed-control language that should not imply a live privacy risk.",
    ),
    "universal_mnpi": ConceptTaxonomy(
        "universal_mnpi", "Universal MNPI",
        "Deal codenames, non-public markers, definitive agreements, MAC/MAE, embargo dates, amounts, percentages.",
        "Use board memos, term sheets, research notes, investor-relations drafts, and deal checklists.",
        "Include public-source references, negated MAC language, lowercase project-management prose, and spa-day bait.",
    ),
    "jurisdictional_mnpi": ConceptTaxonomy(
        "jurisdictional_mnpi", "Jurisdiction-specific MNPI",
        "Local non-public/public-status semantics, selective disclosure, blackout windows, "
        "and issuer-relative materiality.",
        "Use local exchange/regulator language and jurisdiction-specific disclosure timing.",
        "Include public filings, broad press-release references, stale public information, "
        "and non-issuer operational updates.",
    ),
    "sector_mnpi": ConceptTaxonomy(
        "sector_mnpi", "Sector/event MNPI",
        "Crypto, ESG/climate, cyber incident, insider-list, information-barrier, and commercial-term signals.",
        "Use sensitive sector events adjacent to non-public or deal-stage context.",
        "Include educational, marketing, or operational examples that reuse the same words without market sensitivity.",
    ),
    "quasi_identifiers": ConceptTaxonomy(
        "quasi_identifiers", "Quasi-identifiers",
        "Combinations of DOB, location, employer, role, device, account, and linkable IDs.",
        "Create clusters of multiple weak identifiers within the same matter or paragraph.",
        "Include separated weak identifiers and generic demographics that should not identify a person alone.",
    ),
}


PII_RULES: tuple[str, ...] = (
    "sg_nric_fin", "sg_uen", "sg_postal_address", "sg_court_citation", "sg_paynow",
    "sg_mas_licence", "sg_sgx_counter", "sg_ipos_tm_number", "sg_acra_transaction_number",
    "sg_hdb_reference", "sg_sla_lot_number", "sg_sla_title_plan_number", "sg_ura_planning_reference",
    "sg_insurance_policy_number", "sg_tribunal_reference", "my_mykad", "id_nik",
    "th_national_id", "ph_philsys", "ph_tin", "vn_cccd", "hk_hkid", "hk_cr_no",
    "au_tfn", "au_abn", "au_acn", "au_postal_address", "jp_my_number",
    "jp_corporate_number", "jp_postal_code", "kr_rrn", "kr_business_registration",
    "us_ssn", "us_ein", "us_itin", "us_driver_license", "uk_nin", "eu_national_id",
    "in_aadhaar", "in_pan", "in_gstin", "in_voter_id", "cn_resident_id", "cn_uscc",
    "cn_phone", "cn_passport", "ae_emirates_id", "ae_trade_licence", "ae_passport",
    "sa_national_id", "sa_iqama", "sa_commercial_registration", "passport_number",
    "email_address", "phone_number", "bank_account", "named_person", "date_of_birth",
    "age_reference", "ip_address", "mac_address", "imei", "cookie_id", "advertising_id",
    "device_serial_number", "employee_id", "customer_account_number", "internal_session_id",
    "bank_customer_reference", "medical_record_number", "insurance_member_id",
    "quasi_identifier_combination", "cross_border_transfer_marker", "consent_withdrawal_marker",
    "data_minimisation_marker", "religious_belief", "trade_union_membership", "political_opinion",
    "health_condition", "medical_treatment", "biometric_identifier", "genetic_data",
    "sexual_orientation", "sex_life_reference", "minor_data_reference", "crypto_wallet_address",
)


MNPI_RULES: tuple[str, ...] = (
    "material_event", "nonpublic_marker", "transaction_codename", "definitive_agreement",
    "material_adverse_change", "embargo_marker", "financial_amount", "financial_percentage",
    "large_number", "contract_unit_price", "contract_discount_rate", "volume_commitment",
    "royalty_rate", "total_contract_value", "contingent_mnpi_language", "tipping_language",
    "selective_disclosure_risk", "blackout_period_reference", "insider_list_marker",
    "information_barrier_marker", "dpt_pre_listing_marker", "dpt_protocol_event_marker",
    "esg_climate_pre_disclosure", "esg_target_revision", "cyber_incident_pre_disclosure",
)


DOC_TYPES: dict[str, str] = {
    "spa": "a share purchase agreement face page or excerpt",
    "nda": "a non-disclosure agreement preamble and short clause set",
    "sha": "a shareholders agreement excerpt",
    "term_sheet": "a financing, acquisition, or strategic transaction term sheet",
    "memo": "an internal legal, compliance, board, or deal memo",
    "research_note": "an analyst or investor-relations note",
    "employment_letter": "an employment, HR, or onboarding letter",
    "special_category": "a healthcare, HR, or onboarding note focused on special-category personal data",
    "privacy_notice": "a DPA, privacy notice, DSAR, transfer, or retention workflow note",
    "incident_report": "a cyber, ESG, or operational incident report",
}


DOC_TYPE_TO_FIELD: dict[str, str] = {
    "spa": "SPA",
    "nda": "NDA",
    "sha": "SHA",
    "term_sheet": "term_sheet",
    "memo": "memo",
    "research_note": "research_note",
    "employment_letter": "generic",
    "special_category": "generic",
    "privacy_notice": "generic",
    "incident_report": "memo",
}


def supported_jurisdictions() -> tuple[str, ...]:
    return tuple(JURISDICTIONS)


def supported_concepts() -> tuple[str, ...]:
    return tuple(CONCEPTS)


def all_rules() -> tuple[str, ...]:
    return PII_RULES + MNPI_RULES


def jurisdiction_prompt(code: str) -> str:
    item = JURISDICTIONS[code]
    return (
        f"{item.code} — {item.name}\n"
        f"PII definition: {item.pii_definition}\n"
        f"MNPI definition: {item.mnpi_definition}\n"
        f"Context: {item.local_context}"
    )


def concept_prompt(key: str) -> str:
    item = CONCEPTS[key]
    return (
        f"{item.title}: {item.description}\n"
        f"Positive generation target: {item.positive_guidance}\n"
        f"Negative/adversarial target: {item.negative_guidance}"
    )
