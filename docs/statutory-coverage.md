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

## Cross-cutting doctrinal coverage

- **Quasi-identifier reasoning** — PDPA s2 ("identified from that data and other information"), GDPR Recital 26 ("means reasonably likely to be used"), CCPA §1798.140(v) ("reasonably capable of being associated"), Sweeney 2000 (DOB+ZIP+gender → 87% re-identification). Implemented as `quasi_identifier_combination` (item 101).
- **Pseudonymised-but-linkable identifiers** — GDPR Recital 26 + PDPC Anonymisation Advisory Guidelines treat IDs the controller can re-link as personal data. Implemented as `employee_id`, `customer_account_number`, `medical_record_number` with named_person co-occurrence amplifier (item 99).
- **Contingent / forward-looking MNPI** — Basic v. Levinson + MAR Art 7(2-3) + SFA s215. Implemented as `contingent_mnpi_language` with co-occurrence amplifier (item 95).
- **Tipping co-extensivity** — SFA s219 + Rule 10b5-2 + MAR Art 14 + SFO Part XIV. Implemented as `tipping_language` with co-occurrence amplifier (item 96).
- **Selective disclosure (Reg FD)** — 17 CFR 243.100. Implemented as `selective_disclosure_risk`, US-only, with co-occurrence amplifier (item 97).
- **Jurisdiction-suffix wiring** — every MNPI finding's suggestion rationale carries the destination-jurisdiction statute suffix; cross-jurisdiction routing (e.g. source=SG, destination=US) carries BOTH suffixes. Audited by `test/test_mnpi_jurisdiction_suffix.py` (item 94).
- **Statute-citation override** — `KAYPOH_CITATIONS_OVERRIDE` per-tenant TOML substitutes internal compliance citations before the built-in lookup. Per-tenant variant (`KAYPOH_CITATIONS_OVERRIDE_DIR/{tenant_id}.toml`) is item 60 backlog.

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
| Issuer-size-relative materiality (SAB No. 99) | severity is uniform regardless of entity size | 73 |
| Cross-document materiality (SEC v. Texas Gulf Sulphur) | per-doc only; defined-term inheritance is the only cross-doc plumbing | 74 |
| Sector-specific MNPI (pharma trial endpoints, FDA, tech sec-incident, FS regulatory action) | no sector packs | 72 |
| HK "not generally known" narrower test | retriever uses general-availability semantics | 82 |
| Quiet-period / blackout-window calendrical reasoning | only explicit "Embargoed" / "Press Hold" matches | 84 |
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
| Image OCR / recognition | backlog | item 64 |

## Disclaimers

- This document is **not legal advice**. Statute citations are reproduced from public commentary and should be re-verified against the official statute in force before any externally-relied-on use.
- Detector recall and precision are locked against fixture corpora published in `docs/accuracy.md`. Those locks are regression baselines, not population-level accuracy claims.
- `audit_grade` review profile engages public-evidence retrieval and LLM adjudication; the deterministic engine ships as `strict` profile by default.
- The `quasi_identifier_combination` rule and `selective_disclosure_risk` rule are activated under `audit_grade` only — the deterministic-only `strict` profile is span-local.
- Public-status verification is **not** the same as MNPI determination; the engine surfaces evidence of MNPI for human review, not a regulatory determination.
