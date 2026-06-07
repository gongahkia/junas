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
    "date_of_birth": (
        "Date of birth is a direct quasi-identifier: HIPAA 45 CFR §164.514(b)(2)(i)(C) "
        "lists dates tied to an individual in the de-identification safe harbor, while "
        "PDPA s2 / GDPR Recital 26 / CCPA §1798.140 treat linkable attributes as "
        "personal data. Mask or generalise unless disclosure is purpose-limited."
    ),
    "age_reference": (
        "Age can identify or narrow an individual when combined with name, address, "
        "role, or account data. HIPAA 45 CFR §164.514(b)(2)(i)(C) treats ages over 89 "
        "as identifying, and PDPA s2 / GDPR Recital 26 cover linkable attributes. "
        "Generalise or suppress unless age is necessary for the documented purpose."
    ),
    "ip_address": (
        "IP address / online identifier detected. GDPR Recital 30 explicitly lists "
        "internet protocol addresses and cookie/device identifiers as online identifiers; "
        "HIPAA 45 CFR §164.514 includes IP addresses in the safe-harbor identifier list, "
        "and CCPA §1798.140 covers online identifiers. Mask before external disclosure."
    ),
    "mac_address": (
        "MAC address / device identifier detected. HIPAA 45 CFR §164.514 lists device "
        "identifiers and serial numbers; GDPR Recital 30 and CCPA §1798.140 cover "
        "device/online identifiers that can single out a person or household. Mask before send."
    ),
    "imei": (
        "IMEI / mobile-device identifier detected. HIPAA 45 CFR §164.514 lists device "
        "identifiers and serial numbers; GDPR Recital 30 and CCPA §1798.140 cover "
        "device identifiers that can single out a person or household. Mask before send."
    ),
    "cookie_id": (
        "Cookie identifier detected. GDPR Recital 30 explicitly lists cookie identifiers "
        "as online identifiers, and CCPA §1798.140 covers persistent identifiers. Mask or "
        "rotate before external disclosure unless the recipient and purpose are documented."
    ),
    "advertising_id": (
        "Mobile advertising identifier detected. GDPR Recital 30 and CCPA §1798.140 cover "
        "device and advertising identifiers that can single out a person or household. "
        "Mask before send."
    ),
    "device_serial_number": (
        "Device serial number detected. HIPAA 45 CFR §164.514 lists device identifiers "
        "and serial numbers; GDPR Recital 30 and CCPA §1798.140 cover device identifiers. "
        "Mask unless disclosure is purpose-limited."
    ),
    "eu_national_id": (
        "EU national identity / personal identifier detected. GDPR Art 4(1) treats direct "
        "and indirect identifiers as personal data, and Art 87 permits member-state rules "
        "for national identification numbers. Mask unless a lawful basis and recipient "
        "purpose are documented."
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
    "us_itin": (
        "US Individual Taxpayer Identification Number is an IRS-issued taxpayer identifier "
        "for individuals who are not eligible for SSNs. Treat as high-risk personal data "
        "under US sectoral and state privacy law; mask unless the tax-administration "
        "recipient and purpose are documented."
    ),
    "us_driver_license": (
        "US driver-license number is a government-issued license identifier. HIPAA 45 CFR "
        "§164.514 lists certificate/license numbers in the de-identification safe harbor, "
        "and CCPA §1798.140 covers government identifiers. Mask unless the recipient and "
        "lawful purpose are documented."
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
    "sg_ipos_tm_number": (
        "Singapore IPOS trade-mark application or registration number identifies an IP "
        "asset and dispute/application record. In a pre-send legal or transaction memo, "
        "treat as matter-identifying confidential information and mask unless disclosure "
        "is intended and documented."
    ),
    "sg_acra_transaction_number": (
        "Singapore ACRA / Bizfile transaction or filing reference identifies a corporate-"
        "registry lodgement workflow. In a private corporate-secretarial or deal document, "
        "mask unless the recipient and purpose are documented under PDPA s18 and the "
        "Companies Act filing context."
    ),
    "sg_hdb_reference": (
        "Singapore HDB flat-purchase / resale / HFE references identify a housing matter "
        "and can link named applicants, sellers, occupiers, and property details. Treat "
        "as personal data under PDPA s2 and mask unless disclosure is purpose-limited."
    ),
    "sg_sla_lot_number": (
        "Singapore SLA MK/TS land, strata, or accessory lot number identifies a specific "
        "land or strata parcel. In conveyancing, financing, or dispute context it links "
        "parties to property interests and should be masked unless disclosure is intended."
    ),
    "sg_sla_title_plan_number": (
        "Singapore SLA title-plan / strata-title plan reference identifies a property-"
        "title record or management-corporation strata title plan. Mask in private legal "
        "or real-estate documents unless the recipient and purpose are documented."
    ),
    "sg_ura_planning_reference": (
        "Singapore URA planning submission / decision reference identifies a development-"
        "control application or written-permission record. In pre-send real-estate, "
        "financing, or corporate documents, mask unless disclosure is intended and documented."
    ),
    "sg_insurance_policy_number": (
        "Singapore insurance policy / certificate / claim reference identifies a policyholder, "
        "insured asset, beneficiary, or claim workflow in private documents. Treat as "
        "matter-identifying personal or confidential information under PDPA s2/s18 and mask "
        "unless disclosure is intended."
    ),
    "crypto_wallet_address": (
        "Crypto wallet / DPT address detected in a labelled transfer or VASP context. "
        "Wallet addresses can identify customers or counterparties when paired with KYC, "
        "matter, or transaction context; MAS DPT controls and PDPA purpose-limitation "
        "expectations apply. Mask unless disclosure is documented."
    ),
    "sg_tribunal_reference": (
        "Singapore tribunal / regulator dispute reference detected. In SCT, ECT, CDRT, "
        "STB, PDPC, or IPOS matter context, the reference can link parties to private "
        "claims or complaints. Mask unless recipient and purpose are documented."
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
    "internal_session_id": (
        "Internal session / user token is pseudonymised-but-linkable personal data when "
        "the organisation retains logs or account records that can re-link the token to a "
        "person. GDPR Recital 26 + PDPC Anonymisation Advisory Guidelines apply; mask "
        "before external disclosure unless the recipient and purpose are documented."
    ),
    "bank_customer_reference": (
        "Bank CIF / customer reference is pseudonymised-but-linkable personal data and "
        "may identify a financial customer through the bank's internal records. GDPR "
        "Recital 26 + PDPC Anonymisation Advisory Guidelines apply, with financial-sector "
        "confidentiality expectations. Mask unless disclosure is intended and approved."
    ),
    "insurance_member_id": (
        "Insurance member / certificate identifier is pseudonymised-but-linkable personal "
        "data: the insurer or plan administrator can re-link it to the policyholder, "
        "insured member, beneficiary, or claim. GDPR Recital 26 + PDPC Anonymisation "
        "Advisory Guidelines apply. Mask unless disclosure is intended and approved."
    ),
    "quasi_identifier_combination": (
        "Three or more distinct quasi-identifiers co-occur within a 500-character window. "
        "Under PDPA s2 ('identified from that data and other information'), GDPR Recital "
        "26 ('means reasonably likely to be used'), and CCPA §1798.140(v) ('reasonably "
        "capable of being associated'), the combination is personal data even when the "
        "individual attributes are not. Sweeney 2000: DOB + 5-digit ZIP + gender uniquely "
        "identifies ~87% of US adults. Generalise or aggregate before disclosure."
    ),
    "cross_border_transfer_marker": (
        "Cross-border personal-data transfer marker detected. Under PDPA s26 + PDP "
        "Regulations 2021 (SG; ASEAN MCCs / RIPD MCCs joint guide released Jan 2025; "
        "APEC CBPR + PRP certifications recognised); GDPR Chapter V Arts 44-49 (EU; "
        "adequacy / SCC / BCR / certifications / derogations); UK GDPR + DPA 2018 Part 5 "
        "+ UK IDTA (UK); PIPL Art 38 + CAC + SAMR Measures for Certification of Cross-"
        "Border Personal Information Transfer (CN; effective 1 Jan 2026; GB/T 46068-2025 "
        "effective 1 Mar 2026); DPDPA 2023 s16 (IN); UAE PDPL Art 22 (UAE); KSA PDPL "
        "Art 29 (SA); LGPD Art 33 (BR) — verify the relied-on transfer mechanism is "
        "documented (SCC executed / BCR approved / adequacy in force / consent obtained) "
        "before disclosure. Item 53 cadence owns the in-force statute revision."
    ),
    "consent_withdrawal_marker": (
        "Consent-withdrawal / data-subject-rights marker detected. Under PDPA s16 + "
        "PDPC Advisory Guidelines on Anonymisation (SG); GDPR Art 7(3) ('as easy to "
        "withdraw as to give') + Art 17 (erasure) + Art 21 (objection) + Art 16 "
        "(rectification) (EU); UK GDPR Art 17/21 + DPA 2018 s47 (UK); CCPA/CPRA "
        "§1798.105 (delete) / §1798.120 (do-not-sell) / §1798.125 (right-to-know) "
        "(US-CA); DPDPA 2023 s12 (correction + erasure) + s13 (grievance redressal) "
        "(IN); LGPD Art 18 (BR); APPI Art 30 (cessation of use) (JP); PIPA Art 36 "
        "(deletion) (KR); PIPL Art 47 (deletion) (CN); HK PDPO s26 (HK); AU Privacy "
        "Act APP 11.2 (AU) — confirm the request is logged, scoped, and acted on "
        "within the statutory deadline before forwarding."
    ),
    # item 98: special-category PII v1 seed.
    "religious_belief": (
        "Religious-belief reference detected (item 98). Under GDPR Art 9(1) "
        "('religious or philosophical beliefs' is verbatim special category); PIPA "
        "Korea Art 23 ('ideology, belief'); APPI Japan Art 2(3) ('creed' covers "
        "religion); LGPD Brazil Art 5(II); PIPL China Art 28 (religion as sensitive "
        "PI); UAE PDPL Art 15 + KSA PDPL Art 6 (religious belief sensitive); PDPC "
        "SG Advisory Guidelines on Key Concepts (Oct 2024 revision) treats religion "
        "as warranting higher standard of protection. DPDPA India has no sensitive-"
        "data tier; SDF designation (s10) is the escalation mechanism. Detector "
        "flags presence; downstream legal review required for jurisdiction-specific "
        "permissibility (e.g., KSA Basic Law Art 1 + 26 on state religion; UAE "
        "Federal Decree-Law 34/2023 on religious denigration). Mask, redact, or "
        "remove before disclosure unless explicit consent is on file."
    ),
    "trade_union_membership": (
        "Trade-union membership reference detected (item 98). Under GDPR Art 9(1) "
        "('trade union membership' is verbatim special category); PIPA Korea Art 23 "
        "(labor union membership); LGPD Brazil Art 5(II) (trade union + political/"
        "religious/philosophical organisation membership); UAE PDPL Art 15 + KSA "
        "PDPL Art 6 (where applicable). APPI Japan and PIPL China do NOT explicitly "
        "enumerate union membership — kaypoh still surfaces under GDPR / PIPA / LGPD "
        "scope. Mask before disclosure; collective-bargaining + industrial-action "
        "markers also trigger this rule."
    ),
    "political_opinion": (
        "Political-opinion / party-affiliation reference detected (item 98). Under "
        "GDPR Art 9(1) ('political opinions' is verbatim special category); PIPA "
        "Korea Art 23 (political views); APPI Japan Art 2(3) ('creed' covers "
        "political opinion); LGPD Brazil Art 5(II); UAE PDPL Art 15 + KSA PDPL Art "
        "6 (political belief sensitive). PIPL China Art 28 does NOT explicitly "
        "enumerate political opinion — kaypoh still surfaces under GDPR / PIPA / "
        "APPI / LGPD scope. Detector flags presence; jurisdiction-specific permis"
        "sibility analysis is downstream of detection. Mask before disclosure."
    ),
    "health_condition": (
        "Health-condition / diagnosis reference detected (item 105). Under GDPR Art "
        "9(1), data concerning health is special-category personal data; HIPAA 45 "
        "CFR §164.514 and HHS de-identification guidance treat health information "
        "linked to identifiers as PHI and require removal of medical record numbers "
        "and other identifying health fields for safe-harbor de-identification; "
        "PDPC SG Healthcare Sector Advisory Guidelines apply PDPA consent, purpose, "
        "and protection obligations to healthcare institutions. PIPL China Art 28 "
        "also enumerates medical-health status as sensitive personal information. "
        "Mask before disclosure unless explicit consent, statutory authority, or a "
        "documented care/payment purpose is on file."
    ),
    "medical_treatment": (
        "Medication / treatment reference detected (item 105). Treatment, therapy, "
        "prescription, and procedure details reveal data concerning health under "
        "GDPR Art 9(1). HIPAA protects individually identifiable information about "
        "the provision of health care and requires medical identifiers and unique "
        "health-record characteristics to be removed for safe-harbor de-identifica"
        "tion under 45 CFR §164.514. PDPC SG Healthcare Sector Advisory Guidelines "
        "apply PDPA purpose and consent limits to medical-care data. Mask before "
        "external disclosure unless the recipient and lawful medical purpose are "
        "documented."
    ),
    "biometric_identifier": (
        "Biometric identifier reference detected (item 106). GDPR Art 9(1) treats "
        "biometric data processed for uniquely identifying a natural person as "
        "special-category personal data; GDPR Recital 51 clarifies that ordinary "
        "photographs are not automatically special-category biometric data unless "
        "processed by specific technical means for unique identification or "
        "authentication. HIPAA 45 CFR §164.514 safe harbor enumerates biometric "
        "identifiers, including finger and voice prints, as identifiers to remove. "
        "PIPL China Art 28 also enumerates biometrics as sensitive personal "
        "information. Mask biometric templates, hashes, scans, and authentication "
        "records before disclosure unless explicit consent and purpose are on file."
    ),
    "genetic_data": (
        "Genetic-data reference detected (item 106). GDPR Art 9(1) treats genetic "
        "data as special-category personal data; HIPAA / HHS de-identification "
        "guidance treats unique health-record characteristics and linked health "
        "information as PHI; PIPL China Art 28 treats medical-health status and "
        "related sensitive personal information as requiring strict protection. "
        "Mask DNA profiles, genetic-test results, genome sequences, carrier status, "
        "and pathogenic-variant references before disclosure unless explicit "
        "consent or statutory authority is documented."
    ),
    "sexual_orientation": (
        "Sexual-orientation reference detected (item 108). GDPR Art 9(1) lists a "
        "natural person's sexual orientation as special-category personal data. "
        "PDPC SG Key Concepts guidance still treats the underlying facts as "
        "personal data when the individual is identifiable, and the project applies "
        "the higher-protection special-category posture for pre-send review. Mask "
        "or remove before disclosure unless explicit consent and purpose are "
        "documented."
    ),
    "sex_life_reference": (
        "Sex-life reference detected (item 108). GDPR Art 9(1) lists data "
        "concerning a natural person's sex life as special-category personal data. "
        "Where the same passage includes health or treatment details, HIPAA / HHS "
        "PHI principles may also apply in US healthcare context. Mask or remove "
        "before disclosure unless explicit consent, statutory authority, or a "
        "documented care purpose is on file."
    ),
    # item 107: jurisdiction-age-cliff minors detector.
    "minor_data_reference": (
        "Minor / children's-data reference detected (item 107). Under DPDPA India "
        "2023 s2(f) + s9 ('child' = under 18; verifiable parental consent required; "
        "s9(3) prohibits behavioural monitoring + targeted ads to children); GDPR "
        "Art 8 (default 16; member states may lower to 13 — DE/HU/IE/LU/NL/PL/RO/"
        "SK/HR retained 16; FR/GR/SI 15; AT/BG/CY/ES/IT/LT 14; BE/DK/EE/FI/LV/MT/"
        "NO/PT/SE 13); PIPL China Art 31 (under 14 = minor; guardian consent + "
        "dedicated rules); COPPA US 16 CFR Part 312 (under 13; Jan 2025 amendments "
        "tightened data retention + third-party opt-in); PDPC SG Advisory Guide"
        "lines on Children's Personal Data (Mar 2024; default under 18; under-13 "
        "cannot give valid consent); UK ICO Age-Appropriate Design Code (under 18; "
        "in force Sept 2021); AU OAIC Children's Online Privacy Code (under 18; "
        "Privacy Amendment Act 2024 mandates; OAIC code due Dec 2026); HK PCPD "
        "Minors Guidance Note (under 18); UAE PDPL via Wadeema Law (Federal Law "
        "3/2016; under 18); KSA PDPL via Saudi Child Protection Law (under 18); "
        "LGPD Brazil Art 14 (under 18; under-12 special protection). Severity "
        "resolves against the strictest applicable jurisdiction cliff. Verifiable "
        "parental / guardian consent must be on file before any processing of a "
        "child's data; targeted advertising to children is prohibited in most "
        "in-scope regimes."
    ),
    # item 102: India DPDPA recognizers.
    "in_aadhaar": (
        "India Aadhaar is a 12-digit identifier issued by UIDAI. Under DPDPA 2023 s2(t) "
        "(personal data) + s10 (Significant Data Fiduciary heightened-care) + Aadhaar Act "
        "2016 s9, masking is required before any disclosure that is not strictly necessary "
        "for the documented purpose. Verhoeff checksum validated; leading digit 2-9."
    ),
    "in_pan": (
        "India PAN is a 10-character taxpayer identifier issued by the Income Tax Department "
        "(CBDT). Personal data under DPDPA 2023 s2(t). Mask before disclosure unless the "
        "tax-administration purpose is documented and consented."
    ),
    "in_gstin": (
        "India GSTIN is a 15-character GST identification number embedding a PAN. Personal "
        "data under DPDPA 2023 s2(t) when paired with a named individual (proprietorship); "
        "commercial identifier otherwise. Mask unless the GST-administration purpose is on file."
    ),
    "in_voter_id": (
        "India Voter ID (EPIC) is an Election Commission photo-identity number. Personal "
        "data under DPDPA 2023 s2(t). Mask before disclosure unless the recipient is "
        "authorised and the purpose is documented."
    ),
    # item 103: China PIPL recognizers.
    "cn_resident_id": (
        "China Resident Identity Card number (居民身份证号) is an 18-digit identifier with "
        "embedded birth date and administrative-division code. Under PIPL 2021 Art 4 "
        "(personal information) + Art 28 (sensitive personal information when linked to "
        "biometric / health / financial-account context), masking is required. ISO 7064 "
        "MOD 11-2 checksum validated (GB 11643-1999)."
    ),
    "cn_uscc": (
        "China Unified Social Credit Code (统一社会信用代码) is an 18-character corporate "
        "identifier per GB 32100-2015. Commercial identifier; mask in shared documents that "
        "may reveal counterparty identity pre-announcement. ISO 7064 MOD 31-3 checksum "
        "validated (alphabet excludes I/O/Z/S/V)."
    ),
    "cn_phone": (
        "China mobile phone number (11-digit, starts 1[3-9]). Personal information under "
        "PIPL 2021 Art 4. Mask unless the recipient is intended and the purpose is documented."
    ),
    "cn_passport": (
        "China passport number (E/G/D + 8 digits). Personal information under PIPL 2021 "
        "Art 4 and a travel-document identifier; mask before disclosure unless explicit "
        "consent and a documented purpose are on file."
    ),
    # item 104: UAE PDPL recognizers.
    "ae_emirates_id": (
        "UAE Emirates ID is a 15-digit national identifier prefixed 784 (UAE ISO-3166). "
        "Under UAE PDPL Art 1 (personal data) + Art 15 (sensitive data when paired with "
        "religion / health / biometric context), masking is required before disclosure."
    ),
    "ae_trade_licence": (
        "UAE Trade / commercial licence number (DED / DMCC / ADGM / DIFC issuer-specific). "
        "Commercial identifier under UAE PDPL Art 1 when paired with a director name; "
        "mask in pre-announcement documents."
    ),
    "ae_passport": (
        "UAE passport number (single letter + 8 digits). Personal data under UAE PDPL Art 1 "
        "and a travel-document identifier; mask before disclosure unless documented consent."
    ),
    # item 104: KSA PDPL recognizers.
    "sa_national_id": (
        "KSA National ID is a 10-digit identifier (1 = citizen, 2 = resident). Under KSA "
        "PDPL 2023 (Royal Decree M/19) + SDAIA Implementing Regulations 2024 Art 6 "
        "(sensitive data when paired with religion / criminal / health context), masking "
        "is required."
    ),
    "sa_iqama": (
        "KSA Iqama is a 10-digit residence permit (starts with 2). Personal data under "
        "KSA PDPL 2023. Mask before disclosure unless the recipient is authorised."
    ),
    "sa_commercial_registration": (
        "KSA Commercial Registration (CR) is a 10-digit business identifier. Commercial "
        "identifier under KSA PDPL when paired with a director name; mask in pre-"
        "announcement documents."
    ),
    "data_minimisation_marker": (
        "Data-minimisation / over-collection marker detected. Under GDPR Art 5(1)(c) + "
        "UK GDPR Art 5(1)(c) ('adequate, relevant and limited to what is necessary'); "
        "PDPA s18 + Notification Obligation (SG); PIPL Art 6 (CN); LGPD Art 6 II "
        "('necessidade') (BR); DPDPA 2023 s5 (IN); HIPAA Minimum Necessary Standard "
        "45 CFR §164.502(b) (US-health) — verify the collected fields are limited to "
        "the documented purpose. Recent enforcement: CNIL fined Free Mobile €27M "
        "(early 2026) for retention failures."
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
    "conjunctive_mnpi": (
        "Layer-2 conjunctive MNPI finding detected: entity/deal and non-public elements co-occur, "
        "with materiality recorded in finding metadata as lexicalised, quantitative, implied, or "
        "undetermined. Under SFA s218/s219, MAR Art 7/14, Reg FD 17 CFR 243.100, and local "
        "inside-information rules, hold or cite a public source until reviewer approval."
    ),
    "contract_unit_price": (
        "Contract unit price / per-unit economics detected. In commercial, procurement, "
        "licensing, or M&A context, unit economics can be price-sensitive or competitively "
        "confidential. Verify public disclosure before sending externally."
    ),
    "contract_discount_rate": (
        "Contract discount or rebate rate detected. Customer-specific pricing concessions "
        "can be commercially sensitive MNPI or confidential negotiation information. "
        "Generalise or hold unless disclosure is approved."
    ),
    "volume_commitment": (
        "Contract volume commitment detected. Minimum purchase, seat, licence, energy, or "
        "supply commitments can be material to issuer forecasts and commercial negotiations. "
        "Verify public status before external disclosure."
    ),
    "royalty_rate": (
        "Royalty rate detected. Licence economics can disclose confidential valuation, IP, "
        "or revenue-share terms. Hold or generalise unless disclosure is intended and approved."
    ),
    "total_contract_value": (
        "Total contract value detected. Aggregate contract value can be material to revenue "
        "forecasts or deal economics. Verify public disclosure or redact before sending."
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
    "insider_list_marker": (
        "Insider-list / wall-cross marker detected. Under MAR Art 18 (EU/UK — mandatory "
        "insider-list maintenance), FINRA Rule 5280 (US watch/restricted lists), "
        "SFA s218 + SGX Mainboard Listing Rule 1207(6A) (SG), and Corporations Act "
        "s1043F (AU), persons added to such lists are presumed to be in possession of "
        "inside information. Confirm the recipient is on the maintained insider list and "
        "that the disclosure is recorded before forwarding."
    ),
    "information_barrier_marker": (
        "Information-barrier marker detected. Under FCA SYSC 10 + FSA COB 11.4 (UK), "
        "FINRA Rule 5280 (US), MAS Notice SFA 04-N16 (SG), and MAR Art 11 (EU market "
        "soundings), information barriers (Chinese walls / ethical screens) restrict the "
        "flow of inside information between business units. References to crossing or "
        "breaching a barrier are presumptively MNPI-handling events; confirm the recipient "
        "is on the appropriate side of the barrier before forwarding."
    ),
    "dpt_pre_listing_marker": (
        "Digital-asset pre-listing / enforcement marker detected. Under MAS Notice PSN02 "
        "(2 Apr 2024, revised 30 Jun 2025) + Payment Services Act 2019 s6 (DPT licensing) "
        "+ MAS Guidelines on Digital Token Offerings (SG); US Securities Act §5 + Howey + "
        "SEC Reg FD as applied to token issuers; MiCA Title II (EU asset-referenced + "
        "e-money tokens); SFO Cap 571 + SFC VATP Position Paper (HK) — token-launch, "
        "exchange-listing, and enforcement-action language is MNPI pre-public-announcement. "
        "Hold until publicly disclosed or generalise the claim."
    ),
    "dpt_protocol_event_marker": (
        "Digital-asset protocol-event marker detected. Hard forks, governance proposals, "
        "validator slashing, and staking-rewards changes are price-sensitive token-issuer "
        "events under MAS Notice PSN02 + Payment Services Act 2019 (SG), SEC Reg FD as "
        "applied to token issuers (US), MiCA Art 88 (EU significant ART/EMT events), and "
        "SFC VATP Code (HK). Hold until publicly disclosed."
    ),
    "esg_climate_pre_disclosure": (
        "ESG / climate pre-disclosure marker detected. Under SGX Listing Rule 711A/711B + "
        "ISSB IFRS S2 (Scope 1+2 mandatory FYC 2025; Scope 3 mandatory for STI constituents "
        "FYC 2026) (SG); EU CSRD Directive 2022/2464 + ESRS Delegated Reg 2023/2772 + "
        "SFDR Reg 2019/2088 (EU); SEC Final Rule 33-11275 (US climate disclosure, partial "
        "stay pending); ISSB IFRS S1 (sustainability) — pre-disclosure climate metrics and "
        "transition-plan language are price-sensitive when the issuer is in scope of any "
        "of these regimes. Hold until publicly disclosed."
    ),
    "esg_target_revision": (
        "ESG target revision / assurance opinion detected. Restating prior-year emissions, "
        "revising a published climate target, or changing the baseline year is materially "
        "price-sensitive under SGX 711A/711B + IFRS S2 (SG), EU CSRD + ESRS (EU), and SEC "
        "Final Rule 33-11275 (US). Limited / reasonable / qualified / adverse assurance "
        "opinions on a sustainability report carry the same MNPI weight as financial-audit "
        "opinions. Hold until publicly disclosed."
    ),
    "cyber_incident_pre_disclosure": (
        "Cyber-incident pre-disclosure marker detected. Under SEC 8-K Item 1.05 (effective "
        "Dec 2023; 4-business-day window from materiality determination per SEC Division "
        "of Corp Fin C&DIs re-issued May/Jun 2024) + SEC Final Rule 33-11216 (US); NYDFS "
        "23 NYCRR 500.17 (NY FS, 72-hour notification); EU NIS2 Directive 2022/2555 "
        "(early-warning 24h / incident-notification 72h); MAS TRM Guidelines (Jan 2021) + "
        "MAS Notice 644 (SG, 1-hour notification); UK FCA SYSC 13 + PRA SS1/21 — a draft "
        "incident-disclosure or pre-determination memo is MNPI by construction. Hold until "
        "publicly disclosed or generalise the claim; verify the in-force C&DI revision per "
        "item 53 cadence before relying on the citation externally."
    ),
    "blackout_period_reference": (
        "Blackout / closed-period reference detected (item 84). Document date and a "
        "scheduled results-announcement date co-occur inside the issuer's closed period. "
        "Under SGX Mainboard Rule 1207(19)(c) (SG: 2 weeks Q1-Q3; 1 month half/full-year), "
        "HKEX Mainboard Appendix C3 / formerly Appendix 10 Model Code (HK: 30 days "
        "interim/quarterly; 60 days annual), UK MAR Article 19(11) + UKLR / former LR "
        "9.2.6 (UK/EU: 30-day closed period for PDMRs), and EU MAR Article 19(11), "
        "communications during a closed period that move price-sensitive information "
        "outside the issuer trigger insider-dealing and selective-disclosure exposure. "
        "Hold until the period ends or restrict to whitelist recipients on the maintained "
        "insider list."
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
    "IN": "Reference: India Digital Personal Data Protection Act 2023 (DPDPA) sections 2(t), 9, 10, 16.",
    "CN": (
        "Reference: China Personal Information Protection Law 2021 (PIPL) Articles 4, "
        "28, 31, 38; CSL 2016; DSL 2021."
    ),
    "AE": (
        "Reference: UAE Federal Decree-Law 45/2021 (PDPL) Articles 1, 15, 22; "
        "DIFC DPL 2020; ADGM Data Protection Regs 2021."
    ),
    "SA": (
        "Reference: KSA Personal Data Protection Law 2023 (Royal Decree M/19) + "
        "SDAIA Implementing Regulations 2024; Article 29 (cross-border)."
    ),
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
    "IN": "Reference: SEBI (Prohibition of Insider Trading) Regulations 2015.",
    "CN": "Reference: China Securities Law Articles 50-54 (insider trading).",
    "AE": "Reference: UAE Securities and Commodities Authority (SCA) market-abuse regulations.",
    "SA": "Reference: Saudi Capital Market Authority (CMA) Market Conduct Regulations.",
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
