from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from kaypoh.backend.schemas import Classification
from kaypoh.review.citations import CitationOverrideError, mnpi_rationale, pii_rationale
from kaypoh.review.defined_terms import extract_defined_terms, is_defined_term
from kaypoh.review.entity_linker import canonical_person, strip_honorific
from kaypoh.review.jurisdictions import JurisdictionRulePack, resolve_rule_packs
from kaypoh.workflow.privacy_guard import EMAIL_RE, LONG_NUMBER_RE, MONEY_RE, PERCENT_RE, PHONE_RE

SG_NRIC_RE = re.compile(r"\b[STFGM]\d{7}[A-Z]\b", re.IGNORECASE)
# ACRA UEN: legacy 8-9 digit + check letter; new T-format.
SG_UEN_RE = re.compile(r"\b(?:\d{8,9}[A-Z]|T\d{2}[A-Z]{2}\d{4}[A-Z])\b")
PASSPORT_RE = re.compile(r"\b(?:passport|pass no\.?|passport no\.?)\s*[:#-]?\s*([A-Z0-9]{6,12})\b", re.IGNORECASE)
SG_POSTAL_RE = re.compile(r"\b(?:Singapore|S)\s*(\d{6})\b", re.IGNORECASE)
BANK_ACCOUNT_RE = re.compile(
    r"\b(?:bank account|account no\.?|acct no\.?|iban|swift)\s*[:#-]?\s*([A-Z0-9 -]{8,34})\b",
    re.IGNORECASE,
)
MATERIAL_EVENT_RE = re.compile(
    r"\b(acquisition|acquire|merger|takeover|buyout|earnings|guidance|forecast|"
    r"profit warning|dividend|buyback|bankruptcy|restructuring|layoff|fraud|"
    r"investigation|subpoena|cybersecurity|breach|financing|offering|ipo|"
    r"impairment|provision|resignation|ceo|cfo|"
    # legal-contract additions: deal-closing + definitive-agreement vocabulary
    r"definitive\s+agreement|binding\s+agreement|memorandum\s+of\s+understanding|"
    r"letter\s+of\s+intent|consummation|closing|settlement\s+agreement)\b",
    re.IGNORECASE,
)
# legal-contract MNPI rules. each compiles independently so the engine can emit a
# distinct `rule` per finding, which lets downstream suggestions cite the right thing.
TRANSACTION_CODENAME_RE = re.compile(
    # "Project Raven", "Project Atlas Holdings" — internal deal nicknames are nearly always MNPI.
    # the leading "Project" is case-insensitive; the codename token requires titlecase or all-caps
    # so we don't false-positive on "project plan" / "project status" prose.
    # whitespace between tokens is intra-line only — `\s+` would greedily consume newlines and
    # swallow the next paragraph into the matched_text.
    r"\b(?i:Project)[ \t]+(?:[A-Z][A-Za-z]+|[A-Z]{2,})(?:[ \t]+(?:[A-Z][A-Za-z]+|[A-Z]{2,})){0,2}\b"
)
DEFINITIVE_AGREEMENT_RE = re.compile(
    r"\b(?:definitive\s+agreement|binding\s+agreement|share\s+purchase\s+agreement|SPA|"
    r"shareholders'?\s+agreement|SHA|asset\s+purchase\s+agreement|APA|term\s+sheet|"
    r"memorandum\s+of\s+understanding|MOU|letter\s+of\s+intent|LOI)\b",
    re.IGNORECASE,
)
# MAC / MAE matcher. Bare `MAC` and `MAE` are deliberately NOT in the alternation: they
# collide with consumer-product references ("mac mini", "MAE Asia office") and with
# unrelated initialisms. Contracts that abbreviate themselves as "MAC" are handled by
# defined-term suppression at the engine level; bare-token MAC outside a defined-term
# context is too noisy to be useful. Cost of this tightening: a clause that uses bare
# `MAC` without "clause"/"change"/"effect" nearby is missed by the deterministic regex
# — but those documents are exactly the ones the `audit_grade` LLM tier exists to catch.
MAC_CLAUSE_RE = re.compile(
    r"\b(?:material\s+adverse\s+change|material\s+adverse\s+effect|"
    r"MAC\s+clause|MAE\s+clause|MAC\s+threshold|MAE\s+threshold)\b",
    re.IGNORECASE,
)
EMBARGO_RE = re.compile(
    # signing-date and announcement-window markers commonly used in deal comms
    r"\b(?:under\s+embargo|embargoed|press\s+hold|signing\s+date|effective\s+date|"
    r"announcement\s+date|completion\s+date|closing\s+date)\b",
    re.IGNORECASE,
)
NONPUBLIC_RE = re.compile(
    r"\b(confidential|non-public|nonpublic|not yet public|not disclosed|undisclosed|"
    r"internal only|internal circulation only|internal use only|restricted|do not distribute|"
    r"should not be distributed externally|before announcement|pre-announcement|"
    r"quiet period|material non-public information|mnpi)\b",
    re.IGNORECASE,
)
PUBLIC_RE = re.compile(r"\b(publicly announced|press release|filed|disclosed|published|reported)\b", re.IGNORECASE)
NAME_RE = re.compile(
    r"\b(?i:(?:Mr|Ms|Mrs|Mdm|Dr|Prof))\.?[ \t]+[A-Z][a-z]+"
    r"(?:[ \t]+(?:(?i:bin|binti|s/o|d/o|a/l|a/p|al)[ \t]+)?[A-Z][a-z]+){0,5}\b"
)
# items 95 + 96: contingent / forward-looking MNPI vocabulary (Basic v. Levinson, MAR Art 7(2-3),
# SFA s215). Standalone these phrases are noise; the co-occurrence amplifier in review() lifts
# severity from low to medium when a match co-locates within ±200 chars of a deal substrate
# (transaction_codename, definitive_agreement, material_adverse_change, material_event,
# embargo_marker, nonpublic_marker). Common likelihood verbs ("likely to", "expected to") are
# gated on deal-stage verbs to keep precision survivable — bare "likely to" is everywhere.
CONTINGENT_MNPI_RE = re.compile(
    r"\b("
    r"if (?:approved|the (?:deal|transaction|merger|acquisition) (?:closes|completes))|"
    r"should the board (?:agree|approve)|"
    r"subject to (?:board|shareholder|shareholders'|regulatory|management|due diligence|"
    r"financing|condition[s]?\s+precedent) (?:approval|clearance|sign[ -]off|consent)|"
    r"(?:likely|expected) to (?:close|approve|materialise|materialize|impact|complete|"
    r"result in|conclude|sign|announce)|"
    r"under (?:active )?consideration|"
    r"in (?:advanced |preliminary |early[ -]stage |ongoing )?(?:discussions|negotiations)|"
    r"exploratory(?:\s+(?:talks|discussions|stage|phase))?|"
    r"pre[ -]decisional|"
    r"management believes|"
    r"early indications suggest|"
    r"may (?:result in|lead to|trigger) (?:a |an )?(?:acquisition|merger|disposal|takeover|"
    r"restructuring|divestiture|impairment|spin[ -]off)"
    r")\b",
    re.IGNORECASE,
)
# item 99: pseudonymised-but-linkable identifiers. GDPR Recital 26 + PDPC Anonymisation
# Advisory Guidelines treat IDs that the organisation can re-link to a subject as personal
# data even when the bare token isn't immediately identifying. Each pattern is anchor-required
# (Employee ID: / EMP- / Customer Account: / ACCT- / Patient ID: / MRN:) and the capture
# group is wrapped in (?-i:...) with a digit-presence lookahead to defend against bare
# lowercase prose ("Employee ID will be linked to your NRIC") matching the capture as if
# "will" were an identifier.
EMPLOYEE_ID_RE = re.compile(
    r"(?:Employee\s+(?:ID|No\.?|Number)|EMP-|Staff\s+(?:ID|No\.?|Number))[\s:.#-]*"
    r"(?-i:(?=[A-Z0-9-]*\d)([A-Z0-9][A-Z0-9-]{3,11}))\b",
    re.IGNORECASE,
)
CUSTOMER_ACCOUNT_RE = re.compile(
    r"(?:Customer\s+(?:Account|ID|Reference)|ACCT-|CUST-|Member\s+(?:ID|No\.?|Number))[\s:.#-]*"
    r"(?-i:(?=[A-Z0-9-]*\d)([A-Z0-9][A-Z0-9-]{3,15}))\b",
    re.IGNORECASE,
)
MEDICAL_RECORD_RE = re.compile(
    r"(?:MRN|Medical\s+Record\s+(?:No\.?|Number)|Patient\s+(?:ID|No\.?|Number))[\s:.#-]*(\d{6,12})\b",
    re.IGNORECASE,
)
# item 97: Reg FD selective-disclosure red-flags (17 CFR 243.100 — verified against
# Cornell LII 2026-05-26). Vocabulary derived from Reg FD §100(b)(1) recipient categories:
#   (i)  brokers/dealers or associated persons
#   (ii) investment advisers / institutional investment managers (Form 13F filers)
#   (iii) investment companies / affiliated persons
#   (iv) holders of the issuer's securities reasonably foreseeable to trade on the info
# Fires only when packs include US (Reg FD is US-specific); subject to the same
# co-occurrence amplifier as items 95/96 — low standalone, medium when adjacent to an
# MNPI substrate within ±200 chars.
SELECTIVE_DISCLOSURE_RE = re.compile(
    r"\b("
    # analyst-day / analyst-prep — Reg FD §100(b)(1)(i)+(ii) typical recipients
    r"analyst\s+(?:day|call|q&a|breakfast|prep|briefing)|"
    r"sell-?side\s+(?:analyst|mailing|distribution|coverage|q&a|outreach)|"
    r"buy-?side\s+(?:analyst|mailing|distribution|q&a|outreach)|"
    # one-on-one / institutional meeting language — Reg FD §100(b)(1)(i-iii)
    r"one-?on-?one\s+(?:call|meeting|session|briefing)\s+with|"
    r"(?:institutional|select|preferred|key)\s+(?:investor|holder|client)s?\s+only|"
    # broker-dealer / investment adviser / 13F filer recipient categories
    r"broker-?dealer\s+(?:contact|distribution|mailing|outreach)|"
    r"investment\s+adviser\s+(?:mailing|distribution|outreach)|"
    r"13F\s+filer|"
    # Reg FD §100(b)(1)(iv) — holders of issuer's securities
    r"top-?ten\s+(?:holders|shareholders|investors)|"
    r"largest\s+institutional\s+(?:holders|shareholders|investors)"
    r")\b",
    re.IGNORECASE,
)
# item 96: tipping / forwarding language (SFA s219, Rule 10b5-2, MAR Art 14, SFO Part XIV).
# Same co-occurrence amplifier discipline as item 95 — alone these phrases are noise, but
# proximity to MNPI substrate is the tipping offence.
TIPPING_RE = re.compile(
    r"\b("
    r"please (?:share|forward|circulate|distribute) (?:with|to)\b[^\n]{0,40}|"
    r"feel free to (?:share|forward|circulate|distribute)|"
    r"passing this (?:along|on)|"
    r"for (?:distribution|circulation) to (?:clients|investors|partners|select|preferred|"
    r"institutional|limited partners)|"
    r"limited partners? list|"
    r"select (?:investors|holders|clients)|"
    r"institutional (?:investors|holders|clients) only|"
    r"(?:to|with) our (?:largest|key|preferred|select|top) (?:holders|clients|investors|"
    r"shareholders|stakeholders)|"
    r"sell[ -]side (?:mailing|distribution|q&a)|"
    r"buy[ -]side (?:mailing|distribution|q&a)"
    r")",
    re.IGNORECASE,
)
# item 115: insider-list / wall-cross markers. List-maintenance + wall-cross-event vocabulary
# anchored in MAR Art 18 (mandatory insider list), FSMA s118 (UK), FINRA Rule 5280
# (US watch/restricted list), SFA s218 + SGX Mainboard Listing Rule 1207(6A) (SG). Same
# co-occurrence amplifier discipline as items 95/96/97 — low standalone, medium when adjacent
# to MNPI substrate within ±200 chars. Negation guard reused.
INSIDER_LIST_RE = re.compile(
    r"\b("
    r"insider\s+lists?|"
    r"restricted\s+lists?|"
    r"watch\s+lists?|"
    r"wall[- ]cross(?:ed|ing|es)|"
    r"crossed?\s+over\s+the\s+wall|"
    r"brought\s+(?:them\s+|him\s+|her\s+|the\s+\w+\s+)?over\s+the\s+wall|"
    r"taken?\s+over\s+the\s+wall"
    r")\b",
    re.IGNORECASE,
)
# item 115: information-barrier markers. Barrier-existence vocabulary anchored in
# FCA SYSC 10 + FSA COB 11.4 information-barrier rules (UK), FINRA Rule 5280 (US),
# MAS Notice SFA 04-N16 + Securities and Futures Act (SG), MAR Art 11 market-soundings (EU).
INFORMATION_BARRIER_RE = re.compile(
    r"\b("
    r"chinese\s+walls?|"
    r"information\s+barriers?|"
    r"ethical\s+walls?|"
    r"ethical\s+screens?"
    r")\b",
    re.IGNORECASE,
)
# item 112: crypto / digital-asset pre-listing + enforcement markers. Token-launch / TGE /
# airdrop / unlock / exchange-listing vocabulary anchored in MAS Notice PSN02 (2 Apr 2024,
# revised 30 Jun 2025) + Payment Services Act 2019 s6 (DPT licensing) + MAS Guidelines on
# Digital Token Offerings (May 2020) (SG); SEC Securities Act §5 + Howey + Reg FD as applied
# to token issuers (US); MiCA Title II asset-referenced + e-money tokens (EU); SFO Cap 571 +
# SFC VATP Position Paper (HK). `TGE` is case-locked to defend against lowercase prose.
DPT_PRE_LISTING_RE = re.compile(
    r"\b("
    r"genesis\s+block|"
    r"mainnet\s+(?:launch|go[- ]live|activation)|"
    r"token\s+generation\s+event|"
    r"(?-i:TGE)|"
    r"airdrop\s+(?:schedule|allocation|snapshot)|"
    r"vesting\s+cliff|"
    r"unlock\s+(?:event|schedule|cliff)|"
    r"exchange\s+listing\s+(?:decision|approval|application)|"
    r"listed\s+on\s+(?:Binance|Coinbase|Kraken|OKX|Bybit|Upbit|Bitfinex|Gemini|Crypto\.com)|"
    r"wells\s+notice|"
    r"SEC\s+subpoena|"
    r"MAS\s+no[- ]action|"
    r"licence\s+revocation|"
    r"delisting\s+decision|"
    r"enforcement\s+action"
    r")\b",
    re.IGNORECASE,
)
# item 112: digital-asset protocol-event markers. Hard fork / governance / staking
# vocabulary; pre-public-announcement these are MNPI for token issuers + holders.
DPT_PROTOCOL_EVENT_RE = re.compile(
    r"\b("
    r"hard\s+fork|"
    r"chain\s+split|"
    r"consensus\s+change|"
    r"governance\s+proposal|"
    r"protocol\s+upgrade|"
    r"validator\s+slashing|"
    r"staking[- ]rewards?\s+(?:adjustment|change|reduction|increase)|"
    r"treasury\s+rebalancing|"
    r"multi[- ]sig\s+(?:transfer|movement|rotation)"
    r")\b",
    re.IGNORECASE,
)
# item 113: ESG / sustainability pre-disclosure markers. SGX Listing Rule 711A/711B + ISSB
# IFRS S2 (Scope 1+2 mandatory FY 2025; Scope 3 mandatory for STI constituents FY 2026);
# EU CSRD Directive 2022/2464 + SFDR Reg 2019/2088 + ESRS Delegated Reg 2023/2772; SEC
# Final Rule 33-11275 (climate disclosure, partial-stay pending); ISSB IFRS S1 sustainability
# disclosure. `Scope 1/2/3` are case-anchored (the GHG-Protocol convention is capital S).
ESG_CLIMATE_PRE_DISCLOSURE_RE = re.compile(
    r"\b("
    r"(?-i:Scope\s+[123])(?:\s+(?:GHG\s+)?emissions?|\s+category)?|"
    r"tCO2e|"
    r"science[- ]based\s+targets?|"
    r"SBTi[- ]validated|"
    r"transition\s+plan|"
    r"physical[- ]risk\s+assessment|"
    r"value[- ]chain\s+emissions|"
    r"materiality\s+reassessment|"
    r"climate[- ]related\s+(?:disclosures?|risks?)|"
    r"IFRS\s+S[12]\s+(?:compliance|disclosure)"
    r")\b",
    re.IGNORECASE,
)
# item 113: ESG target revision + assurance markers. Restating prior-year emissions or
# revising a published climate target is materially price-sensitive under SGX 711A/711B +
# IFRS S2 (revisions require explicit disclosure). Limited / reasonable assurance opinions
# carry the same MNPI weight as financial-audit opinions when issued on a sustainability
# report.
ESG_TARGET_REVISION_RE = re.compile(
    r"\b("
    r"revise\s+(?:downward|upward)[^.\n]{0,40}?(?:emissions?|targets?)|"
    r"restate\s+(?:prior[- ]year\s+)?(?:Scope\s+[123]|emissions?)|"
    r"change\s+(?:the\s+)?baseline\s+year|"
    r"limited\s+assurance(?:\s+opinion)?|"
    r"reasonable\s+assurance(?:\s+opinion)?|"
    r"qualified\s+opinion\s+on\s+sustainability|"
    r"adverse\s+opinion\s+on\s+sustainability|"
    r"assurance\s+scope"
    r")\b",
    re.IGNORECASE,
)
# item 114: cyber-incident pre-disclosure detector. SEC 8-K Item 1.05 (effective Dec 2023;
# 4-business-day disclosure window from MATERIALITY DETERMINATION per SEC Division of Corp
# Fin C&DIs re-issued May/Jun 2024) — a pre-determination / pre-disclosure draft is MNPI by
# construction. Co-anchored by NYDFS 23 NYCRR 500.17 (FS NY), EU NIS2 Directive 2022/2555
# (EU/UK FS), MAS TRM Guidelines (Jan 2021) + MAS Notice 644 (SG), UK FCA SYSC 13 +
# PRA SS1/21 (UK). Severity follows the co-occurrence amplifier; explicit 8-K timer /
# materiality-determination language is also detected as substrate via the 8-K phrase set.
CYBER_INCIDENT_RE = re.compile(
    r"\b("
    r"we\s+have\s+(?:determined|concluded)\s+(?:that\s+)?(?:this\s+|the\s+)?incident\s+is|"
    r"incident\s+is\s+(?:material|materially\s+impactful)|"
    r"materiality\s+determination|"
    r"material\s+cybersecurity\s+incident|"
    r"ransomware\s+(?:affecting|incident|attack|deployment)|"
    r"data\s+exfiltration\s+(?:confirmed|detected|suspected)|"
    r"unauthori[sz]ed\s+access\s+to\s+(?:production|customer|corporate|internal)|"
    r"RAT\s+detected|"
    r"lateral\s+movement(?:\s+(?:detected|observed))?|"
    r"command[- ]and[- ]control\s+(?:beacon|server|infrastructure)|"
    r"extortion\s+demand|"
    r"decryption\s+key|"
    r"8[- ]?K\s+(?:filing|Item\s+1\.05)|"
    r"Item\s+1\.05\s+(?:disclosure|filing|notification)|"
    r"4[- ]business[- ]day\s+(?:window|timer|deadline)"
    r")\b",
    re.IGNORECASE,
)
# item 109: cross-border personal-data transfer markers. Statutes: PDPA s26 + PDP Regulations
# 2021 (SG; ASEAN MCCs + RIPD MCCs released Jan 2025); GDPR Chapter V Arts 44-49 (EU); UK GDPR
# + DPA 2018 Part 5 (UK); PIPL Art 38 + CAC + SAMR Measures for Certification of Cross-Border
# Personal Information Transfer effective 1 Jan 2026 + GB/T 46068-2025 effective 1 Mar 2026
# (CN); DPDPA 2023 s16 (IN); UAE PDPL Art 22 (UAE); KSA PDPL Art 29 (SA); LGPD Art 33 (BR).
# `data export to` is constrained by a following `[a-z]` lookahead so we don't fire on
# unrelated prose like "data export tool".
CROSS_BORDER_TRANSFER_RE = re.compile(
    r"\b("
    r"transfer(?:s|red|ring)?\s+outside\s+(?:Singapore|the\s+EEA|the\s+EU|the\s+UK|the\s+Kingdom|the\s+territory)|"
    r"third[- ]country\s+(?:transfer|recipient|jurisdiction)|"
    r"standard\s+contractual\s+clauses?|"
    r"SCCs?\s+(?:executed|in\s+place|signed)|"
    r"EU\s+SCCs?|"
    r"UK\s+IDTA|"
    r"adequacy\s+(?:decision|finding|determination)|"
    r"CAC\s+security\s+assessment|"
    r"CAC\s+standard\s+contract|"
    r"China\s+SCCs?|"
    r"ASEAN\s+(?:MCCs?|Model\s+Contractual\s+Clauses)|"
    r"RIPD\s+MCCs?|"
    r"APEC\s+CBPR|"
    r"Cross[- ]Border\s+Privacy\s+Rules|"
    r"PRP\s+certification|"
    r"binding\s+corporate\s+rules|"
    r"BCRs?\s+(?:approved|in\s+place|relied\s+on)|"
    r"Schrems\s+II(?:\s+reliance)?|"
    r"personal\s+data\s+export|"
    r"data\s+export\s+to\s+(?=[A-Za-z])"
    r")\b",
    re.IGNORECASE,
)
# item 110: consent-withdrawal + data-subject-rights markers. Statutes: PDPA s16 + Advisory
# Guidelines on Anonymisation (SG); GDPR Art 7(3) + Art 17 + Art 21 + Art 16 (EU; "as easy
# to withdraw as to give"); UK GDPR Art 17/21 + DPA 2018 s47 (UK); CCPA/CPRA §1798.105/120/125
# (US-CA); DPDPA 2023 s12+s13 (IN); LGPD Art 18 (BR); APPI Art 30 (JP); PIPA Art 36 (KR);
# PIPL Art 47 (CN); HK PDPO s26 (HK); AU Privacy Act APP 11.2 (AU).
CONSENT_WITHDRAWAL_RE = re.compile(
    r"\b("
    r"withdraw(?:al)?\s+(?:of\s+)?(?:my\s+|her\s+|his\s+|their\s+)?consent|"
    r"withdrew\s+(?:my\s+|her\s+|his\s+|their\s+)?consent|"
    r"consent\s+(?:has\s+been\s+|is\s+|was\s+)?withdrawn|"
    r"data\s+subject\s+access\s+requests?|"
    r"DSARs?|"
    r"right\s+to\s+erasure|"
    r"erasure\s+requests?|"
    r"request\s+for\s+erasure|"
    r"right\s+to\s+be\s+forgotten|"
    r"right\s+to\s+delete|"
    r"do\s+not\s+sell\s+(?:my\s+)?(?:personal\s+)?(?:data|information)|"
    r"right\s+to\s+know|"
    r"data\s+deletion\s+requests?|"
    r"delete\s+(?:my|her|his|their)\s+(?:personal\s+)?data|"
    r"objection\s+to\s+processing|"
    r"right\s+to\s+object|"
    r"rectification\s+requests?|"
    r"right\s+to\s+rectification|"
    r"retention\s+period\s+(?:has\s+)?(?:expired|lapsed|elapsed)"
    r")\b",
    re.IGNORECASE,
)
# item 111: data-minimisation / over-collection markers. Statutes: GDPR Art 5(1)(c) +
# UK GDPR Art 5(1)(c) ("adequate, relevant and limited to what is necessary"); PDPA s18 +
# Notification Obligation (SG); PIPL Art 6 (CN); LGPD Art 6 II (BR); DPDPA s5 (IN);
# HIPAA Minimum Necessary Standard §164.502(b) (US). Recent enforcement: CNIL fined Free
# Mobile €27M early 2026 for retention failures.
DATA_MINIMISATION_RE = re.compile(
    r"\b("
    r"data\s+minimi[sz]ation(?:\s+principle)?|"
    r"purpose\s+limitation|"
    r"adequate,?\s+relevant\s+and\s+limited|"
    r"limited\s+to\s+what\s+is\s+necessary|"
    r"necessary\s+for\s+the\s+(?:stated\s+|specific\s+)?purpose|"
    r"collect(?:ing|ed|s)?\s+(?:more|excess(?:ive)?)\s+(?:data|personal\s+data|information)|"
    r"over[- ]collect(?:ion|ing)|"
    r"excessive\s+data\s+collection|"
    r"minimum\s+necessary\s+standard"
    r")\b",
    re.IGNORECASE,
)


SEVERITY_SCORE = {"low": 25.0, "medium": 55.0, "high": 85.0}

# document types where a named person reference is materially sensitive (counterparty principals,
# signatories, beneficial owners). lifts named_person severity from low to high.
NAMED_PERSON_HIGH_SEVERITY_DOC_TYPES = frozenset({"spa", "nda", "sha", "term_sheet", "shareholders_agreement"})

# Two-tier router defaults. The LLM tier engages when:
#   1. the review profile is `audit_grade` (caller opted in), AND
#   2. an LLM adjudicator + public-evidence retriever are wired into the engine, AND
#   3. the MNPI score lands in the ambiguous band [LLM_TIER_MNPI_LOWER, LLM_TIER_MNPI_UPPER).
# Documents with mnpi_score < LOWER are confidently SAFE on deterministic signal alone;
# documents with mnpi_score >= UPPER are confidently risky and the LLM cannot soften them
# below the deterministic-floor invariant anyway. The band keeps p95 latency bounded for
# the 90% case by only spending LLM tokens where the verdict can actually move.
#
# Defaults below were picked from the score-from-severity table:
#   single medium finding score ≈ 55; two medium findings ≈ 58; one high ≈ 85.
# So the band [25, 70) covers documents with at least one medium finding but no high.
# `scripts/calibrate_escalation_threshold.py` writes tenant-specific bounds into
# configs/runtime.py once enough journal-replay data exists.
LLM_TIER_MNPI_LOWER = 25.0
LLM_TIER_MNPI_UPPER = 70.0

VALID_REVIEW_PROFILES = frozenset({"strict", "audit_grade"})

# tokens that NAME_RE may accidentally bind as the trailing word of a multi-token name
# (e.g. "Mr Lee Ltd" → trailing "Ltd"). suppressed in the surname-only fuzzy pass so we don't
# fire on every corporate-suffix occurrence in the document.
_SURNAME_DENYLIST = frozenset({
    "ltd", "limited", "inc", "incorporated", "llc", "llp", "plc", "corp", "corporation",
    "co", "company", "gmbh", "ag", "sa", "nv", "bv", "pte", "pvt", "sdn", "bhd",
    "holdings", "industries", "ventures", "capital", "partners", "group",
})

# per-document-type MNPI severity overrides. mirrors NAMED_PERSON_HIGH_SEVERITY_DOC_TYPES.
# the deterministic engine defaults below ship the strict/high posture; overrides soften severity
# for casual-prose document types where the same vocabulary is less load-bearing, and tighten
# severity for external-memo / research-note contexts where deal vocabulary is highly sensitive.
# keyed by (rule, doc_type) -> severity; doc_type is casefolded before lookup.
MNPI_DOC_TYPE_SEVERITY_OVERRIDES: dict[tuple[str, str], str] = {
    # transaction_codename: defaults to high. softened in casual prose. retained high for memos.
    ("transaction_codename", "generic"): "medium",
    ("transaction_codename", "casual"): "medium",
    ("transaction_codename", "chat"): "medium",
    ("transaction_codename", "email_casual"): "medium",
    ("transaction_codename", "memo"): "high",
    ("transaction_codename", "research_note"): "high",
    ("transaction_codename", "external_memo"): "high",
    # definitive_agreement abbreviation context — softer in prose than in a contract face page.
    ("definitive_agreement", "generic"): "medium",
    ("definitive_agreement", "casual"): "medium",
    ("definitive_agreement", "chat"): "medium",
    # MAC clause language outside an actual contract is informational, not MNPI-grade.
    ("material_adverse_change", "generic"): "medium",
    ("material_adverse_change", "casual"): "medium",
    ("material_adverse_change", "chat"): "medium",
    # embargo markers in a memo or research note are the canonical "do not send" signal.
    ("embargo_marker", "memo"): "high",
    ("embargo_marker", "research_note"): "high",
    ("embargo_marker", "external_memo"): "high",
}


# source-verification states for MNPI findings. exposes whether a public-status check
# actually happened, so reviewers can tell "we did not look" apart from "we looked and
# found nothing". PII findings always carry `not_checked` — public-status is not a
# meaningful concept for personal data. see item 36 in ARCHITECTURE-PIVOT-24-MAY.md.
SOURCE_VERIFICATION_NOT_CHECKED = "not_checked"
SOURCE_VERIFICATION_PUBLIC_SOURCE_MATCHED = "public_source_matched"
SOURCE_VERIFICATION_NO_PUBLIC_SOURCE_FOUND = "no_public_source_found"
SOURCE_VERIFICATION_AMBIGUOUS = "ambiguous"
VALID_SOURCE_VERIFICATION = frozenset({
    SOURCE_VERIFICATION_NOT_CHECKED,
    SOURCE_VERIFICATION_PUBLIC_SOURCE_MATCHED,
    SOURCE_VERIFICATION_NO_PUBLIC_SOURCE_FOUND,
    SOURCE_VERIFICATION_AMBIGUOUS,
})

# in-document URL detector. used to honour item 36's "the document itself contains a
# citable public source reference" carve-out: a material_event sentence that contains
# a http(s) URL is treated as self-citing. conservative — does not try to distinguish
# public press wires from private wiki links; the maker/checker review is the backstop.
_INDOC_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


@dataclass
class ReviewFinding:
    id: str
    category: str
    rule: str
    jurisdiction: str
    severity: str
    score: float
    matched_text: str
    start_char: int
    end_char: int
    reason: str
    legal_basis: str
    source_verification: str = SOURCE_VERIFICATION_NOT_CHECKED
    source: str = "text"
    image_locator: dict[str, Any] | None = None
    image_ocr_confidence: float | None = None
    image_ocr_regions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ReviewSuggestion:
    id: str
    finding_id: str
    action: str
    replacement_text: str
    rationale: str


@dataclass
class ReviewResult:
    overall_risk: Classification
    document_score: float
    pii_score: float
    mnpi_score: float
    jurisdictions_applied: list[str]
    jurisdiction_policy: str
    findings: list[ReviewFinding] = field(default_factory=list)
    suggestions: list[ReviewSuggestion] = field(default_factory=list)
    public_evidence: dict[str, Any] | None = None
    llm_adjudication: dict[str, Any] | None = None
    privacy_ledger: list[dict[str, Any]] = field(default_factory=list)
    coverage_warnings: list[dict[str, Any]] = field(default_factory=list)
    degraded_modes: list[dict[str, Any]] = field(default_factory=list)


class ReviewLayerError(RuntimeError):
    """Raised when an enabled review layer fails closed at runtime."""

    def __init__(self, layer: str, message: str):
        super().__init__(message)
        self.layer = layer


def _risk_from_score(score: float) -> Classification:
    if score >= 70.0:
        return Classification.HIGH_RISK
    if score >= 35.0:
        return Classification.LOW_RISK
    return Classification.SAFE


def _line_context(text: str, start: int, end: int) -> str:
    left = text.rfind("\n", 0, start) + 1
    right = text.find("\n", end)
    if right < 0:
        right = len(text)
    return text[left:right].strip()


def _new_finding(
    *,
    idx: int,
    category: str,
    rule: str,
    jurisdiction: str,
    severity: str,
    matched_text: str,
    start: int,
    end: int,
    reason: str,
    legal_basis: str,
    source_verification: str = SOURCE_VERIFICATION_NOT_CHECKED,
) -> ReviewFinding:
    return ReviewFinding(
        id=f"{category.lower()}:{rule}:{start}:{end}:{idx}",
        category=category,
        rule=rule,
        jurisdiction=jurisdiction,
        severity=severity,
        score=SEVERITY_SCORE[severity],
        matched_text=matched_text,
        start_char=start,
        end_char=end,
        reason=reason,
        legal_basis=legal_basis,
        source_verification=source_verification,
    )


# Narrow negation-window check used by the MAC/MAE rule. Looks ~20 chars left of the match
# for a negator that immediately precedes it. Catches the common forms — "no MAC", "not a
# MAC clause", "without any MAC clause" — without trying to be a general parser. Anything
# more nuanced (subordinate clauses, double negatives) is deliberately left to the LLM tier.
_NEGATION_LOOKBACK = re.compile(
    r"\b(?:no|nor|not|without|never|absent|excluding|neither)\b[\s\w]{0,15}\Z",
    re.IGNORECASE,
)


def _is_negated_context(text: str, match_start: int) -> bool:
    window = text[max(0, match_start - 25):match_start]
    return bool(_NEGATION_LOOKBACK.search(window))


# Rules whose span "wins" over phone_number when the two overlap on the same bytes.
# These are all primary-identifier detectors: a NRIC or UEN that happens to match the
# loose PHONE_RE alternation is canonically the identifier, not a phone number.
_HIGHER_PRIORITY_THAN_PHONE = frozenset({
    "sg_nric_fin", "sg_uen",
    "my_mykad", "id_nik", "th_national_id", "ph_philsys", "ph_tin", "vn_cccd",
    "hk_hkid", "hk_cr_no", "au_tfn", "au_abn", "au_acn",
    "jp_my_number", "jp_corporate_number", "kr_rrn", "kr_business_registration",
    "passport_number", "bank_account",
})


def _apply_retrieval_verification(
    findings: list["ReviewFinding"], public_evidence: dict[str, Any] | None
) -> None:
    """Mutate MNPI findings' source_verification based on retriever output.

    Aggregate model: the retriever returns one verdict for the whole doc, so all MNPI
    findings inherit that verdict. PII findings are never touched (public-status is not
    meaningful for personal data). MNPI findings already marked public_source_matched
    by an in-doc URL (see _mnpi_findings material_event branch) are not overwritten."""
    if not public_evidence:
        return
    status = str(public_evidence.get("status") or "")
    if status != "queried":
        return
    sources = public_evidence.get("sources") or []
    unverified = public_evidence.get("unverified_claims") or []
    if sources:
        verdict = SOURCE_VERIFICATION_PUBLIC_SOURCE_MATCHED
    elif unverified:
        verdict = SOURCE_VERIFICATION_AMBIGUOUS
    else:
        verdict = SOURCE_VERIFICATION_NO_PUBLIC_SOURCE_FOUND
    for f in findings:
        if f.category != "MNPI":
            continue
        if f.source_verification == SOURCE_VERIFICATION_PUBLIC_SOURCE_MATCHED:
            continue
        f.source_verification = verdict


# items 95 + 96: rules whose severity is low standalone but escalates to medium when a
# match co-locates within ±_CO_OCCURRENCE_WINDOW chars of a higher-severity MNPI rule. The
# proximity check is char-based, matching the existing _line_context convention used for
# material_event. A bare "in discussions" or "please share" is noise; the same phrase
# adjacent to "Project Sapphire" or a definitive-agreement reference is the offence.
_CO_OCCURRENCE_AMPLIFIER_RULES = frozenset({
    "contingent_mnpi_language", "tipping_language", "selective_disclosure_risk",
    "insider_list_marker", "information_barrier_marker",
    "dpt_pre_listing_marker", "dpt_protocol_event_marker",
    "esg_climate_pre_disclosure", "esg_target_revision",
    "cyber_incident_pre_disclosure",
})
_CO_OCCURRENCE_TRIGGER_RULES = frozenset({
    "transaction_codename", "definitive_agreement", "material_adverse_change",
    "material_event", "embargo_marker", "nonpublic_marker",
})
_CO_OCCURRENCE_WINDOW = 200


def _amplify_co_occurring_low_mnpi(findings: list["ReviewFinding"]) -> None:
    """Lift `contingent_mnpi_language` / `tipping_language` from low → medium when within
    ±_CO_OCCURRENCE_WINDOW chars of a trigger MNPI rule. Mutates findings in place."""
    trigger_spans = [
        (f.start_char, f.end_char)
        for f in findings
        if f.rule in _CO_OCCURRENCE_TRIGGER_RULES
    ]
    if not trigger_spans:
        return
    for f in findings:
        if f.rule not in _CO_OCCURRENCE_AMPLIFIER_RULES or f.severity != "low":
            continue
        # window: any overlap between [f.start-W, f.end+W] and [lo, hi]
        f_lo = max(0, f.start_char - _CO_OCCURRENCE_WINDOW)
        f_hi = f.end_char + _CO_OCCURRENCE_WINDOW
        for lo, hi in trigger_spans:
            if f_lo <= hi and lo <= f_hi:
                f.severity = "medium"
                f.score = SEVERITY_SCORE["medium"]
                f.reason = (
                    f.reason + " — escalated due to adjacent MNPI substrate within ±200 chars"
                )
                break


# item 99: pseudonymised-but-linkable identifier rules. Escalate medium → high when a
# named_person finding co-occurs anywhere in the same document. The linking-key risk that
# makes GDPR Recital 26 / PDPC Anonymisation Advisory treat these as personal data is
# document-scoped, not span-local — once a named person + an internal ID both appear in
# the same doc, the re-link is trivial.
_PSEUDONYMISED_LINKABLE_RULES = frozenset({
    "employee_id", "customer_account_number", "medical_record_number",
})


# items 109/110/111: PII-handling-event rules that require a lookback-25 negation guard.
# These describe data flows / retention triggers / over-collection language; "no cross-border
# transfer is contemplated", "consent has not been withdrawn", "we are not over-collecting"
# should not fire. Parallel to the MNPI-side `_negation_guarded` set in `_mnpi_findings`.
_PII_NEGATION_GUARDED = frozenset({
    "cross_border_transfer_marker",
    "consent_withdrawal_marker",
    "data_minimisation_marker",
})


# item 101: quasi-identifier combination seed. PDPA s2 ("identified from that data and
# other information"), GDPR Recital 26 ("means reasonably likely to be used"), and CCPA
# §1798.140(v) ("reasonably capable of being associated") all extend personal data to
# combinations of attributes that re-identify when joined. Single named_person + phone is
# noise; named_person + NRIC + phone + email + address in the same paragraph is a
# re-identification dossier. The seed rule fires when ≥3 distinct quasi-identifier rules
# co-occur within a 500-char sliding window. Activated under audit_grade only — the v1
# rule is deliberately conservative recall-wise; item 70 v2 owns the full k-anonymity
# probability estimate.
_QUASI_IDENTIFIER_RULES = frozenset({
    # named-person + direct contact
    "named_person", "email_address", "phone_number", "bank_account",
    # postal-address signals
    "sg_postal_address", "jp_postal_code", "au_postal_address",
    # SG / SEA / HK / AU / JP / KR / US / UK local government / company IDs
    "sg_nric_fin", "sg_uen", "passport_number",
    "my_mykad", "id_nik", "th_national_id", "ph_philsys", "ph_tin", "vn_cccd",
    "hk_hkid", "hk_cr_no", "au_tfn", "au_abn", "au_acn",
    "jp_my_number", "jp_corporate_number", "kr_rrn", "kr_business_registration",
    "us_ssn", "us_ein", "uk_nin",
    # pseudonymised-but-linkable (item 99)
    "employee_id", "customer_account_number", "medical_record_number",
})
_QUASI_IDENTIFIER_WINDOW = 500
_QUASI_IDENTIFIER_MIN_DISTINCT = 3


def _detect_quasi_identifier_combinations(
    findings: list["ReviewFinding"],
    *,
    review_profile: str,
    jurisdiction: str,
    legal_basis: str,
    idx_start: int,
) -> list["ReviewFinding"]:
    """Greedy left-to-right sliding window over quasi-identifier findings sorted by
    start_char. Emits at most one combination finding per cluster — once a window with
    ≥3 distinct rules is emitted, the left pointer advances past the cluster to avoid
    overlapping emissions. audit_grade only; strict stays span-local."""
    if review_profile != "audit_grade":
        return []
    quasi = sorted(
        [f for f in findings if f.rule in _QUASI_IDENTIFIER_RULES],
        key=lambda f: f.start_char,
    )
    if len(quasi) < _QUASI_IDENTIFIER_MIN_DISTINCT:
        return []

    out: list["ReviewFinding"] = []
    idx = idx_start
    left = 0
    while left < len(quasi):
        right = left
        while (
            right + 1 < len(quasi)
            and quasi[right + 1].start_char - quasi[left].start_char <= _QUASI_IDENTIFIER_WINDOW
        ):
            right += 1
        distinct_rules = {quasi[k].rule for k in range(left, right + 1)}
        if len(distinct_rules) >= _QUASI_IDENTIFIER_MIN_DISTINCT:
            window_start = quasi[left].start_char
            window_end = max(quasi[k].end_char for k in range(left, right + 1))
            out.append(
                _new_finding(
                    idx=idx,
                    category="PII",
                    rule="quasi_identifier_combination",
                    jurisdiction=jurisdiction,
                    severity="medium",
                    matched_text=(
                        f"{len(distinct_rules)} distinct quasi-identifiers "
                        f"within {window_end - window_start} chars"
                    ),
                    start=window_start,
                    end=window_end,
                    reason=(
                        f"{len(distinct_rules)} distinct quasi-identifier rules co-occur "
                        f"within a {_QUASI_IDENTIFIER_WINDOW}-char window — combination "
                        f"is personal data under PDPA s2 / GDPR Recital 26"
                    ),
                    legal_basis=legal_basis,
                )
            )
            idx += 1
            left = right + 1  # advance past this cluster
        else:
            left += 1
    return out


def _amplify_pseudonymised_when_linked(findings: list["ReviewFinding"]) -> None:
    """Lift pseudonymised-but-linkable PII findings from medium → high when a named_person
    finding appears anywhere in the same document. Mutates findings in place."""
    has_named_person = any(f.rule == "named_person" for f in findings)
    if not has_named_person:
        return
    for f in findings:
        if f.rule not in _PSEUDONYMISED_LINKABLE_RULES or f.severity != "medium":
            continue
        f.severity = "high"
        f.score = SEVERITY_SCORE["high"]
        f.reason = f.reason + " — escalated due to named_person re-link risk (GDPR Recital 26)"


# item 73: entity-size-relative materiality (SAB 99 + ASX GN8).
#
# SEC Staff Accounting Bulletin No. 99 (1999) accepts 5% as a "preliminary assumption / initial
# step" against revenue or total assets but mandates qualitative overlay. ASX Guidance Note 8
# publishes numeric earnings-variance bands: ≥10% material (presume disclose); ≤5% non-material;
# 5–10% grey zone; ASX 300 issuers apply 5% not 10%; non-guiding ≥15% surprise floor.
#
# ESMA / BaFin / SGX MB 703 / HKEX MB 13.09 / UK MAR Art 7 explicitly refuse a generic
# numeric trigger — kaypoh surfaces the percentage as advisory only for those jurisdictions
# rather than coding a numeric verdict that contradicts regulator posture.
#
# Fail-loud when no entity_size_lookup is configured: emit a degraded_modes entry and leave
# financial_amount/financial_percentage findings at their default severity. Silent 1% default
# would systematically mis-tier small-cap docs.
#
# Sources:
#  - https://www.sec.gov/interps/account/sab99.htm
#  - https://www.asx.com.au/documents/about/guidance-note-8-clean-copy.pdf
#  - https://www.bafin.de/EN/Aufsicht/BoersenMaerkte/Emittentenleitfaden/Modul3/Kapitel1/...
#  - https://rulebook.sgx.com/rulebook/703-0
#  - https://en-rules.hkex.com.hk/rulebook/1309-0

# Per-jurisdiction tier ladders. Threshold = fraction-of-base (revenue or market_cap). Tier
# at or above threshold yields the named severity. Walk from highest tier downward; first
# threshold met wins. Existing SEVERITY_SCORE only defines low/medium/high — we collapse the
# would-be "critical" top into "high" rather than expand the global severity vocabulary.
_MATERIALITY_TIERS_US: tuple[tuple[float, str], ...] = (
    (0.05, "high"),      # SAB 99 "5% rule of thumb"
    (0.01, "medium"),    # below 5% but non-trivial
)
_MATERIALITY_TIERS_AU_GENERAL: tuple[tuple[float, str], ...] = (
    (0.10, "high"),      # ASX GN8 ≥10% disclose presumption
    (0.05, "medium"),    # ASX GN8 5-10% grey zone
)
_MATERIALITY_TIERS_AU_ASX300: tuple[tuple[float, str], ...] = (
    (0.05, "high"),       # halved per ASX GN8 ASX-300 guidance
    (0.025, "medium"),
)
# Jurisdictions whose regulators explicitly refuse a numeric threshold. We surface percentage
# vs base as advisory reason but never mutate severity. Reviewer judgement closes the loop.
_MATERIALITY_ADVISORY_ONLY: frozenset[str] = frozenset({"SG", "HK", "UK", "EU", "MY", "ID", "TH", "PH", "VN", "JP", "KR"})

_MATERIALITY_SCALED_RULES: frozenset[str] = frozenset({"financial_amount", "financial_percentage"})


class EntitySizeLookup:
    """Protocol for entity revenue / market-cap lookups (item 73).

    Returns a dict with at least one of `revenue` or `market_cap` in the entity's reporting
    currency. Subclasses may attach `is_asx_300: bool` for AU jurisdiction halving. Implementers
    are responsible for currency normalisation against the matched value's currency — the engine
    treats `revenue`/`market_cap` as already in the same denomination as the finding text.

    Engine never instantiates a default lookup. Without one, financial_amount and
    financial_percentage findings keep their default severity and the engine emits a
    `materiality_lookup_not_configured` degraded mode rather than guess."""

    def lookup(self, entity_id: str, jurisdiction: str) -> dict[str, Any] | None:
        raise NotImplementedError


# Parses an MNPI financial_amount matched_text into a numeric base value in millions. Returns
# None when the unit suffix is missing — `$5,000,000` parses; `$5,000,000.00` parses; bare
# `$5` does not get scaled (too noisy without a unit). Conservative: prefer not to scale than
# to scale wrongly.
_AMOUNT_UNIT_RE = re.compile(
    r"(?P<num>\d(?:[\d,]*\d)?(?:\.\d+)?)\s*(?P<unit>thousand|million|billion|trillion|[KMBT])?",
    re.IGNORECASE,
)
_UNIT_MULTIPLIER: dict[str, float] = {
    "": 1.0, "K": 1e3, "THOUSAND": 1e3,
    "M": 1e6, "MILLION": 1e6,
    "B": 1e9, "BILLION": 1e9,
    "T": 1e12, "TRILLION": 1e12,
}


def _parse_financial_amount(matched_text: str) -> float | None:
    """Return the matched amount as a raw numeric value, or None when unparseable. Currency
    symbols are ignored — entity-size comparison is denomination-agnostic at this layer; the
    EntitySizeLookup caller is responsible for currency-normalising its revenue / market_cap
    values to the same denomination as the source document."""
    m = _AMOUNT_UNIT_RE.search(matched_text)
    if not m:
        return None
    num_str = m.group("num").replace(",", "")
    try:
        num = float(num_str)
    except ValueError:
        return None
    unit_key = (m.group("unit") or "").upper()
    multiplier = _UNIT_MULTIPLIER.get(unit_key, 1.0)
    return num * multiplier


def _parse_financial_percentage(matched_text: str) -> float | None:
    """Return percentage as a fraction (5% → 0.05). None when unparseable."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", matched_text)
    if not m:
        return None
    try:
        return float(m.group(1)) / 100.0
    except ValueError:
        return None


def _resolve_tiers(jurisdiction: str, entity_info: dict[str, Any] | None) -> tuple[tuple[float, str], ...] | None:
    """Return the tier ladder for the given jurisdiction. None for advisory-only jurisdictions
    (engine surfaces percentage as reason suffix but does not mutate severity)."""
    juris_codes = jurisdiction.split("+")
    if any(code == "AU" for code in juris_codes):
        if entity_info and entity_info.get("is_asx_300"):
            return _MATERIALITY_TIERS_AU_ASX300
        return _MATERIALITY_TIERS_AU_GENERAL
    if any(code == "US" for code in juris_codes):
        return _MATERIALITY_TIERS_US
    if any(code in _MATERIALITY_ADVISORY_ONLY for code in juris_codes):
        return None
    # Unknown / synthesised baseline pack: default to US ladder (SAB 99 is the most-cited).
    return _MATERIALITY_TIERS_US


def _tier_for(fraction: float, ladder: tuple[tuple[float, str], ...]) -> str | None:
    for threshold, severity in ladder:
        if fraction >= threshold:
            return severity
    return None


def _scale_financial_by_entity_size(
    findings: list["ReviewFinding"],
    *,
    jurisdiction: str,
    entity_id: str | None,
    entity_size_lookup: "EntitySizeLookup | None",
) -> list[dict[str, Any]]:
    """Mutate financial_amount / financial_percentage finding severities per item 73 ladder.
    Returns a list of degraded_modes entries when the lookup is unavailable or returns
    insufficient data. Fails loud — no silent default."""
    affected = [f for f in findings if f.rule in _MATERIALITY_SCALED_RULES]
    if not affected:
        return []
    if entity_size_lookup is None or not entity_id:
        return [
            {
                "mode": "materiality_lookup_not_configured",
                "status": "skipped",
                "reason": (
                    "no entity_size_lookup configured or entity_id not provided; "
                    "financial_amount / financial_percentage findings kept at default "
                    "severity. SAB 99 5% / ASX GN8 entity-relative scaling unavailable."
                ),
                "detail": {"affected_finding_count": len(affected)},
            }
        ]
    try:
        entity_info = entity_size_lookup.lookup(entity_id, jurisdiction)
    except Exception as exc:  # entity-source providers are external — fail loud, not closed
        return [
            {
                "mode": "materiality_lookup_failed",
                "status": "failed_closed",
                "reason": f"entity size lookup raised: {exc}",
                "detail": {"entity_id": entity_id, "jurisdiction": jurisdiction},
            }
        ]
    if not entity_info:
        return [
            {
                "mode": "materiality_lookup_missing_entity",
                "status": "skipped",
                "reason": (
                    f"entity_size_lookup returned no record for {entity_id!r} under "
                    f"jurisdiction {jurisdiction}; financial findings kept at default severity"
                ),
                "detail": {"entity_id": entity_id, "jurisdiction": jurisdiction},
            }
        ]
    ladder = _resolve_tiers(jurisdiction, entity_info)
    # Choose the larger of (revenue, market_cap) as the base — SAB 99 doesn't mandate which.
    # Larger base yields a lower fraction → softer tier. Conservative for over-firing.
    base = max(
        float(entity_info.get("revenue") or 0.0),
        float(entity_info.get("market_cap") or 0.0),
    )
    if base <= 0:
        return [
            {
                "mode": "materiality_lookup_invalid_base",
                "status": "skipped",
                "reason": "entity_size_lookup returned non-positive revenue and market_cap",
                "detail": {"entity_id": entity_id, "jurisdiction": jurisdiction},
            }
        ]
    for f in affected:
        if f.rule == "financial_amount":
            value = _parse_financial_amount(f.matched_text)
            if value is None:
                continue
            fraction = value / base
        else:  # financial_percentage — direct fraction; entity base used for context only
            fraction = _parse_financial_percentage(f.matched_text)
            if fraction is None:
                continue
        if ladder is None:
            # Advisory-only jurisdiction (MAR / SGX / HKEX): annotate reason, leave severity.
            f.reason = (
                f.reason
                + f" — entity-relative {fraction:.2%} (regulator declines numeric materiality threshold; review required)"
            )
            continue
        new_tier = _tier_for(fraction, ladder)
        if new_tier is None or SEVERITY_SCORE[new_tier] <= SEVERITY_SCORE[f.severity]:
            # Tier ladder did not exceed the deterministic floor. Leave severity intact.
            f.reason = f.reason + f" — entity-relative {fraction:.2%} (below scaling tier)"
            continue
        f.severity = new_tier
        f.score = SEVERITY_SCORE[new_tier]
        f.reason = (
            f.reason
            + f" — escalated to {new_tier} per SAB 99 / ASX GN8 entity-relative tier "
            f"({fraction:.2%} of base)"
        )
    return []


# item 84: blackout-window calendrical detector.
#
# Most listed-company regimes have a closed period before results announcements. Today's
# `embargo_marker` catches explicit "embargoed" / "press hold" strings but no calendrical
# reasoning. This pass fires `blackout_period_reference` when a document references both
# (a) its own date and (b) a results / earnings announcement date such that today falls
# within the jurisdiction's blackout window.
#
# Jurisdiction registry (verified 2026-05-27):
#  - SGX Mainboard Rule 1207(19)(c): 2 weeks before Q1-Q3; 1 month before half / full-year.
#    https://rulebook.sgx.com/rulebook/1207
#  - HKEX MB Appendix C3 (formerly Appendix 10 Model Code, renumbered Update 91):
#    30 days before interim / quarterly; 60 days before annual results.
#    https://en-rules.hkex.com.hk/rulebook/model-code-securities-transactions-directors-listed-issuers-1
#  - UK MAR Art 19(11) + UKLR (formerly LR 9.2.6): 30 calendar days closed period for PDMRs
#    before interim and year-end financial reports.
#    https://handbook.fca.org.uk/handbook?entityId=uklr
#  - US Reg FD: no codified duration. Firm-policy 2–4 weeks; advisory only here.
#    https://icrinc.com/news-resources/quiet-period-questions-answered-for-public-companies/
#  - ASX: no exchange-mandated duration (LR 12.9 + GN 27 require an issuer trading policy
#    but do not set a length). Advisory only.
#
# v1 ships per-juris explicit-date detection only. ticker → next-earnings-date lookup is
# deferred to v2 (audit_grade; depends on item 73 entity_size_lookup substrate + EDGAR
# connector — earnings dates without a paid feed are estimates, not ground truth).

_BLACKOUT_WINDOW_DAYS: dict[str, dict[str, int]] = {
    "SG": {"interim": 14, "annual": 30},   # SGX MB 1207(19)(c)
    "HK": {"interim": 30, "annual": 60},   # HKEX MB App C3
    "UK": {"interim": 30, "annual": 30},   # UK MAR Art 19(11) + UKLR
    "EU": {"interim": 30, "annual": 30},   # EU MAR Art 19(11) (parallel to UK MAR)
}

# Earnings-date anchors. Each carries a period_type label so the engine selects the right
# window. Order matters — more specific patterns first to avoid mis-classifying "annual" as
# "interim".
_EARNINGS_DATE_ANCHORS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(
        r"\b(?:full[ -]year|annual|FY|year[ -]end)\s+results?\s+(?:announcement\s+)?"
        r"(?:to\s+be\s+(?:released|announced|published)\s+on|scheduled\s+for|"
        r"on|due|expected\s+on|set\s+for)\s+"
        r"([\w,/\- ]{6,40}?)(?=[.\n,;]|\Z)",
        re.IGNORECASE,
    ), "annual"),
    (re.compile(
        r"\b(?:interim|half[ -]year|H[12]|Q[1-4]|quarterly)\s+results?\s+"
        r"(?:announcement\s+)?(?:to\s+be\s+(?:released|announced|published)\s+on|"
        r"scheduled\s+for|on|due|expected\s+on|set\s+for)\s+"
        r"([\w,/\- ]{6,40}?)(?=[.\n,;]|\Z)",
        re.IGNORECASE,
    ), "interim"),
    (re.compile(
        # Generic "earnings on" / "results on" without period qualifier — default to interim
        # (the shorter window is more conservative; reviewer can override).
        r"\b(?:earnings|results)\s+(?:announcement\s+)?"
        r"(?:to\s+be\s+(?:released|announced|published)\s+on|scheduled\s+for|"
        r"on|due|expected\s+on|set\s+for)\s+"
        r"([\w,/\- ]{6,40}?)(?=[.\n,;]|\Z)",
        re.IGNORECASE,
    ), "interim"),
)

# Document date anchors. First match wins. Several common memo / email / contract headers.
_DOC_DATE_ANCHORS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bDate\s*[:\-]\s*([\w,/\- ]{6,30})", re.IGNORECASE),
    re.compile(r"\bToday(?:'s\s+date)?\s+is\s+([\w,/\- ]{6,30})", re.IGNORECASE),
    re.compile(r"\bMemo\s+date\s*[:\-]\s*([\w,/\- ]{6,30})", re.IGNORECASE),
    re.compile(r"\bDated\s+(?:as\s+of\s+)?([\w,/\- ]{6,30})", re.IGNORECASE),
)

# Date parsing covering the SG/UK/EU/HK conventions reviewers actually use.
_MONTH_NAMES: dict[str, int] = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_DATE_ISO_RE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_DATE_DMY_NAME_RE = re.compile(
    r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b"
)
_DATE_MDY_NAME_RE = re.compile(
    r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})\b"
)
_DATE_DMY_SLASH_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def _parse_date(text: str) -> tuple[int, int, int] | None:
    """Return (year, month, day) for the first recognised date in `text`. Tries ISO,
    DMY-name, MDY-name, and DMY-slash forms. Returns None when none match. DMY-slash
    is the SG/UK/EU convention — US MDY-slash ambiguity is left to the reviewer.

    Implemented with stdlib only to keep `kaypoh-local` torch-ban discipline intact.
    """
    import datetime as _dt
    text = text.strip()
    m = _DATE_ISO_RE.search(text)
    if m:
        try:
            _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return int(m.group(1)), int(m.group(2)), int(m.group(3))
        except ValueError:
            pass
    m = _DATE_DMY_NAME_RE.search(text)
    if m:
        month = _MONTH_NAMES.get(m.group(2).lower())
        if month:
            try:
                _dt.date(int(m.group(3)), month, int(m.group(1)))
                return int(m.group(3)), month, int(m.group(1))
            except ValueError:
                pass
    m = _DATE_MDY_NAME_RE.search(text)
    if m:
        month = _MONTH_NAMES.get(m.group(1).lower())
        if month:
            try:
                _dt.date(int(m.group(3)), month, int(m.group(2)))
                return int(m.group(3)), month, int(m.group(2))
            except ValueError:
                pass
    m = _DATE_DMY_SLASH_RE.search(text)
    if m:
        try:
            _dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            return int(m.group(3)), int(m.group(2)), int(m.group(1))
        except ValueError:
            pass
    return None


def _detect_blackout_period_references(
    text: str,
    *,
    packs: list[JurisdictionRulePack],
    jurisdiction: str,
    legal_basis: str,
    idx_start: int,
) -> list["ReviewFinding"]:
    """Fire `blackout_period_reference` when document date + earnings date co-occur within
    the per-jurisdiction blackout window. Only fires when at least one applicable juris is
    in `_BLACKOUT_WINDOW_DAYS`. Severity medium standalone."""
    applicable_juris = [pack.code for pack in packs if pack.code in _BLACKOUT_WINDOW_DAYS]
    if not applicable_juris:
        return []

    doc_date: tuple[int, int, int] | None = None
    for anchor in _DOC_DATE_ANCHORS:
        m = anchor.search(text)
        if m:
            doc_date = _parse_date(m.group(1))
            if doc_date:
                break
    if doc_date is None:
        return []

    import datetime as _dt
    doc_d = _dt.date(*doc_date)

    out: list["ReviewFinding"] = []
    idx = idx_start
    # Dedup by parsed earnings date — both the specific anchor (annual / interim with
    # period qualifier) and the generic anchor can match the same date phrase; the more
    # specific match wins via iteration order.
    seen_earnings: set[tuple[int, int, int]] = set()
    for pattern, period in _EARNINGS_DATE_ANCHORS:
        for m in pattern.finditer(text):
            earnings_date = _parse_date(m.group(1))
            if not earnings_date:
                continue
            if earnings_date in seen_earnings:
                continue
            seen_earnings.add(earnings_date)
            ed = _dt.date(*earnings_date)
            delta = (ed - doc_d).days
            if delta < 0:
                continue
            # Pick the strictest applicable jurisdiction (longest window).
            applicable_window = max(
                _BLACKOUT_WINDOW_DAYS[code][period] for code in applicable_juris
            )
            if delta > applicable_window:
                continue
            window_owner = max(
                applicable_juris,
                key=lambda code: _BLACKOUT_WINDOW_DAYS[code][period],
            )
            out.append(
                _new_finding(
                    idx=idx,
                    category="MNPI",
                    rule="blackout_period_reference",
                    jurisdiction=jurisdiction,
                    severity="medium",
                    matched_text=m.group(),
                    start=m.start(),
                    end=m.end(),
                    reason=(
                        f"Document dated {doc_d.isoformat()}; {period} results "
                        f"announcement on {ed.isoformat()} is within {window_owner} "
                        f"{applicable_window}-day blackout window (delta={delta} days)"
                    ),
                    legal_basis=legal_basis,
                )
            )
            idx += 1
    return out


def _suppress_redundant_phone_findings(findings: list["ReviewFinding"]) -> list["ReviewFinding"]:
    """Drop phone_number findings whose [start, end) is fully covered by a higher-priority
    identifier finding (NRIC, UEN, MyKad, NIK, CCCD, passport, bank account).

    Conservative: only suppresses when the higher-priority span fully *contains* the phone
    span. A partially-overlapping phone match keeps firing so we don't accidentally lose
    real phones that touch other entities."""
    spans_to_beat: list[tuple[int, int]] = [
        (f.start_char, f.end_char)
        for f in findings
        if f.rule in _HIGHER_PRIORITY_THAN_PHONE
    ]
    if not spans_to_beat:
        return findings
    kept: list["ReviewFinding"] = []
    for f in findings:
        if f.rule == "phone_number" and any(
            lo <= f.start_char and f.end_char <= hi
            for lo, hi in spans_to_beat
        ):
            continue
        kept.append(f)
    return kept


def _pack_scope(packs: list[JurisdictionRulePack]) -> str:
    return "+".join(pack.code for pack in packs)


def _legal_basis(packs: list[JurisdictionRulePack], field_name: str) -> str:
    rules: list[str] = []
    seen: set[str] = set()
    for pack in packs:
        for rule in getattr(pack, field_name):
            if rule not in seen:
                rules.append(rule)
                seen.add(rule)
    return ", ".join(rules)


class PreSendReviewEngine:
    def __init__(
        self,
        *,
        public_evidence_retriever: Any | None = None,
        llm_adjudicator: Any | None = None,
        llm_defined_term_extractor: Any | None = None,
        llm_coverage_auditor: Any | None = None,
        entity_size_lookup: EntitySizeLookup | None = None,
    ):
        self.public_evidence_retriever = public_evidence_retriever
        self.llm_adjudicator = llm_adjudicator
        # audit_grade-only LLM helper that catches preamble defined-term patterns the
        # deterministic regex misses (`hereinafter referred to as "X"`, etc.). cached by
        # document hash so paired-doc workflows don't re-pay the LLM cost.
        self.llm_defined_term_extractor = llm_defined_term_extractor
        # audit_grade-only inverse audit. given the deterministic findings + a doc hash,
        # advises on patterns that may have been missed. output is journaled as
        # `coverage_warning` events and surfaced on ReviewResult; advisory only — never
        # mutates findings, scores, or classification.
        self.llm_coverage_auditor = llm_coverage_auditor
        # item 73: entity revenue / market-cap source. Engine never instantiates a default —
        # without one, financial_amount / financial_percentage findings keep their default
        # severity and the engine emits a materiality_lookup_not_configured degraded mode.
        self.entity_size_lookup = entity_size_lookup

    def _pii_findings(
        self,
        text: str,
        packs: list[JurisdictionRulePack],
        document_type: str = "generic",
        defined_terms: set[str] | None = None,
    ) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        jurisdiction = _pack_scope(packs)
        legal_basis = _legal_basis(packs, "pii_rules")
        defined = defined_terms or set()
        patterns = []
        if any(pack.code == "SG" for pack in packs):
            patterns.extend(
                [
                    ("sg_nric_fin", SG_NRIC_RE, "high", "Singapore NRIC/FIN-like identifier"),
                    ("sg_uen", SG_UEN_RE, "high", "Singapore ACRA UEN identifier"),
                    ("sg_postal_address", SG_POSTAL_RE, "medium", "Singapore postal-code address signal"),
                ]
            )
        patterns.extend(
            [
                ("email_address", EMAIL_RE, "medium", "Email address can identify an individual"),
                ("phone_number", PHONE_RE, "medium", "Phone number can identify or contact an individual"),
                ("passport_number", PASSPORT_RE, "high", "Passport-like identifier"),
                ("bank_account", BANK_ACCOUNT_RE, "high", "Bank/account-like financial identifier"),
                # item 99: pseudonymised-but-linkable identifiers. medium standalone; amplified
                # to high when a named_person finding co-occurs anywhere in the document.
                ("employee_id", EMPLOYEE_ID_RE, "medium",
                 "Employee identifier — pseudonymised-but-linkable personal data"),
                ("customer_account_number", CUSTOMER_ACCOUNT_RE, "medium",
                 "Customer account / member identifier — pseudonymised-but-linkable personal data"),
                ("medical_record_number", MEDICAL_RECORD_RE, "high",
                 "Medical record / patient identifier — special-category personal data"),
                # items 109/110/111: PII-handling-event markers. medium standalone; negation
                # guard via `_PII_NEGATION_GUARDED` lookback-25.
                ("cross_border_transfer_marker", CROSS_BORDER_TRANSFER_RE, "medium",
                 "Cross-border personal-data transfer marker"),
                ("consent_withdrawal_marker", CONSENT_WITHDRAWAL_RE, "medium",
                 "Consent-withdrawal / data-subject-rights marker"),
                ("data_minimisation_marker", DATA_MINIMISATION_RE, "medium",
                 "Data-minimisation / over-collection marker"),
            ]
        )

        idx = 0
        for rule, pattern, severity, reason in patterns:
            for match in pattern.finditer(text):
                start, end = match.span(1) if match.lastindex else match.span()
                if end <= start:
                    continue
                if rule in _PII_NEGATION_GUARDED and _is_negated_context(text, start):
                    continue
                findings.append(
                    _new_finding(
                        idx=idx,
                        category="PII",
                        rule=rule,
                        jurisdiction=jurisdiction,
                        severity=severity,
                        matched_text=text[start:end],
                        start=start,
                        end=end,
                        reason=reason,
                        legal_basis=legal_basis,
                    )
                )
                idx += 1

        # TOML-driven recognizers from each pack. fires per-pack rather than per-jurisdiction
        # query because a SG+MY query should run BOTH MyKad and NRIC detectors. dedup-on-span
        # below prevents the same matched bytes being double-counted when packs overlap (e.g.,
        # a customer pack defining its own `email_address` recognizer).
        seen_spans: set[tuple[str, int, int]] = {
            (f.rule, f.start_char, f.end_char) for f in findings
        }
        for pack in packs:
            for recognizer in pack.recognizers:
                for match in recognizer.pattern.finditer(text):
                    cg = recognizer.capture_group
                    if cg and match.lastindex and cg <= match.lastindex:
                        start, end = match.span(cg)
                    else:
                        start, end = match.span()
                    if end <= start:
                        continue
                    if not recognizer.is_valid(text[start:end]):
                        continue
                    span_key = (recognizer.rule_name, start, end)
                    if span_key in seen_spans:
                        continue
                    seen_spans.add(span_key)
                    findings.append(
                        _new_finding(
                            idx=idx,
                            category="PII",
                            rule=recognizer.rule_name,
                            jurisdiction=jurisdiction,
                            severity=recognizer.severity,
                            matched_text=text[start:end],
                            start=start,
                            end=end,
                            reason=recognizer.reason,
                            legal_basis=legal_basis,
                        )
                    )
                    idx += 1

        # named_person uses a two-pass anchor + variant linker so `Dr Jane Tan` and a later bare
        # `Jane Tan` collapse to the same anonymisation key. defined terms are suppressed.
        findings.extend(
            self._named_person_findings(
                text=text,
                jurisdiction=jurisdiction,
                legal_basis=legal_basis,
                defined_terms=defined,
                document_type=document_type,
                idx_start=idx,
            )
        )

        # cross-rule span-dedup post-pass. PHONE_RE is intentionally loose so any number-like
        # span (NRIC, UEN, MyKad, NIK, CCCD, etc.) also matches it. We could tighten PHONE_RE
        # but that risks losing real phones; instead, drop phone_number findings whose span is
        # *fully contained* within a higher-priority national-/company-ID span. The
        # higher-priority finding stays; the duplicate phone finding gets suppressed.
        findings = _suppress_redundant_phone_findings(findings)

        # item 99: pseudonymised-but-linkable IDs escalate medium → high when a named_person
        # co-occurs in the same document. The named_person pass above must have run first.
        _amplify_pseudonymised_when_linked(findings)

        return findings

    def _named_person_findings(
        self,
        *,
        text: str,
        jurisdiction: str,
        legal_basis: str,
        defined_terms: set[str],
        document_type: str,
        idx_start: int,
    ) -> list[ReviewFinding]:
        severity = (
            "high" if document_type.strip().lower() in NAMED_PERSON_HIGH_SEVERITY_DOC_TYPES else "low"
        )
        findings: list[ReviewFinding] = []
        occupied: list[tuple[int, int]] = []
        anchors: dict[str, str] = {}  # canonical key -> honorific-stripped surface form
        idx = idx_start

        # pass 1: honorific-led names anchor the canonical set
        for match in NAME_RE.finditer(text):
            start, end = match.span()
            matched_text = text[start:end]
            if is_defined_term(matched_text, defined_terms):
                continue
            findings.append(
                _new_finding(
                    idx=idx,
                    category="PII",
                    rule="named_person",
                    jurisdiction=jurisdiction,
                    severity=severity,
                    matched_text=matched_text,
                    start=start,
                    end=end,
                    reason="Named person reference",
                    legal_basis=legal_basis,
                )
            )
            occupied.append((start, end))
            idx += 1
            canonical = canonical_person(matched_text)
            stripped = strip_honorific(matched_text)
            if canonical and stripped and canonical != stripped.casefold():
                anchors.setdefault(canonical, stripped)
            elif canonical and stripped:
                anchors.setdefault(canonical, stripped)

        # pass 2: bare variants of an anchored name (e.g., later mentions without honorific).
        # full-name variants first, then surname-only variants. surname-only matching is
        # intentionally narrow: only the trailing token of an anchored honorific name fires, and
        # only when it appears as a stand-alone capitalised word. avoids false-positives on
        # common surname-shaped words appearing without an anchored reference in the same doc.
        for canonical, stripped in anchors.items():
            if len(stripped) < 3:
                continue
            variant_pattern = re.compile(rf"\b{re.escape(stripped)}\b")
            for match in variant_pattern.finditer(text):
                start, end = match.span()
                if any(start < oe and os_ < end for os_, oe in occupied):
                    continue
                matched_text = text[start:end]
                if is_defined_term(matched_text, defined_terms):
                    continue
                findings.append(
                    _new_finding(
                        idx=idx,
                        category="PII",
                        rule="named_person",
                        jurisdiction=jurisdiction,
                        severity=severity,
                        matched_text=matched_text,
                        start=start,
                        end=end,
                        reason="Named person variant linked to an anchored honorific reference",
                        legal_basis=legal_basis,
                    )
                )
                occupied.append((start, end))
                idx += 1

        # pass 3: surname-only fuzzy variants. only fires when a multi-token honorific anchor
        # exists ("Dr Jane Tan" → "Tan"), the surname token is title-cased and ≥2 chars, and the
        # surname is not also a defined term in the document. word boundaries (\b...\b) already
        # exclude mid-word matches like "Tannery" or "Tanner".
        # corporate suffixes that NAME_RE might have swallowed (e.g. "Mr Lee Ltd") would otherwise
        # bind "Ltd" as a surname and fire on every Ltd in the doc — denylist guards against that.
        seen_surnames: set[str] = set()
        for canonical, stripped in anchors.items():
            tokens = stripped.split()
            if len(tokens) < 2:
                continue
            surname = tokens[-1]
            if len(surname) < 2 or not surname[0].isupper():
                continue
            if surname.casefold() in _SURNAME_DENYLIST:
                continue
            if surname.casefold() in seen_surnames:
                continue
            if is_defined_term(surname, defined_terms):
                continue
            seen_surnames.add(surname.casefold())
            surname_pattern = re.compile(rf"\b{re.escape(surname)}\b")
            for match in surname_pattern.finditer(text):
                start, end = match.span()
                if any(start < oe and os_ < end for os_, oe in occupied):
                    continue
                matched_text = text[start:end]
                if is_defined_term(matched_text, defined_terms):
                    continue
                findings.append(
                    _new_finding(
                        idx=idx,
                        category="PII",
                        rule="named_person",
                        jurisdiction=jurisdiction,
                        severity=severity,
                        matched_text=matched_text,
                        start=start,
                        end=end,
                        reason="Surname-only reference linked to an anchored honorific name",
                        legal_basis=legal_basis,
                    )
                )
                occupied.append((start, end))
                idx += 1
        return findings

    def _mnpi_findings(
        self,
        text: str,
        packs: list[JurisdictionRulePack],
        defined_terms: set[str] | None = None,
        document_type: str = "generic",
    ) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        jurisdiction = _pack_scope(packs)
        legal_basis = _legal_basis(packs, "mnpi_rules")
        defined = defined_terms or set()
        doc_type_key = (document_type or "generic").strip().lower()
        idx = 0
        for match in MATERIAL_EVENT_RE.finditer(text):
            context = _line_context(text, match.start(), match.end())
            # item 36: phrasing alone ("publicly announced", "press release") no longer softens
            # severity. soften only when the same line carries a citable http(s) URL — the
            # document is self-citing. retrieval-driven softening is layered in by the post-pass
            # in review() once the public-evidence retriever has actually run.
            severity = "medium"
            reason = "Material corporate or market event language"
            source_verification = SOURCE_VERIFICATION_NOT_CHECKED
            if NONPUBLIC_RE.search(context):
                severity = "high"
                reason = "Material event appears tied to non-public or restricted context"
            elif PUBLIC_RE.search(context) and _INDOC_URL_RE.search(context):
                severity = "low"
                reason = "Material event paired with an in-document citable source reference"
                source_verification = SOURCE_VERIFICATION_PUBLIC_SOURCE_MATCHED

            findings.append(
                _new_finding(
                    idx=idx,
                    category="MNPI",
                    rule="material_event",
                    jurisdiction=jurisdiction,
                    severity=severity,
                    matched_text=context or match.group(),
                    start=max(0, text.rfind("\n", 0, match.start()) + 1),
                    end=(text.find("\n", match.end()) if text.find("\n", match.end()) >= 0 else len(text)),
                    reason=reason,
                    legal_basis=legal_basis,
                    source_verification=source_verification,
                )
            )
            idx += 1

        # rules where matching a contract's own defined term (e.g. "SPA" abbreviating itself)
        # would false-positive. blanket-suppressing every MNPI rule against defined terms is
        # too aggressive (e.g. "Project Atlas" as a defined transaction codename is still MNPI),
        # so we only suppress the abbreviation-style rules.
        suppressible_rules = {"definitive_agreement", "material_adverse_change"}
        for pattern, rule, severity, reason in [
            (NONPUBLIC_RE, "nonpublic_marker", "high", "Explicit non-public/confidentiality marker"),
            (TRANSACTION_CODENAME_RE, "transaction_codename", "high",
             "Internal deal codename detected; treat as MNPI until publicly disclosed"),
            (DEFINITIVE_AGREEMENT_RE, "definitive_agreement", "high",
             "Definitive-agreement reference may carry MNPI before announcement"),
            (MAC_CLAUSE_RE, "material_adverse_change", "high",
             "Material adverse change / effect language signals MNPI-grade context"),
            (EMBARGO_RE, "embargo_marker", "high",
             "Embargo / signing-date marker indicates MNPI handling"),
            (MONEY_RE, "financial_amount", "medium", "Specific financial amount may be material"),
            (PERCENT_RE, "financial_percentage", "medium", "Specific financial percentage may be material"),
            (LONG_NUMBER_RE, "large_number", "medium", "Large numeric value may be material"),
        ]:
            effective_severity = MNPI_DOC_TYPE_SEVERITY_OVERRIDES.get((rule, doc_type_key), severity)
            for match in pattern.finditer(text):
                if rule in suppressible_rules and is_defined_term(match.group(), defined):
                    continue
                # narrow negation guard for MAC/MAE-style rules. catches the most common
                # "no MAC clause concerns" / "not subject to MAC clause" patterns. doesn't
                # try to be a general NLP solver — that's the audit_grade LLM tier's job.
                if rule == "material_adverse_change" and _is_negated_context(text, match.start()):
                    continue
                findings.append(
                    _new_finding(
                        idx=idx,
                        category="MNPI",
                        rule=rule,
                        jurisdiction=jurisdiction,
                        severity=effective_severity,
                        matched_text=match.group(),
                        start=match.start(),
                        end=match.end(),
                        reason=reason,
                        legal_basis=legal_basis,
                    )
                )
                idx += 1

        # items 95 + 96 + 97: contingent + tipping + Reg FD selective-disclosure language.
        # All three ship at severity `low`; the post-pass amplifier in review() escalates to
        # `medium` when adjacent to a deal substrate. Negation guard reused for contingent.
        # selective_disclosure_risk only fires when destination/source jurisdiction includes US
        # (Reg FD is US-specific — 17 CFR 243.100). The juris-gate is checked outside the loop.
        is_us_scope = any(pack.code == "US" for pack in packs)
        post_pass_rules: list[tuple[Any, str, str]] = [
            (CONTINGENT_MNPI_RE, "contingent_mnpi_language",
             "Contingent / forward-looking language; amplifies when adjacent to deal substrate"),
            (TIPPING_RE, "tipping_language",
             "Forwarding / distribution language; amplifies when adjacent to MNPI substrate"),
            (INSIDER_LIST_RE, "insider_list_marker",
             "Insider-list / wall-cross marker; amplifies when adjacent to MNPI substrate"),
            (INFORMATION_BARRIER_RE, "information_barrier_marker",
             "Information-barrier marker; amplifies when adjacent to MNPI substrate"),
            (DPT_PRE_LISTING_RE, "dpt_pre_listing_marker",
             "Digital-asset pre-listing / enforcement marker; amplifies when adjacent to MNPI substrate"),
            (DPT_PROTOCOL_EVENT_RE, "dpt_protocol_event_marker",
             "Digital-asset protocol-event marker; amplifies when adjacent to MNPI substrate"),
            (ESG_CLIMATE_PRE_DISCLOSURE_RE, "esg_climate_pre_disclosure",
             "ESG / climate pre-disclosure marker; amplifies when adjacent to MNPI substrate"),
            (ESG_TARGET_REVISION_RE, "esg_target_revision",
             "ESG target revision / assurance opinion; amplifies when adjacent to MNPI substrate"),
            (CYBER_INCIDENT_RE, "cyber_incident_pre_disclosure",
             "Cyber-incident pre-disclosure marker; amplifies when adjacent to MNPI substrate"),
        ]
        if is_us_scope:
            post_pass_rules.append(
                (SELECTIVE_DISCLOSURE_RE, "selective_disclosure_risk",
                 "Selective-disclosure language (Reg FD); amplifies when adjacent to MNPI substrate")
            )
        # rules where lookback-window negation should suppress firing.
        _negation_guarded = {
            "contingent_mnpi_language", "insider_list_marker", "information_barrier_marker",
            "dpt_pre_listing_marker", "dpt_protocol_event_marker",
            "esg_climate_pre_disclosure", "esg_target_revision",
            "cyber_incident_pre_disclosure",
        }
        for pattern, rule, reason in post_pass_rules:
            for match in pattern.finditer(text):
                if rule in _negation_guarded and _is_negated_context(text, match.start()):
                    continue
                findings.append(
                    _new_finding(
                        idx=idx,
                        category="MNPI",
                        rule=rule,
                        jurisdiction=jurisdiction,
                        severity="low",
                        matched_text=match.group(),
                        start=match.start(),
                        end=match.end(),
                        reason=reason,
                        legal_basis=legal_basis,
                    )
                )
                idx += 1
        return findings

    def _score(self, findings: list[ReviewFinding], category: str) -> float:
        matches = [finding.score for finding in findings if finding.category == category]
        if not matches:
            return 0.0
        return min(100.0, max(matches) + max(0, len(matches) - 1) * 3.0)

    def _suggestions(
        self,
        findings: list[ReviewFinding],
        include_suggestions: bool,
        *,
        tenant_id: str | None = None,
    ) -> list[ReviewSuggestion]:
        if not include_suggestions:
            return []

        suggestions: list[ReviewSuggestion] = []
        for index, finding in enumerate(findings):
            if finding.category == "PII":
                action = "redact"
                replacement = "[REDACTED PERSONAL DATA]"
                rationale = pii_rationale(
                    rule=finding.rule,
                    jurisdiction=finding.jurisdiction,
                    matched_text=finding.matched_text,
                    tenant_id=tenant_id,
                )
            elif finding.severity == "high":
                action = "remove_or_hold"
                replacement = "[REMOVE UNTIL PUBLICLY DISCLOSED OR APPROVED]"
                rationale = mnpi_rationale(
                    rule=finding.rule,
                    jurisdiction=finding.jurisdiction,
                    severity=finding.severity,
                    matched_text=finding.matched_text,
                    tenant_id=tenant_id,
                )
            else:
                action = "verify_or_rewrite"
                replacement = "[CITE PUBLIC SOURCE OR GENERALISE CLAIM]"
                rationale = mnpi_rationale(
                    rule=finding.rule,
                    jurisdiction=finding.jurisdiction,
                    severity=finding.severity,
                    matched_text=finding.matched_text,
                    tenant_id=tenant_id,
                )

            suggestions.append(
                ReviewSuggestion(
                    id=f"suggestion:{index}",
                    finding_id=finding.id,
                    action=action,
                    replacement_text=replacement,
                    rationale=rationale,
                )
            )
        return suggestions

    def _llm_tier_engaged(self, *, review_profile: str, mnpi_score: float) -> bool:
        """Return True when the document is eligible for LLM-tier reasoning.

        Three gates, all must hold:
          - profile opt-in: `audit_grade` (caller asked for the LLM tier)
          - score band: mnpi_score in [LLM_TIER_MNPI_LOWER, LLM_TIER_MNPI_UPPER)
          - components available: at least one of (public_evidence_retriever, llm_adjudicator)

        This is the two-tier engine's router: a document outside the ambiguous band either
        can't be moved by the LLM (score already high enough to be a deterministic high) or
        doesn't need the LLM (score already SAFE on deterministic signal). The router keeps
        p95 latency bounded for the 90% case.
        """
        if review_profile != "audit_grade":
            return False
        # any of the three LLM-tier helpers is sufficient to engage the band gate;
        # individual helpers still self-gate on their own preconditions further down.
        if (
            self.public_evidence_retriever is None
            and self.llm_adjudicator is None
            and self.llm_coverage_auditor is None
        ):
            return False
        return LLM_TIER_MNPI_LOWER <= mnpi_score < LLM_TIER_MNPI_UPPER

    def _maybe_public_evidence(
        self, *, text: str, entity_id: str | None, mnpi_score: float, engage: bool
    ) -> dict[str, Any] | None:
        if not engage:
            return None
        if mnpi_score <= 0 or self.public_evidence_retriever is None:
            return None
        try:
            return self.public_evidence_retriever.retrieve(text=text, entity_id=entity_id, lexicon=None)
        except Exception as exc:
            raise ReviewLayerError("public_evidence", f"public-evidence retrieval failed: {exc}") from exc

    def _maybe_llm_adjudication(
        self,
        *,
        text: str,
        overall_risk: Classification,
        public_evidence: dict[str, Any] | None,
        engage: bool,
        findings: list | None = None,
        entity_id: str | None = None,
    ) -> dict[str, Any] | None:
        if not engage:
            return None
        if self.llm_adjudicator is None or overall_risk == Classification.SAFE:
            return None
        # adjudicate() accepts findings + entity_id as optional kwargs so
        # structured-tokens mode has the data it needs. raw_text mode ignores them.
        # using kwargs-with-default avoids breaking callers that implement the older
        # interface (dummy adjudicators in tests, etc.).
        try:
            return self.llm_adjudicator.adjudicate(
                text=text,
                current_classification=overall_risk.value,
                public_evidence=public_evidence,
                findings=findings,
                entity_id=entity_id,
            )
        except TypeError:
            # backwards-compat shim: older adjudicators reject the new kwargs.
            try:
                return self.llm_adjudicator.adjudicate(
                    text=text,
                    current_classification=overall_risk.value,
                    public_evidence=public_evidence,
                )
            except Exception as retry_exc:
                raise ReviewLayerError("llm_adjudicator", f"LLM adjudication failed: {retry_exc}") from retry_exc
        except Exception as exc:
            raise ReviewLayerError("llm_adjudicator", f"LLM adjudication failed: {exc}") from exc

    def review(
        self,
        *,
        text: str,
        source_jurisdiction: str,
        destination_jurisdiction: str,
        entity_id: str | None,
        include_suggestions: bool,
        document_type: str = "generic",
        session_id: str | None = None,
        matter_id: str | None = None,
        review_profile: str = "strict",
        tenant_id: str | None = None,
    ) -> ReviewResult:
        if review_profile not in VALID_REVIEW_PROFILES:
            raise ValueError(
                f"review_profile must be one of {sorted(VALID_REVIEW_PROFILES)}; got {review_profile!r}"
            )
        packs = resolve_rule_packs(source_jurisdiction, destination_jurisdiction)
        defined_terms = extract_defined_terms(text)
        # audit_grade-only LLM pre-pass over the preamble to catch defined terms the regex
        # misses. cached by document hash; raw doc body is not sent (the helper sees only
        # the first PREAMBLE_CHAR_CAP characters).
        if review_profile == "audit_grade" and self.llm_defined_term_extractor is not None:
            from kaypoh.review.llm_defined_terms import extract_with_cache

            defined_terms = defined_terms | extract_with_cache(
                text=text, extractor=self.llm_defined_term_extractor,
            )
        # cross-doc defined-term inheritance: merge prior session-scoped terms into the current
        # document's set, then persist the current document's terms back to the session store so
        # the next related-doc review inherits them too. SPA defines `the "Purchaser"` once;
        # a paired disclosure schedule reviewed in the same session inherits that suppression.
        if session_id:
            from kaypoh.review.session_store import add_defined_terms, load_defined_terms

            inherited = load_defined_terms(session_id, tenant_id=tenant_id)
            defined_terms = defined_terms | inherited
            if defined_terms - inherited:
                add_defined_terms(session_id, defined_terms - inherited, tenant_id=tenant_id)
        # item 55: matter-scoped inheritance sits above session-scope. Sessions belong to a matter;
        # defined terms accumulate at matter level and inherit into every session within that matter.
        # Closes the 30+ document M&A case where session-scope loses inheritance once the session
        # rotates. matter terms persist across reviewers / weeks / sessions under the same matter_id.
        if matter_id:
            from kaypoh.review.matter_store import (
                add_defined_terms as add_matter_terms,
                load_defined_terms as load_matter_terms,
            )

            matter_inherited = load_matter_terms(matter_id, tenant_id=tenant_id)
            defined_terms = defined_terms | matter_inherited
            if defined_terms - matter_inherited:
                add_matter_terms(matter_id, defined_terms - matter_inherited, tenant_id=tenant_id)
        findings = self._pii_findings(text, packs, document_type, defined_terms) + self._mnpi_findings(
            text, packs, defined_terms, document_type
        )
        # items 95 + 96: lift contingent/tipping severity when co-located with a deal substrate.
        # Mutates in place before scoring so the escalated severity feeds into mnpi_score.
        _amplify_co_occurring_low_mnpi(findings)

        # item 73: entity-size-relative materiality (SAB 99 + ASX GN8). Mutates
        # financial_amount / financial_percentage severities per jurisdiction tier ladder
        # when an entity_size_lookup is configured. Fails loud via degraded_modes when not.
        degraded_modes: list[dict[str, Any]] = _scale_financial_by_entity_size(
            findings,
            jurisdiction=_pack_scope(packs),
            entity_id=entity_id,
            entity_size_lookup=self.entity_size_lookup,
        )

        # item 84: blackout-window calendrical detector. Fires when document date + earnings
        # date co-occur within the per-jurisdiction closed period (SGX 14d/30d, HKEX 30d/60d,
        # UK/EU MAR 30d/30d). US Reg FD has no codified duration; not registered. Standalone
        # medium severity — does not need the items-95/96/97 amplifier.
        mnpi_legal_basis = _legal_basis(packs, "mnpi_rules")
        findings.extend(
            _detect_blackout_period_references(
                text,
                packs=packs,
                jurisdiction=_pack_scope(packs),
                legal_basis=mnpi_legal_basis,
                idx_start=len(findings),
            )
        )

        # item 101: quasi-identifier combination seed. audit_grade only; appends one finding
        # per cluster of ≥3 distinct quasi-identifier rules within a 500-char window.
        jurisdiction_label = _pack_scope(packs)
        pii_legal_basis = _legal_basis(packs, "pii_rules")
        findings.extend(
            _detect_quasi_identifier_combinations(
                findings,
                review_profile=review_profile,
                jurisdiction=jurisdiction_label,
                legal_basis=pii_legal_basis,
                idx_start=len(findings),
            )
        )
        pii_score = self._score(findings, "PII")
        mnpi_score = self._score(findings, "MNPI")
        document_score = max(pii_score, mnpi_score)
        overall_risk = _risk_from_score(document_score)

        engage_llm_tier = self._llm_tier_engaged(review_profile=review_profile, mnpi_score=mnpi_score)
        public_evidence = self._maybe_public_evidence(
            text=text, entity_id=entity_id, mnpi_score=mnpi_score, engage=engage_llm_tier
        )
        # item 36: after retrieval, attribute a source-verification state to every MNPI finding.
        # aggregate semantics (the retriever returns one verdict for the document, not per-finding):
        #   queried + sources non-empty   -> public_source_matched
        #   queried + sources empty       -> no_public_source_found
        #   queried + sources empty + an unverified_claim signal -> ambiguous
        #   any other status              -> leave whatever _mnpi_findings already set
        # MNPI findings that already self-cited via _INDOC_URL_RE keep their public_source_matched
        # state (per-finding evidence beats document-aggregate retrieval evidence).
        _apply_retrieval_verification(findings, public_evidence)
        privacy_ledger = list((public_evidence or {}).get("privacy_ledger", []))
        llm_adjudication = self._maybe_llm_adjudication(
            text=text,
            overall_risk=overall_risk,
            public_evidence=public_evidence,
            engage=engage_llm_tier,
            findings=findings,
            entity_id=entity_id,
        )
        if llm_adjudication is not None:
            privacy_ledger.append(
                {
                    "destination": str(llm_adjudication.get("provider") or "llm"),
                    "operation": "llm_adjudication",
                    "allowed": llm_adjudication.get("status") == "adjudicated",
                    "reason": str(
                        llm_adjudication.get("review_recommendation")
                        or llm_adjudication.get("status")
                        or ""
                    ),
                    "query": "",
                    "redactions": [],
                    "input_mode": str(llm_adjudication.get("input_mode") or ""),
                }
            )
        if llm_adjudication and llm_adjudication.get("status") == "adjudicated":
            label = llm_adjudication.get("risk_label")
            if label in Classification.__members__ and max(pii_score, mnpi_score) < 85.0:
                overall_risk = Classification(label)

        # inverse-audit "what did we miss?" — audit_grade only. advisory output goes both
        # into the result (for immediate reviewer visibility) AND the journal (so the
        # audit-pack export carries it). engine never acts on these warnings.
        coverage_warnings: list[dict[str, Any]] = []
        if engage_llm_tier and self.llm_coverage_auditor is not None:
            from kaypoh.review.llm_coverage_audit import run_coverage_audit

            coverage_warnings = run_coverage_audit(
                text=text,
                findings=findings,
                document_type=document_type,
                auditor=self.llm_coverage_auditor,
            )
        try:
            suggestions = self._suggestions(findings, include_suggestions, tenant_id=tenant_id)
        except CitationOverrideError as exc:
            raise ReviewLayerError("citation_override", f"citation override resolution failed: {exc}") from exc

        return ReviewResult(
            overall_risk=overall_risk,
            document_score=round(document_score, 3),
            pii_score=round(pii_score, 3),
            mnpi_score=round(mnpi_score, 3),
            jurisdictions_applied=[pack.code for pack in packs],
            jurisdiction_policy="strictest_wins",
            findings=findings,
            suggestions=suggestions,
            public_evidence=public_evidence,
            llm_adjudication=llm_adjudication,
            privacy_ledger=privacy_ledger,
            coverage_warnings=coverage_warnings,
            degraded_modes=degraded_modes,
        )
