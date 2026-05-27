# Kaypoh Statutory Coverage

> Last revised 2026-05-26. Procurement-facing artefact mapping every shipped detector to the statute it implements. Authoritative source for "what kaypoh actually detects under PDPA / GDPR / SFA / MAR / Reg FD" assertions. Companion to `ARCHITECTURE-PIVOT-24-MAY.md` §First-Principles Statutory Analysis — that section is the editorial draft; this doc is the standalone artefact a procurement reviewer can hand to compliance.

This file is regression-tested. `test/test_statutory_coverage_doc.py` asserts that every jurisdiction in `citations.py:_MNPI_JURISDICTION_SUFFIX` / `_PII_JURISDICTION_SUFFIX`, every detector rule_name in `jurisdictions_data/*.toml`, and every PII/MNPI rationale key in `citations.py` is mentioned somewhere in this file. Drift fails CI.

## Scope

Kaypoh is a pre-send document safety layer detecting **personal data (PII)** and **material non-public information (MNPI)** evidence in documents destined for GenAI prompts, email, or external sharing. It is **not** a horizontal DLP replacement (Purview / Netskope / Nightfall already compete on detector breadth). The wedge is SG/SEA-native local-ID + legal-MNPI detection with statute-cited rationales.

Citations below are reproduced from public commentary and official statute text. Statute section numbers (notably SG SFA s215/s218/s219/s221, HK SFO Cap. 571 Part XIV s270-281, JP FIEA Art 166-167, KR FSCMA Art 174-179) should be re-verified against the official statute revision in force before external use; item 53 owns this cadence.

## Jurisdictions in scope

Each jurisdiction below ships a curated TOML pack at `src/kaypoh/review/jurisdictions_data/<CODE>.toml`. Universal rules fire regardless of jurisdiction pack; jurisdiction-specific rules and statute citations require a curated pack.

| Code | Jurisdiction | PII Statute | MNPI / Inside-Information Statute |
|---|---|---|---|
| **SG** | Singapore | Personal Data Protection Act 2012 (PDPA s2, s13, s18) | Securities and Futures Act 2001 ss215, 218, 219 |
| **MY** | Malaysia | Personal Data Protection Act 2010 (PDPA Malaysia ss6-7) | Capital Markets and Services Act 2007 ss188-189 |
| **ID** | Indonesia | UU Perlindungan Data Pribadi (UU PDP) No. 27/2022 | OJK Regulation 31/POJK.04/2015 + UU Pasar Modal 8/1995 |
| **TH** | Thailand | PDPA B.E. 2562 (2019) s26 | Securities and Exchange Act B.E. 2535 ss241-243 |
| **PH** | Philippines | Data Privacy Act 2012 (RA 10173) s3(g)/(h)/(l) | Securities Regulation Code (RA 8799) s27 |
| **VN** | Vietnam | Decree 13/2023/ND-CP arts 2-3 | Law on Securities 2019 (Law No. 54/2019/QH14) art 12 |
| **HK** | Hong Kong | Personal Data (Privacy) Ordinance Cap. 486 s2 | Securities and Futures Ordinance Cap. 571 Part XIV ss270-281 |
| **AU** | Australia | Privacy Act 1988 (Cth) + Australian Privacy Principles | Corporations Act 2001 (Cth) ss1042A-1043O |
| **JP** | Japan | APPI Art 2 + My Number Act | Financial Instruments and Exchange Act Arts 166-167 |
| **KR** | South Korea | PIPA Art 2 + Art 24-2 | Financial Investment Services and Capital Markets Act Arts 174-179 |
| **US** | United States | CCPA/CPRA Cal. Civ. Code §1798.140(v); HIPAA 45 CFR §164.514; GLBA NPI | Securities Exchange Act 1934 s10(b); SEC Rule 10b-5; Reg FD (17 CFR 243.100); Basic v. Levinson |
| **UK** | United Kingdom | UK GDPR Art 4(1); Data Protection Act 2018 s3(2) | UK Market Abuse Regulation (UK MAR) Art 7 |
| **EU** | European Union | GDPR Art 4(1); Recital 26; Art 9 special-category | EU Market Abuse Regulation 596/2014 Art 7 |
| **SEA** | Southeast Asia baseline | ASEAN cross-border privacy baseline | ASEAN-baseline market-abuse principles |
| **IN** | India | Digital Personal Data Protection Act 2023 (DPDPA) ss 2(t), 9, 10, 16 | SEBI (Prohibition of Insider Trading) Regulations 2015 |
| **CN** | China | Personal Information Protection Law 2021 (PIPL) Arts 4, 28, 31, 38; CSL 2016; DSL 2021 | China Securities Law Arts 50-54 |
| **AE** | United Arab Emirates | UAE Federal Decree-Law 45/2021 (PDPL) Arts 1, 15, 22; DIFC DPL 2020; ADGM Data Protection Regs 2021 | UAE Securities and Commodities Authority (SCA) regulations |
| **SA** | Saudi Arabia | KSA Personal Data Protection Law 2023 (Royal Decree M/19) + SDAIA Implementing Regulations 2024; Art 29 (cross-border) | Saudi Capital Market Authority (CMA) Market Conduct Regulations |

## Universal PII detectors

These rules fire regardless of source/destination jurisdiction. The statutory anchor is jurisdiction-resolved at finding time via `citations.py:_PII_JURISDICTION_SUFFIX`.

| Rule | Statutory anchor (jurisdiction-resolved) | Severity | Notes |
|---|---|---|---|
| `email_address` | PDPA s2 (personal data) / GDPR Art 4(1) | medium | universal |
| `phone_number` | PDPA s2 / GDPR Art 4(1) | medium | universal |
| `passport_number` | PDPA s2 + PDPC NRIC Advisory | high | universal |
| `bank_account` | financial-identifier across PDPA + GLBA + GDPR Art 5 | high | universal |
| `named_person` | PDPA s2 / GDPR Art 4(1) — honorific-anchored | low/high | severity escalates in counterparty docs (SPA / NDA / SHA / term sheet) |
| `employee_id` | GDPR Recital 26 + PDPC Anonymisation Advisory Guidelines | medium → high | escalates to high when named_person co-occurs (item 99) |
| `customer_account_number` | GDPR Recital 26 + PDPC Anonymisation Advisory Guidelines | medium → high | escalates to high when named_person co-occurs (item 99) |
| `medical_record_number` | HIPAA 45 CFR §164.514 + GDPR Art 9 + PDPC special-category | high | already high standalone (special-category) |
| `quasi_identifier_combination` | PDPA s2 + GDPR Recital 26 + CCPA §1798.140(v) + Sweeney 2000 | medium | audit_grade only; fires when ≥3 distinct quasi-IDs cluster within 500 chars (item 101) |
| `cross_border_transfer_marker` | PDPA s26 + PDP Regulations 2021 + ASEAN MCCs + APEC CBPR (SG); GDPR Chapter V Arts 44-49 (EU); UK GDPR + DPA 2018 Part 5 + UK IDTA (UK); PIPL Art 38 + CAC + SAMR Measures 2026 + GB/T 46068-2025 (CN); DPDPA 2023 s16 (IN); UAE PDPL Art 22 (UAE); KSA PDPL Art 29 (SA); LGPD Art 33 (BR) — SCC / IDTA / adequacy / CAC / ASEAN MCCs / APEC CBPR / BCR / Schrems II / data-export vocabulary | medium | item 109; PII-handling-event lexicon under `_PII_NEGATION_GUARDED` frozenset; no MNPI co-occurrence amplifier |
| `consent_withdrawal_marker` | PDPA s16 + Advisory Guidelines on Anonymisation (SG); GDPR Art 7(3) + Art 17 + Art 21 + Art 16 (EU); UK GDPR Art 17/21 + DPA 2018 s47 (UK); CCPA/CPRA §1798.105/120/125 (US-CA); DPDPA 2023 s12 + s13 (IN); LGPD Art 18 (BR); APPI Art 30 (JP); PIPA Art 36 (KR); PIPL Art 47 (CN); HK PDPO s26 (HK); AU Privacy Act APP 11.2 (AU) — DSAR / right-to-erasure / right-to-delete / do-not-sell / objection / rectification / retention-expired vocabulary | medium | item 110; PII-handling-event lexicon under `_PII_NEGATION_GUARDED` |
| `data_minimisation_marker` | GDPR Art 5(1)(c) + UK GDPR Art 5(1)(c) ("adequate, relevant and limited to what is necessary"); PDPA s18 + Notification Obligation (SG); PIPL Art 6 (CN); LGPD Art 6 II (BR); DPDPA 2023 s5 (IN); HIPAA Minimum Necessary Standard 45 CFR §164.502(b) (US-health) — purpose-limitation / adequate-relevant-limited / over-collection / Minimum-Necessary vocabulary | medium | item 111; PII-handling-event lexicon under `_PII_NEGATION_GUARDED` |

## Jurisdiction-specific PII detectors

Each row is a TOML recognizer in `src/kaypoh/review/jurisdictions_data/<CODE>.toml`. Validator column refers to checksum / prefix-exclusion validators in `jurisdictions.py:_VALIDATORS`.

### SG (Singapore)

| Rule | Statutory anchor | Severity | Validator |
|---|---|---|---|
| `sg_nric_fin` | PDPA s13 + PDPC NRIC Advisory (effective 31 Dec 2026) | high | none |
| `sg_uen` | PDPA s18 + ACRA UEN register | high | none |
| `sg_postal_address` | PDPA s2 — residential address | medium | none |
| `sg_court_citation` | matter / counterparty identifier in pre-send legal-firm docs (SAL neutral citation form `[YYYY] SG{CODE} <num>`) | medium | none |
| `sg_paynow` | PDPA s13 + MAS PaymentServices Act 2019 + PayNow service-provider undertakings | high | none |
| `sg_mas_licence` | SFA 2001 + Financial Advisers Act 2001 (CMS / FA licensee disclosure) | medium | none |
| `sg_sgx_counter` | SFA s218 (insider trading) + SGX Mainboard Rule 703 (continuous disclosure) | low | none |

### MY / ID / TH / PH / VN

| Rule | Statutory anchor | Severity | Validator |
|---|---|---|---|
| `my_mykad` | Malaysia PDPA 2010 ss6-7 — National Registration Identity (MyKad) | high | none (dashed format only) |
| `id_nik` | UU PDP 27/2022 arts 4-10 — Nomor Induk Kependudukan (NIK) | high | none (16-digit civil-registry) |
| `th_national_id` | Thailand PDPA B.E. 2562 s26 — 13-digit national identifier | high | none (dashed format only) |
| `ph_philsys` | Philippines Data Privacy Act of 2012 (RA 10173) s3(l) — PhilSys System Number | high | none |
| `ph_tin` | RA 10173 — Tax Identification Number | medium | none |
| `vn_cccd` | Vietnam Decree 13/2023/ND-CP arts 2-3 — Căn cước công dân | high | anchored capture |

### HK / AU / JP / KR

| Rule | Statutory anchor | Severity | Validator |
|---|---|---|---|
| `hk_hkid` | PDPO Cap. 486 s2 — Hong Kong Identity Card | high | `hk_hkid` mod-11 checksum |
| `hk_cr_no` | PDPO Cap. 486 — Companies Registry / Business Registration identifier | medium | none |
| `au_tfn` | Privacy Act 1988 APP 6 — Australian Tax File Number | high | `au_tfn` mod-11 checksum |
| `au_abn` | Privacy Act 1988 APP 6 — Australian Business Number | medium | `au_abn` mod-89 checksum |
| `au_acn` | Privacy Act 1988 APP 6 — Australian Company Number | medium | `au_acn` mod-10 checksum |
| `au_postal_address` | Privacy Act 1988 APP 6 — state + 4-digit postcode | medium | none |
| `jp_my_number` | APPI Art 2 + My Number Act — Individual Number | high | `jp_my_number` mod-11 checksum |
| `jp_corporate_number` | APPI Art 2 — Corporate Number | medium | `jp_corporate_number` mod-9 checksum |
| `jp_postal_code` | APPI Art 18 — Japan Post postal code | medium | none |
| `kr_rrn` | PIPA Art 2 + Art 24-2 — Resident Registration Number | high | `kr_rrn` mod-11 checksum |
| `kr_business_registration` | PIPA Art 2 — Business Registration Number | medium | `kr_business_registration` mod-10 checksum |

### US / UK

| Rule | Statutory anchor | Severity | Validator |
|---|---|---|---|
| `us_ssn` | SSA + applicable sectoral privacy law (HIPAA / GLBA / state) | high | `us_ssn` (rejects area 000/666/9XX, group 00, serial 0000, public sentinels 078-05-1120 / 219-09-9999) |
| `us_ein` | IRS — Employer Identification Number | medium | `us_ein` (IRS prefix allowlist) |
| `uk_nin` | UK GDPR + Data Protection Act 2018 — National Insurance Number | high | `uk_nin` (HMRC prefix-exclusion: D F I Q U V first letter, O second; reserved BG/GB/KN/NK/NT/TN/ZZ) |

### IN (India) — item 102

| Rule | Statutory anchor | Severity | Validator |
|---|---|---|---|
| `in_aadhaar` | DPDPA 2023 s2(t) + Aadhaar Act 2016 s9 — UIDAI 12-digit identifier | high | `in_aadhaar` (Verhoeff checksum per UIDAI; leading digit 2-9; rejects all-same-digit + known test vectors) |
| `in_pan` | DPDPA 2023 s2(t) + Income Tax Department (CBDT) — Permanent Account Number | high | `in_pan` (format `[A-Z]{3}[PCHFATBLJG][A-Z]\d{4}[A-Z]`; 4th letter encodes entity type) |
| `in_gstin` | DPDPA 2023 s2(t) — Goods and Services Tax Identification Number | medium | format-only in v1 (Luhn MOD 36 checksum deferred to v2) |
| `in_voter_id` | DPDPA 2023 s2(t) — Election Commission Photo Identity Card (EPIC) | medium | none (format `[A-Z]{3}\d{7}` with Voter ID / EPIC context anchor) |

### CN (China) — item 103

| Rule | Statutory anchor | Severity | Validator |
|---|---|---|---|
| `cn_resident_id` | PIPL 2021 Art 4 + Art 28 (sensitive PI) — 居民身份证号 18-digit | high | `cn_resident_id` (ISO 7064 MOD 11-2 per GB 11643-1999; supports `X` tail) |
| `cn_uscc` | GB 32100-2015 — Unified Social Credit Code 18-char corporate identifier | medium | `cn_uscc` (ISO 7064 MOD 31-3; alphabet excludes I/O/Z/S/V) |
| `cn_phone` | PIPL 2021 Art 4 — China mobile phone (11-digit, starts 1[3-9]) | medium | none (context-anchored on 手机 / 电话 / Mobile / Phone) |
| `cn_passport` | PIPL 2021 Art 4 — China passport (`[EGD]\d{8}`) | high | none |

### AE (United Arab Emirates) — item 104

| Rule | Statutory anchor | Severity | Validator |
|---|---|---|---|
| `ae_emirates_id` | UAE PDPL Art 1 + Art 15 (sensitive) — Emirates ID 15-digit (784-prefix) | high | `ae_emirates_id` (format + 784 prefix; government checksum not publicly documented per web search 2026-05-27) |
| `ae_trade_licence` | UAE PDPL Art 1 — DED / DMCC / ADGM / DIFC commercial licence | medium | none (issuer-context anchored) |
| `ae_passport` | UAE PDPL Art 1 — UAE passport (`[A-Z]\d{8}`) | high | none |

### SA (Saudi Arabia) — item 104

| Rule | Statutory anchor | Severity | Validator |
|---|---|---|---|
| `sa_national_id` | KSA PDPL 2023 + SDAIA Implementing Regulations 2024 Art 6 (sensitive) — 10-digit (1 = citizen / 2 = resident) | high | `sa_national_id` (format + leading-digit; Saudi MOI checksum not publicly documented per web search 2026-05-27) |
| `sa_iqama` | KSA PDPL 2023 — 10-digit residence permit (starts with 2) | high | `sa_iqama` (format + leading-digit-2) |
| `sa_commercial_registration` | KSA PDPL 2023 — 10-digit Commercial Registration (CR) | medium | none (Arabic + English context anchored on `CR No.` / `سجل تجاري`) |

## MNPI / inside-information detectors

These rules fire regardless of jurisdiction; the statutory anchor is jurisdiction-resolved at finding time via `citations.py:_MNPI_JURISDICTION_SUFFIX`.

| Rule | Statutory anchor (jurisdiction-resolved) | Severity | Notes |
|---|---|---|---|
| `material_event` | SFA s218 / SEC Rule 10b-5 / MAR Art 7 / SFO Part XIV / Basic v. Levinson | medium-high | severity high when paired with non-public marker; low when paired with in-doc URL self-citation (item 36) |
| `nonpublic_marker` | universal "confidential / non-public / embargo" language | high | |
| `transaction_codename` | SFA s215 + MAR Art 7 — `Project <CapitalizedName>` deal codename | high | |
| `definitive_agreement` | SFA s215 + MAR Art 7 — SPA / SHA / APA / MOU / LOI / term sheet | high | |
| `material_adverse_change` | MAC / MAE clause language; price-sensitive | high | with negation guard against "no MAC" / "without MAC" |
| `embargo_marker` | embargo / signing date / closing date / effective date markers | high | |
| `financial_amount` | exact monetary scalar (potential MNPI under SAB No. 99) | medium | |
| `financial_percentage` | exact percentage scalar | medium | |
| `large_number` | large numeric value | medium | |
| `contingent_mnpi_language` | Basic v. Levinson + MAR Art 7(2-3) + SFA s215 — contingent / probabilistic / pre-decisional language ("subject to board approval", "in discussions", "management believes", gated "likely/expected to close|approve|materialise") | low → medium | item 95; co-occurrence amplifier escalates to medium when within ±200 chars of a deal substrate |
| `tipping_language` | SFA s219 + Rule 10b5-2 + MAR Art 14 + SFO Part XIV — passing-on / forwarding / select-distribution language | low → medium | item 96; same ±200 char amplifier |
| `selective_disclosure_risk` | 17 CFR 243.100 (Reg FD) §100(b)(1)(i-iv) recipient categories — brokers/dealers, investment advisers / 13F filers, investment companies, holders of issuer's securities reasonably foreseeable to trade | low → medium | item 97; **US-only** (registers into the post-pass only when packs include US); same ±200 char amplifier |
| `insider_list_marker` | MAR Art 18 (EU/UK insider-list maintenance) + FINRA Rule 5280 (US watch/restricted list) + SFA s218 + SGX Mainboard Listing Rule 1207(6A) (SG) + Corporations Act s1043F (AU) — list-maintenance + wall-cross-event vocabulary | low → medium | item 115; same ±200 char amplifier; negation guard reused |
| `information_barrier_marker` | FCA SYSC 10 + FSA COB 11.4 (UK information barriers) + FINRA Rule 5280 (US) + MAS Notice SFA 04-N16 (SG) + MAR Art 11 (EU market soundings) — barrier-existence vocabulary | low → medium | item 115; same ±200 char amplifier; negation guard reused |
| `dpt_pre_listing_marker` | MAS Notice PSN02 (2 Apr 2024, revised 30 Jun 2025) + Payment Services Act 2019 s6 + MAS Guidelines on Digital Token Offerings (SG); US Securities Act §5 + Howey + SEC Reg FD; MiCA Title II (EU); SFO Cap 571 + SFC VATP Position Paper (HK) — token-launch / TGE / airdrop / exchange-listing / enforcement vocabulary | low → medium | item 112; `TGE` case-locked; same ±200 char amplifier; negation guard reused |
| `dpt_protocol_event_marker` | MAS Notice PSN02 + Payment Services Act 2019 (SG); SEC Reg FD as applied to token issuers (US); MiCA Art 88 (EU significant ART/EMT events); SFC VATP Code (HK) — protocol-event / governance / staking-rewards vocabulary | low → medium | item 112; same ±200 char amplifier; negation guard reused |
| `esg_climate_pre_disclosure` | SGX Listing Rule 711A/711B + ISSB IFRS S2 (SG; Scope 1+2 mandatory FYC 2025, Scope 3 STI-constituents FYC 2026) + EU CSRD Directive 2022/2464 + ESRS Delegated Reg 2023/2772 + SFDR Reg 2019/2088 (EU) + SEC Final Rule 33-11275 (US, partial stay) + ISSB IFRS S1 — Scope / tCO2e / SBTi / transition-plan vocabulary | low → medium | item 113; `Scope 1/2/3` case-locked; same ±200 char amplifier; negation guard reused |
| `esg_target_revision` | SGX 711A/711B + IFRS S2 (SG) + EU CSRD + ESRS (EU) + SEC Final Rule 33-11275 (US) — revise / restate / change-baseline / assurance-opinion vocabulary | low → medium | item 113; same ±200 char amplifier; negation guard reused |
| `cyber_incident_pre_disclosure` | SEC 8-K Item 1.05 (effective Dec 2023; 4-business-day window from materiality determination, C&DIs re-issued May/Jun 2024) + SEC Final Rule 33-11216 (US); NYDFS 23 NYCRR 500.17 (72h, NY FS); EU NIS2 Directive 2022/2555 (24h early-warning / 72h notification); MAS TRM Guidelines + MAS Notice 644 (1h, SG); UK FCA SYSC 13 + PRA SS1/21 — materiality-determination / ransomware / exfiltration / lateral-movement / 8-K timer vocabulary | low → medium | item 114; same ±200 char amplifier; negation guard reused; item-88 statute-drift watcher tracked |
| `blackout_period_reference` | SGX Mainboard Rule 1207(19)(c) (SG: 2 weeks Q1-Q3; 1 month half/full-year); HKEX Mainboard Appendix C3 / formerly Appendix 10 Model Code, renumbered Update 91 (HK: 30 days interim/quarterly; 60 days annual); UK MAR Article 19(11) + UKLR / former LR 9.2.6 (UK: 30-day closed period for PDMRs); EU MAR Article 19(11) — fires when document-date and a scheduled results-announcement date co-occur inside the per-juris closed period | medium | item 84; calendrical detector with per-jurisdiction window registry; US Reg FD has no codified duration and is intentionally not registered |

## Cross-cutting doctrinal coverage

- **Quasi-identifier reasoning** — PDPA s2 ("identified from that data and other information"), GDPR Recital 26 ("means reasonably likely to be used"), CCPA §1798.140(v) ("reasonably capable of being associated"), Sweeney 2000 (DOB+ZIP+gender → 87% re-identification). Implemented as `quasi_identifier_combination` (item 101).
- **Cross-border personal-data transfer** — PDPA s26 + PDP Regulations 2021 (SG) + ASEAN MCCs joint guide Jan 2025 + APEC CBPR; GDPR Chapter V (EU); UK GDPR + DPA 2018 Part 5 + UK IDTA (UK); PIPL Art 38 + CAC + SAMR Measures effective 1 Jan 2026 + GB/T 46068-2025 effective 1 Mar 2026 (CN); DPDPA s16 (IN); UAE PDPL Art 22 (UAE); KSA PDPL Art 29 (SA); LGPD Art 33 (BR). Implemented as `cross_border_transfer_marker` (item 109).
- **Consent withdrawal + data-subject rights** — PDPA s16 (SG); GDPR Art 7(3) + Art 17 + Art 21 + Art 16 (EU); UK GDPR Art 17/21 + DPA 2018 s47 (UK); CCPA/CPRA §1798.105/120/125 (US-CA); DPDPA s12+s13 (IN); LGPD Art 18 (BR); APPI Art 30 (JP); PIPA Art 36 (KR); PIPL Art 47 (CN); HK PDPO s26 (HK); AU APP 11.2 (AU). Implemented as `consent_withdrawal_marker` (item 110).
- **Data-minimisation / purpose limitation** — GDPR Art 5(1)(c) + UK GDPR Art 5(1)(c); PDPA s18 (SG); PIPL Art 6 (CN); LGPD Art 6 II (BR); DPDPA s5 (IN); HIPAA Minimum Necessary Standard §164.502(b) (US). Implemented as `data_minimisation_marker` (item 111).
- **Pseudonymised-but-linkable identifiers** — GDPR Recital 26 + PDPC Anonymisation Advisory Guidelines treat IDs the controller can re-link as personal data. Implemented as `employee_id`, `customer_account_number`, `medical_record_number` with named_person co-occurrence amplifier (item 99).
- **Contingent / forward-looking MNPI** — Basic v. Levinson + MAR Art 7(2-3) + SFA s215. Implemented as `contingent_mnpi_language` with co-occurrence amplifier (item 95).
- **Tipping co-extensivity** — SFA s219 + Rule 10b5-2 + MAR Art 14 + SFO Part XIV. Implemented as `tipping_language` with co-occurrence amplifier (item 96).
- **Selective disclosure (Reg FD)** — 17 CFR 243.100. Implemented as `selective_disclosure_risk`, US-only, with co-occurrence amplifier (item 97).
- **Insider-list / wall-cross markers** — MAR Art 18 + FINRA Rule 5280 + SFA s218 + SGX 1207(6A) + Corporations Act s1043F. Implemented as `insider_list_marker` with co-occurrence amplifier (item 115).
- **Information-barrier markers** — FCA SYSC 10 + FSA COB 11.4 + FINRA Rule 5280 + MAS Notice SFA 04-N16 + MAR Art 11. Implemented as `information_barrier_marker` with co-occurrence amplifier (item 115).
- **Crypto / digital-asset pre-listing + enforcement** — MAS PSN02 + Payment Services Act 2019 + MAS Digital Token Offerings + US Securities Act §5 + Howey + MiCA Title II + SFO Cap 571. Implemented as `dpt_pre_listing_marker` with co-occurrence amplifier (item 112).
- **Crypto / digital-asset protocol events** — MAS PSN02 + Payment Services Act 2019 + SEC Reg FD applied to token issuers + MiCA Art 88 + SFC VATP Code. Implemented as `dpt_protocol_event_marker` with co-occurrence amplifier (item 112).
- **ESG / climate pre-disclosure** — SGX 711A/711B + IFRS S1/S2 + EU CSRD + ESRS + SFDR + SEC 33-11275. Implemented as `esg_climate_pre_disclosure` with co-occurrence amplifier (item 113).
- **ESG / target revision + assurance opinion** — SGX 711A/711B + IFRS S2 + EU CSRD + ESRS + SEC 33-11275. Implemented as `esg_target_revision` with co-occurrence amplifier (item 113).
- **Cyber-incident pre-disclosure** — SEC 8-K Item 1.05 + Final Rule 33-11216 + NYDFS 500.17 + NIS2 + MAS TRM + Notice 644 + FCA SYSC 13 + PRA SS1/21. Implemented as `cyber_incident_pre_disclosure` with co-occurrence amplifier (item 114). Item-88 statute-drift watcher tracks C&DI revisions.
- **Quiet-period / blackout-window calendrical reasoning** — SGX MB 1207(19)(c) + HKEX MB App C3 + UK MAR Art 19(11) + EU MAR Art 19(11). Implemented as `blackout_period_reference` (item 84). US Reg FD has no codified duration and is intentionally not registered. v1 ships explicit-date detection only; ticker → next-earnings-date lookup deferred to v2 (`audit_grade`).
- **Issuer-relative materiality (SAB 99 + ASX GN8)** — SEC SAB 99 5% "rule of thumb" (US) + ASX Guidance Note 8 ≥10% material / ≤5% non-material / ASX-300 halved (AU) + MAR / SGX MB 703 / HKEX 13.09 advisory-only (regulators refuse a numeric threshold). Implemented as `_scale_financial_by_entity_size` post-pass (item 73). Requires an `EntitySizeLookup` configured on the engine; otherwise emits `materiality_lookup_not_configured` degraded mode and leaves severity intact (fail-loud — no silent default).
- **Matter-scoped defined-term inheritance** — matter sits above session: defined terms accumulate at matter level and inherit into every session within that matter. Closes the 30+ document M&A case where session-scope loses inheritance once the session rotates. Implemented as `matter_store.py` mirroring `session_store.py` at `${KAYPOH_JOURNAL_DIR}/matters/{matter_id}/defined_terms.json` (item 55). Matter ID supports `{dms_vendor}:{matter_id}` composite keys aligned with iManage Work / NetDocuments matter IDs (no published cross-vendor canonical spec — opaque-key approach).
- **Jurisdiction-suffix wiring** — every MNPI finding's suggestion rationale carries the destination-jurisdiction statute suffix; cross-jurisdiction routing (e.g. source=SG, destination=US) carries BOTH suffixes. Audited by `test/test_mnpi_jurisdiction_suffix.py` (item 94).
- **Statute-citation override** — `KAYPOH_CITATIONS_OVERRIDE_DIR/{tenant_id}.toml` resolves tenant-specific internal compliance citations before the global `KAYPOH_CITATIONS_OVERRIDE` fallback. Malformed configured overrides fail closed instead of silently falling back.

## Known statutory gaps

These statutory concepts are recognised in the first-principles analysis but not yet implemented as detectors. Each maps to an open expansion-sequence item in `ARCHITECTURE-PIVOT-24-MAY.md`.

| Statutory concept | Detector gap | Item |
|---|---|---|
| DOB / age | no detector | 33 |
| IP / device / online identifier | no detector | 33 |
| US driver-license / ITIN | no detector | 33 |
| EU member-state national-IDs (DE Personalausweis, FR INSEE, etc.) | no detector | 33 |
| Broad postal-address parsing (multi-line, free-form) | only SG / JP / AU postal recognizers ship | 34 |
| General semantic PII / NER fallback | not implemented | 35 |
| Special-category PII (health diagnoses, biometric, religion, racial origin, political opinion, trade-union, sex life) — GDPR Art 9, PDPC special-cat, PIPA, APPI, LGPD, DPDPA | no detector | 71 / 98 |
| Issuer-size-relative materiality (SAB No. 99) | v1 shipped 2026-05-27 (item 73): `_scale_financial_by_entity_size` post-pass with US (SAB 99 5%) + AU (GN8 5/10% + ASX-300 halving) tier ladders; MAR/SGX/HKEX advisory-only; fail-loud via `degraded_modes` when no `EntitySizeLookup` configured. Default `EntitySizeLookup` provider implementation is operator-driven | 73 (v1 shipped) |
| Cross-document materiality (SEC v. Texas Gulf Sulphur) | v1 partial shipped 2026-05-27: matter store (item 55) provides defined-term inheritance across sessions. Combinatorial findings aggregator (full item 74) deferred — research showed matter-boundary inference without explicit ID is undecidable and risks privilege-waiver surface area | 55 (shipped) / 74 (aggregator deferred) |
| Sector-specific MNPI (pharma trial endpoints, FDA, tech sec-incident, FS regulatory action) | no sector packs | 72 |
| HK "not generally known" narrower test | retriever uses general-availability semantics | 82 |
| Quiet-period / blackout-window calendrical reasoning | v1 shipped 2026-05-27 (item 84): `blackout_period_reference` rule with SG/HK/UK/EU window registry; explicit-date detection (no ticker→earnings-date lookup; deferred v2) | 84 (v1 shipped) |
| Source-verified public-status adjudication by default | requires `audit_grade` + configured provider | 36 (shipped — explicit-states version) |
| Public-evidence retrieval for non-US jurisdictions | configured under audit_grade; HK-specific stricter threshold pending | 82 |
| Local postal-address for HK / KR | not implemented | 86 follow-up |

## Operational defensibility surfaces

The detector inventory above is one defensibility axis. The operational surfaces below are the other.

| Surface | Status | Citation |
|---|---|---|
| HMAC-chained review journal integrity | shipped | items 14, 16, 18 |
| Journal key rotation (per-org keystore) | shipped | item 14 |
| Encrypted local mapping store (Fernet, key-gated) | shipped | item 41 |
| Mapping retention / purge tooling | shipped | item 41 |
| Multi-tenant request isolation (server SKU) | shipped | item 42 |
| JWT/API-key tenant auth + RBAC | shipped | item 42 |
| SIEM export (JSON-over-syslog) | shipped | item 43 |
| Document metadata leakage review/scrub (DOCX, PDF, JPEG/PNG EXIF) | shipped | item 49 |
| Fail-closed scanned-PDF / uncertain-format gate | shipped | item 50 |
| Reviewer-mandated wait period (audit-pack export) | shipped | item 17 |
| Audit-pack reviewer roll-up (maker-checker visibility) | shipped | item 15 |
| Recall-baseline reviewer attribution | shipped | item 16 |
| Latency SLO targets in CI | partial | item 56 |
| Per-tenant citations override | backlog | item 60 |
| Subject-erasure reverse-index | backlog | item 59 |
| Reviewer identity bound to authenticated principal | backlog | item 57 |
| Local-daemon production ACL | backlog | item 58 |
| Workflow-wide fail-closed audit | backlog | item 65 |
| Binary / container metadata coverage (XLSX pivot cache, PPTX notes, EML attachments, archives) | backlog | item 61 |
| Image OCR / recognition | shipped | item 64 |

## Disclaimers

- This document is **not legal advice**. Statute citations are reproduced from public commentary and should be re-verified against the official statute in force before any externally-relied-on use.
- Detector recall and precision are locked against fixture corpora published in `docs/accuracy.md`. Those locks are regression baselines, not population-level accuracy claims.
- `audit_grade` review profile engages public-evidence retrieval and LLM adjudication; the deterministic engine ships as `strict` profile by default.
- The `quasi_identifier_combination` rule and `selective_disclosure_risk` rule are activated under `audit_grade` only — the deterministic-only `strict` profile is span-local.
- Public-status verification is **not** the same as MNPI determination; the engine surfaces evidence of MNPI for human review, not a regulatory determination.
