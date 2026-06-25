from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Any

from junas.backend.schemas import Classification
from junas.external.privacy_guard import EMAIL_RE, LONG_NUMBER_RE, MONEY_RE, PERCENT_RE, PHONE_RE
from junas.review.citations import CitationOverrideError, mnpi_rationale, pii_rationale
from junas.review.conjunctive_mnpi import detect_conjunctive_mnpi
from junas.review.defined_terms import extract_defined_terms, is_defined_term
from junas.review.detectors import (
    DetectorContext,
    DetectorRegistry,
    detect_address_findings,
    detect_core_identifier_findings,
    detect_personal_attribute_inferences,
    detect_semantic_pii_fallback_findings,
    detect_sg_wedge_remainder_findings,
    detect_us_driver_license_findings,
    driver_license_coverage_warnings,
    semantic_pii_degraded_modes,
)
from junas.review.document_structure import parse_document_structure
from junas.review.entity_linker import canonical_person, strip_honorific
from junas.review.jurisdictions import JurisdictionRulePack, normalize_jurisdiction, resolve_rule_packs

SG_NRIC_RE = re.compile(r"\b[STFGM]\d{7}[A-Z]\b", re.IGNORECASE)
# ACRA UEN: legacy 8-9 digit + check letter; new T-format.
SG_UEN_RE = re.compile(r"\b(?:\d{8,9}[A-Z]|T\d{2}[A-Z]{2}\d{4}[A-Z])\b")
PASSPORT_RE = re.compile(
    r"\b(?:passport|pass no\.?|passport no\.?)\s*[:#-]?\s*((?=[A-Z0-9]*\d)[A-Z0-9]{6,12})\b",
    re.IGNORECASE,
)
SG_POSTAL_RE = re.compile(r"\b(?:Singapore|S)\s*(\d{6})\b", re.IGNORECASE)
BANK_ACCOUNT_RE = re.compile(
    r"\b(?:account\s+no\.?|acct\s+no\.?|a/c|iban|swift|bank\s+account)\s*[:#-]\s*"
    r"((?-i:(?=[A-Z0-9x* -]{0,33}\d)[A-Z0-9][A-Z0-9x* -]{5,33}[A-Z0-9x*]))\b"
    r"|\baccount\s+((?-i:(?=[A-Z0-9-]{0,33}\d)[A-Z0-9][A-Z0-9-]{5,33}[A-Z0-9]))\b",
    re.IGNORECASE,
)
BANK_ACCOUNT_ENDING_RE = re.compile(
    r"\bbank\s+account\s+ending\s+-?\d{2,6}\b",
    re.IGNORECASE,
)
CONTRACT_UNIT_PRICE_RE = re.compile(
    r"\b(?:unit\s+price|price\s+per\s+(?:share|unit|seat|licen[cs]e)|per-unit\s+price)\s*"
    r"(?:is|of|:|=)?\s*(?:SGD|USD|S\$|\$)\s*[\d,]+(?:\.\d{1,4})?\b",
    re.IGNORECASE,
)
CONTRACT_DISCOUNT_RE = re.compile(
    r"\b(?:contract\s+)?(?:discount|rebate)\s*(?:rate)?\s*(?:is|of|:|=)?\s*"
    r"\d{1,2}(?:\.\d+)?\s*%(?=$|\s|[.,;:)])",
    re.IGNORECASE,
)
VOLUME_COMMITMENT_RE = re.compile(
    r"\b(?:minimum|annual|monthly|quarterly)?\s*volume\s+commitment\s*(?:is|of|:|=)?\s*"
    r"\d{1,3}(?:,\d{3})+(?:\.\d+)?\s*(?:units|licen[cs]es|seats|tonnes|tons|MWh|kWh)\b",
    re.IGNORECASE,
)
ROYALTY_RATE_RE = re.compile(
    r"\b(?:royalty\s+rate\s*(?:is|of|:|=)?\s*\d{1,2}(?:\.\d+)?\s*%|"
    r"\d{1,2}(?:\.\d+)?\s*%\s+royalty)(?=$|\s|[.,;:)])",
    re.IGNORECASE,
)
TOTAL_CONTRACT_VALUE_RE = re.compile(
    r"\b(?:total\s+contract\s+value|aggregate\s+contract\s+value|contract\s+value|TCV)\s*"
    r"(?:is|of|:|=)?\s*(?:SGD|USD|S\$|\$)\s*[\d,]+(?:\.\d{1,2})?\b",
    re.IGNORECASE,
)
MATERIAL_EVENT_RE = re.compile(
    r"\b(acquisition|acquire|merger|takeover|buyout|earnings|guidance|forecast|"
    r"profit warning|dividend|buyback|bankruptcy|restructuring|layoff|fraud|"
    r"investigation|subpoena|cybersecurity|breach|financing|offering|ipo|"
    r"impairment|provision|resignation|"
    r"(?:ceo|cfo|chief\s+(?:executive|financial)\s+officer)\s+"
    r"(?:resign(?:s|ed|ation)?|steps?\s+down|stepped\s+down|"
    r"depart(?:s|ed|ure)?|appointed|appointment)|"
    # legal-contract additions: deal-closing + definitive-agreement vocabulary
    r"definitive\s+agreement|binding\s+agreement|memorandum\s+of\s+understanding|"
    r"letter\s+of\s+intent|consummation|closing|settlement\s+agreement)\b",
    re.IGNORECASE,
)
_MATERIAL_EVENT_NEGATED_CONTEXT_RE = re.compile(
    r"\b(?:"
    r"not\s+(?:price[- ]sensitive|a\s+profit\s+forecast|profit\s+forecast|"
    r"profit\s+warning|earnings\s+guidance|mnpi|upsi)|"
    r"absence\s+of\s+mnpi|no\s+(?:new\s+)?(?:price[- ]sensitive|upsi|mnpi)|no\s+unpublished|"
    r"no\s+material\s+non[- ]public\s+information|"
    r"no\s+material\s+non[- ]public\s+information\s+remains|"
    r"contains\s+no\s+unpublished|public\s+and\s+stale|public/stale|"
    r"already[-\s]+announced\s+terms|"
    r"no\s+upsi\s+(?:is\s+)?included|are\s+not\s+upsi|"
    r"disclosure\s+status\s+regarding|corporate\s+context|"
    r"no\s+event\s+has\s+occurred|"
    r"no\s+new\s+material\s+terms|internal\s+timelines\s+are\s+illustrative\s+only|"
    r"does\s+not\s+alter\s+risk\s+profile|anti[- ]fraud\s+analytics|fully\s+remediated|"
    r"no\s+cross[- ]border\s+movement[^\n.;]{0,80}(?:planned|required)|"
    r"breach\s+may\s+trigger\s+internal\s+sanctions|employment\s+integration|"
    r"does\s+not\s+(?:itself\s+)?create\s+a\s+current\s+disclosure\s+obligation|"
    r"does\s+not\s+(?:itself\s+)?(?:contain|constitute)\s+(?:mnpi|"
    r"(?:a\s+)?mac|earnings\s+guidance|(?:a\s+)?profit\s+forecast)|"
    r"does\s+not\s+make\s+the\s+content\s+price\s+sensitive|"
    r"reg\s+fd\s*/\s*hipaa\s*/\s*glba\s+guidance|"
    r"policy\s+guidance|"
    r"external\s+references\s+allowed|ok\s+to\s+cite|"
    r"decline\s+and\s+refer[^\n.;]{0,80}(?:public|website|filed)|"
    r"employment\s+matter[^\n.;]{0,80}temporary\s+suspension|"
    r"no\s+material\s+adverse\s+change|"
    r"no\s+(?:live\s+)?(?:incident|breach|breach\s+specifics|forecast\s+downgrades)|"
    r"public\s+(?:cybersecurity\s+)?training\s+materials|"
    r"format\s+guidance\s+only|operational\s+guidance|abstract\s+dei\s+guidance|"
    r"compliance\s+guidance|(?:NPC|regulatory)\s+guidance|"
    r"non-production\s+examples|"
    r"illustrative\s+case\s+studies|public\s+journals|do\s+not\s+pertain|"
    r"education\s+only|public\s+mas\s+guidance"
    r")\b",
    re.IGNORECASE,
)
_MATERIAL_EVENT_PUBLIC_CONTEXT_RE = re.compile(
    r"\b(?:"
    r"generally\s+available|"
    r"(?:previously|already)[-\s]+announced|"
    r"public(?:ly)?\s+available|"
    r"public\s+(?:announcement|disclosures?|information|reference|source|filings?|notice)|"
    r"public\s+(?:release|transaction\s+status)|"
    r"(?:is|are)\s+public|"
    r"ok\s+to\s+cite|external\s+references\s+allowed|"
    r"decline\s+and\s+refer[^\n.;]{0,80}(?:public|website|filed)|"
    r"materials?\s+are\s+public|public\s+form\s+17-c|"
    r"announced\s+on|e[- ]disclosure|"
    r"public\s+and\s+stale|"
    r"from\s+(?:public|openly\s+available)\s+materials?|"
    r"no\s+(?:new\s+)?(?:price[- ]sensitive|upsi|mnpi)|no\s+unpublished|"
    r"not\s+price[- ]sensitive|not\s+mnpi|not\s+upsi|not\s+required|not\s+an\s+announcement|"
    r"educational|training|format\s+guidance\s+only|operational\s+guidance|"
    r"non-production\s+examples|"
    r"illustrative\s+case\s+studies|public\s+journals|do\s+not\s+pertain|"
    r"no\s+(?:sgxnet\s+)?disclosure\s+is\s+required"
    r")\b",
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
    r"\b(confidential|non-public|nonpublic|not yet public|not yet publicly disclosed|not disclosed|undisclosed|"
    r"internal only|internal circulation only|internal use only|restricted|do not distribute|"
    r"should not be distributed externally|before announcement|pre-announcement|"
    r"quiet period|material non-public information|inside information|price[- ]sensitive information|PSI|"
    r"unpublished price[- ]sensitive information|unpublished material information|undisclosed material facts|"
    r"market[- ]sensitive information|not generally available|not generally known|not for market release|"
    r"mnpi)\b|(?:未公表|未公開|非公開|公表前|未公布|未公告|미공개|공개\s*전|시장\s*공개\s*전)",
    re.IGNORECASE,
)
PUBLIC_RE = re.compile(
    r"\b(publicly announced|press release|filed|disclosed|published|reported|HKEXnews|HKEX announcement|"
    r"ASX announcement|market announcement|continuous disclosure announcement|TDnet|timely disclosure|"
    r"TSE disclosure|KRX KIND|DART filing)\b",
    re.IGNORECASE,
)
NAME_RE = re.compile(
    r"\b(?i:(?:Mr|Ms|Mrs|Mdm|Dr|Prof))\.?[ \t]+[A-Z][a-z]+(?:[-\u2010-\u2015][A-Z][a-z]+)?"
    r"(?:[ \t]+(?:(?i:bin|binti|s/o|d/o|a/l|a/p|al)[ \t]+)?"
    r"[A-Z][a-z]+(?:[-\u2010-\u2015][A-Z][a-z]+)?){0,5}\b"
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
    r"subject to (?:board|shareholder|shareholders'|regulatory|management|"
    r"investment\s+committee|IC|due diligence|financing|condition[s]?\s+precedent|"
    r"HKEX|SFC|SEHK|Listing\s+Committee|ASX|ASIC|TSE|JPX|J[- ]?FSA|KRX|FSC|FSS|DART) "
    r"(?:approval[s]?|clearance[s]?|sign[ -]off|consent)|"
    r"pending (?:board|shareholder|shareholders'|regulatory|management|investment\s+committee|IC|"
    r"HKEX|SFC|SEHK|Listing\s+Committee|ASX|ASIC|TSE|JPX|J[- ]?FSA|KRX|FSC|FSS|DART) "
    r"(?:approval[s]?|clearance[s]?|sign[ -]off|consent)|"
    r"ASIC relief|FSC review|FSS review|SEHK clearance|J[- ]?FSA clearance|"
    r"(?:likely|expected) to (?:close|approve|materialise|materialize|impact|complete|"
    r"result in|conclude|sign|announce)|"
    r"under (?:active )?consideration|"
    r"in (?:advanced |preliminary |early[ -]stage |ongoing |non[ -]binding )?"
    r"(?:discussions|negotiations)|"
    r"exploratory(?:\s+(?:talks|discussions|stage|phase))?|"
    r"pre[ -]decisional|"
    r"management believes|"
    r"early indications suggest|"
    r"may (?:result in|lead to|trigger) (?:a |an )?(?:acquisition|merger|disposal|takeover|"
    r"restructuring|divestiture|impairment|spin[ -]off)"
    r")\b",
    re.IGNORECASE,
)
# items 78 + 99: pseudonymised-but-linkable identifiers. GDPR Recital 26 + PDPC
# Anonymisation Advisory Guidelines treat IDs that the organisation can re-link to a
# subject as personal data even when the bare token is not immediately identifying.
# Every pattern is context-anchored, and non-UUID captures are case-sensitive with a
# digit-presence lookahead to defend against lowercase prose matching as an identifier.
EMPLOYEE_ID_RE = re.compile(
    r"(?:Employee\s+(?:ID|No\.?|Number)|EMP-|Staff\s+(?:ID|No\.?|Number))[\s:.#-]*"
    r"(?-i:(?=[A-Z0-9-]*\d)([A-Z0-9][A-Z0-9-]{3,11}))(?![A-Za-z0-9-])",
    re.IGNORECASE,
)
CUSTOMER_ACCOUNT_RE = re.compile(
    r"(?:(?<!Bank\s)Customer\s+(?:Account|ID|Reference)|ACCT-|CUST-|"
    r"(?<!Insurance\s)(?<!Policy\s)(?<!Plan\s)(?<!Benefits\s)(?<!Insured\s)"
    r"Member\s+(?:ID|No\.?|Number))[\s:.#-]*"
    r"(?-i:(?=[A-Z0-9-]*\d)([A-Z0-9][A-Z0-9-]{3,15}))\b",
    re.IGNORECASE,
)
MEDICAL_RECORD_RE = re.compile(
    r"(?:MRN|Medical\s+Record\s+(?:No\.?|Number)|Patient\s+(?:ID|No\.?|Number))[\s:.#-]*(\d{6,12})\b",
    re.IGNORECASE,
)
_UUID_TOKEN = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
INTERNAL_SESSION_ID_RE = re.compile(
    r"\b(?:"
    r"(?:internal\s+)?(?:user\s+)?session\s+(?:ID|token)|"
    r"login\s+session\s+(?:ID|token)|"
    r"internal\s+user\s+(?:ID|token)"
    r")\s*[:=#-]\s*(?:uuid\s*)?"
    r"(?:" + _UUID_TOKEN + r")(?:_(?:session|user))?\b|"
    r"\b(?:" + _UUID_TOKEN + r")_(?:session|user)\b",
    re.IGNORECASE,
)
BANK_CUSTOMER_REFERENCE_RE = re.compile(
    r"\b(?:"
    r"bank\s+(?:customer|client|internal)\s+(?:reference|ref|ID|No\.?|Number)|"
    r"CIF\s+(?:ID|No\.?|Number)|"
    r"bank\s+CIF|"
    r"customer\s+information\s+file\s+(?:ID|No\.?|Number)"
    r")[\s:.#-]*(?-i:(?=[A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{4,15})\b",
    re.IGNORECASE,
)
INSURANCE_MEMBER_ID_RE = re.compile(
    r"\b(?:"
    r"insurance\s+member\s+(?:ID|No\.?|Number)|"
    r"policy\s+member\s+(?:ID|No\.?|Number)|"
    r"plan\s+member\s+(?:ID|No\.?|Number)|"
    r"benefits\s+member\s+(?:ID|No\.?|Number)|"
    r"insured\s+member\s+(?:ID|No\.?|Number)|"
    r"member\s+certificate\s+(?:ID|No\.?|Number)"
    r")[\s:.#-]*(?-i:(?=[A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{4,15})\b",
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
    r"wall[- ]crossed (?:holders|investors|analysts|placees)|"
    r"market sounding(?:s)? to (?:select|institutional|cornerstone) (?:investors|holders|placees)|"
    r"pre[- ]brief(?:ing)? (?:select|institutional|cornerstone) (?:investors|holders|placees)|"
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
    r"SFC insider list|"
    r"ASX restricted list|"
    r"TDnet embargo list|"
    r"KRX restricted list|"
    r"grey list|"
    r"permanent insider list|"
    r"J[- ]?IR embargo list|"
    r"KIND disclosure hold list|"
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
    r"private[- ]side wall|"
    r"public[- ]side wall|"
    r"private[- ]side/public[- ]side controls?|"
    r"wall[- ]crossing controls?|"
    r"deal team quarantine|"
    r"restricted[- ]list controls?|"
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
PHARMA_TRIAL_MNPI_RE = re.compile(
    r"\b("
    r"Phase\s+(?:I{1,3}|IV|[1-4])\s+(?:clinical\s+)?trial\s+(?:top[- ]line\s+)?(?:data|results|readout)|"
    r"top[- ]line\s+(?:clinical\s+)?(?:data|results|readout)|"
    r"primary\s+endpoint\s+(?:met|missed|not\s+met|failed)|"
    r"interim\s+analysis\s+(?:met|missed|failed|stopped|halted)|"
    r"DSMB\s+(?:recommendation|halt|stop|safety\s+signal)|"
    r"FDA\s+(?:clinical\s+hold|complete\s+response\s+letter|CRL|breakthrough\s+therapy\s+designation)|"
    r"EMA\s+(?:CHMP\s+opinion|marketing\s+authorisation\s+refusal)|"
    r"regulatory\s+(?:approval|rejection)\s+for\s+(?:the\s+)?(?:drug|therapy|indication)"
    r")\b",
    re.IGNORECASE,
)
FINANCIAL_SERVICES_REGULATORY_MNPI_RE = re.compile(
    r"\b("
    r"(?:CET1|Tier\s+1|capital)\s+(?:shortfall|breach|ratio\s+breach)|"
    r"(?:liquidity\s+coverage\s+ratio|LCR|NSFR)\s+(?:breach|shortfall)|"
    r"stress[- ]test\s+(?:failure|result|shortfall)|"
    r"(?:PRA|FCA|MAS|OCC|Federal\s+Reserve|FDIC|SEC|FINRA)\s+(?:consent\s+order|enforcement\s+action|"
    r"supervisory\s+letter|matter\s+requiring\s+attention|MRA|MRIA)|"
    r"AML\s+(?:remediation\s+order|control\s+deficiency|enforcement\s+action)|"
    r"sanctions\s+screening\s+(?:breach|deficiency)|"
    r"customer\s+redress\s+provision"
    r")\b",
    re.IGNORECASE,
)
ENERGY_RESERVES_MNPI_RE = re.compile(
    r"\b("
    r"(?:proved|probable|2P|3P)\s+reserves?\s+(?:downgrade|upgrade|restatement|write[- ]down)|"
    r"reserve\s+(?:replacement\s+ratio|downgrade|upgrade|restatement)|"
    r"(?:discovery|appraisal|exploration)\s+well\s+(?:result|success|failure|dry\s+hole)|"
    r"drilling\s+(?:result|success|failure)|"
    r"production\s+guidance\s+(?:cut|reduction|increase|revision)|"
    r"impairment\s+(?:charge|test)\s+(?:for|on)\s+(?:oil|gas|mining|energy)\s+assets?"
    r")\b",
    re.IGNORECASE,
)
LEGAL_PROCEEDING_MNPI_RE = re.compile(
    r"\b("
    r"(?:settlement\s+in\s+principle|settlement\s+term\s+sheet|class[- ]action\s+settlement)|"
    r"(?:adverse|draft)\s+(?:judg(?:e)?ment|ruling|award)|"
    r"(?:arbitration\s+award|tribunal\s+award)\s+(?:expected|draft|adverse|favourable)|"
    r"(?:DOJ|SEC|FCA|SFO|MAS|ACCC|ASIC)\s+(?:settlement|enforcement\s+settlement|deferred\s+prosecution\s+agreement)|"
    r"litigation\s+(?:reserve|provision)\s+(?:increase|release|write[- ]back)|"
    r"(?:injunction|freezing\s+order|asset\s+freeze)\s+(?:granted|denied|expected|draft)"
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
PERSONAL_DATA_SECURITY_SAFEGUARDS_RE = re.compile(
    r"\b("
    r"reasonable\s+security\s+safeguards|"
    r"data\s+security\s+measures\s+(?:for|to\s+protect)\s+personal\s+data|"
    r"access\s+controls?\s+for\s+personal\s+data|"
    r"(?:logs?|monitoring)\s+(?:and\s+)?review\s+(?:of|for)\s+personal\s+data\s+access|"
    r"encryption,?\s+obfuscation,?\s+masking\s+or\s+(?:the\s+use\s+of\s+)?virtual\s+tokens"
    r")\b",
    re.IGNORECASE,
)
PERSONAL_DATA_BREACH_NOTIFICATION_RE = re.compile(
    r"\b("
    r"personal\s+data\s+breach|"
    r"intimat(?:e|ion)\s+(?:to\s+)?(?:each\s+)?affected\s+data\s+principal|"
    r"notify\s+(?:each\s+)?affected\s+data\s+principal|"
    r"breach\s+notification\s+(?:to|for)\s+(?:affected\s+)?data\s+principals?|"
    r"description\s+of\s+the\s+breach,?\s+including\s+its\s+nature"
    r")\b",
    re.IGNORECASE,
)


# item 98: special-category PII v1 seed — religion / union / political. Anchored detectors
# under GDPR Art 9(1) (verbatim list: racial/ethnic, political, religion/philosophy, trade-union,
# genetic, biometric, health, sex life); PIPA Korea Art 23 (sensitive incl. union + political);
# APPI Japan Art 2(3) "special care-required" (creed covers religion + political; union NOT
# explicitly enumerated); LGPD Brazil Art 5(II); PIPL China Art 28 (religion + minors <14;
# political NOT explicitly enumerated); UAE PDPL Art 15 + KSA PDPL Art 6 (religion + political,
# union NOT enumerated); PDPC SG Advisory Guidelines on Key Concepts (rev Oct 2024) treats these
# as warranting higher standard of protection (not a distinct legal class). DPDPA India has no
# sensitive-data tier (escalation is via SDF designation s10, not data-class).
#
# v1 shipped religion/union/political. Items 105/106/108 extend the same strict-anchor
# pattern to health/medical, biometric/genetic, and sex-life/orientation.
#
# Anchor strategy: each pattern requires proximity context within ±6 tokens. Religion fires
# only near a named_person OR explicit faith/practice marker. Trade-union fires only near
# membership/representation marker. Political fires only near member/supporter/voter marker.
# Defends against Christian Dior / Hindu Kush / AFL Premiership / Trade Union Square /
# "ruling party of the contract" / "Independent Green Party".
#
# Per-category opt-out via JUNAS_SPECIAL_CATEGORY_DISABLE=religion,union,political,
# health,biometric,genetic,sexual for tenants with high false-positive sensitivity.

# Religion vocabulary anchored on faith/practice marker. The non-capturing trailing context
# absorbs whitespace + up to 30 chars of the faith-marker so the matched span covers the
# subject phrase, not just the lone faith token. Lowercase prose matches via re.IGNORECASE
# but the FAITH_RE alternation excludes proper-name colliders: "Dior" / "Khan" are not faiths.
_RELIGION_TERMS = (
    r"Christian|Catholic|Protestant|Anglican|Methodist|Orthodox|Lutheran|Baptist|"
    r"Muslim|Sunni|Shia|Shi'?ite|Muhammadan|"
    r"Buddhist|Theravada|Mahayana|"
    r"Hindu|"
    r"Sikh|"
    r"Jewish|Judaic|Orthodox\s+Jew|"
    r"Jain|"
    r"Taoist|Daoist|"
    r"agnostic|atheist|"
    r"Bahai|Baha'?i|"
    r"Zoroastrian|Parsi"
)
RELIGION_RE = re.compile(
    # The matched span includes both the faith marker AND the trigger phrase to give
    # reviewers context. Trigger phrases lock the religious-belief reading.
    r"\b(?:"
    # Pattern A: "Dr Jane Tan is a (devout|practicing|observant)? Muslim" / "...is Christian"
    r"(?:Mr|Ms|Mrs|Mdm|Dr|Prof|Sir|Dame)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\s+"
    r"(?:is|was|identifies\s+as|practices?|practiced|practising|practised|"
    r"belongs?\s+to|adheres?\s+to|converted\s+to|raised\s+(?:as\s+)?(?:a\s+)?)\s+"
    r"(?:a\s+)?(?:devout|practi[cs]ing|observant|orthodox|reformed|liberal)?\s*"
    r"(?:" + _RELIGION_TERMS + r")"
    r"|"
    # Pattern B: explicit faith / religion / religious-affiliation marker
    r"(?:religious\s+affiliation|faith|religion|religious\s+belief|religious\s+practice|"
    r"creed)\s*[:=]\s*(?:" + _RELIGION_TERMS + r")"
    r"|"
    # Pattern C: "members? of the (Catholic|Buddhist|...) (church|community|faith)"
    r"members?\s+of\s+(?:the\s+)?(?:" + _RELIGION_TERMS + r")\s+"
    r"(?:church|community|faith|congregation|temple|mosque|parish|gurudwara|synagogue)"
    r"|"
    # Pattern D: "attends? the (parish|mosque|temple|synagogue|gurudwara)"
    r"(?:attends?|prays\s+at|worships\s+at)\s+(?:the\s+)?"
    r"(?:parish|mosque|temple|synagogue|gurudwara|church|congregation)"
    r")\b",
    re.IGNORECASE,
)

# Trade-union vocabulary requires explicit membership / representation marker. Excludes
# "Trade Union Square", "Union Pacific" (railway), "AFL Premiership" (Australian Football).
TRADE_UNION_RE = re.compile(
    r"\b(?:"
    # Pattern A: "member of (the )? (NTUC|union|...)"
    r"member\s+of\s+(?:the\s+)?(?:NTUC|TUC|AFL[- ]CIO|DGB|CGT|trade\s+union|labou?r\s+union|"
    r"workers'?\s+union|union)"
    r"|"
    # Pattern B: "joined the union" / "joined NTUC" — employment context implied by verb
    r"joined\s+(?:the\s+)?(?:NTUC|TUC|AFL[- ]CIO|DGB|CGT|trade\s+union|labou?r\s+union|"
    r"workers'?\s+union)"
    r"|"
    # Pattern C: explicit role + employment context
    r"(?:union\s+(?:member|representative|delegate|steward)|shop\s+steward)"
    r"|"
    # Pattern D: collective-bargaining + action markers (these don't need pre-context)
    r"collective\s+bargaining\s+(?:agreement|representative|unit)|"
    r"(?:strike|industrial\s+action)\s+ballot|"
    r"picket\s+line"
    r"|"
    # Pattern E: "represented by (the )? union"
    r"represented\s+by\s+(?:the\s+|her\s+|his\s+|their\s+)?(?:union|trade\s+union|labou?r\s+union)"
    r")\b",
    re.IGNORECASE,
)

# Political-opinion vocabulary requires explicit party-membership / electoral marker. Excludes
# court usage ("the opposition argued"), legal-language usage ("ruling party of the contract"),
# and adjective-only "Independent" / "Green" without party-suffix anchor.
_POLITICAL_PARTIES = (
    # SG
    r"PAP|People'?s\s+Action\s+Party|WP|Workers'?\s+Party|PSP|Progress\s+Singapore\s+Party|"
    r"SDP|Singapore\s+Democratic\s+Party|"
    # US
    r"Democrats?|Democratic\s+Party|Republicans?|Republican\s+Party|GOP|"
    # UK — bare "Labour" / "Conservatives" included because the surrounding pattern
    # (voted for / member of / donated to) already locks the political reading.
    r"Tory|Tories|Conservatives?|Conservative\s+Party|Labour(?:\s+Party)?|"
    r"Liberal\s+Democrats?|Lib\s+Dems?|Reform\s+UK|Green\s+Party|"
    # JP / KR
    r"LDP|Liberal\s+Democratic\s+Party\s+of\s+Japan|CDP|Komeito|"
    r"Democratic\s+Party\s+of\s+Korea|People\s+Power\s+Party|"
    # CN
    r"CCP|Chinese\s+Communist\s+Party|"
    # AU
    r"Labor\s+Party|Liberal\s+Party\s+of\s+Australia|Nationals\s+Party|"
    # DE / FR / IT
    r"CDU|SPD|AfD|Bündnis\s+90|Die\s+Linke|"
    r"En\s+Marche|La\s+République\s+En\s+Marche|RN|Rassemblement\s+National|"
    # IN
    r"BJP|Bharatiya\s+Janata\s+Party|INC|Indian\s+National\s+Congress|AAP|Aam\s+Aadmi\s+Party"
)
POLITICAL_RE = re.compile(
    r"\b(?:"
    # Pattern A: "member of (the )? <Party>"
    r"members?\s+of\s+(?:the\s+)?(?:" + _POLITICAL_PARTIES + r")"
    r"|"
    # Pattern B: "supporter of (the )? <Party>" / "donated to <Party>"
    r"(?:supporters?|donors?|activists?)\s+(?:of|for|to)\s+(?:the\s+)?"
    r"(?:" + _POLITICAL_PARTIES + r")"
    r"|"
    r"donated\s+(?:to|towards?)\s+(?:the\s+)?(?:" + _POLITICAL_PARTIES + r")"
    r"|"
    # Pattern C: voted/campaigned + party
    r"(?:voted\s+(?:for|against)|campaigned\s+for|endorsed)\s+(?:the\s+)?"
    r"(?:" + _POLITICAL_PARTIES + r")"
    r"|"
    # Pattern D: registered party affiliation
    r"registered\s+(?:as\s+(?:a\s+)?)?(?:" + _POLITICAL_PARTIES + r")"
    r"|"
    # Pattern E: explicit affiliation marker
    r"(?:political\s+affiliation|party\s+affiliation|party\s+membership)\s*[:=]\s*"
    r"(?:" + _POLITICAL_PARTIES + r")"
    r")\b",
    re.IGNORECASE,
)

_HEALTH_CONDITION_TERMS = (
    r"type\s+[12]\s+diabetes|diabetes|hypertension|HIV|AIDS|cancer|carcinoma|"
    r"leukaemia|leukemia|asthma|epilepsy|schizophrenia|bipolar\s+disorder|"
    r"major\s+depressive\s+disorder|depression|anxiety\s+disorder|PTSD|"
    r"pregnancy|pregnant|tuberculosis|hepatitis\s+[ABC]|chronic\s+kidney\s+disease|"
    r"Parkinson'?s(?:\s+disease)?|Alzheimer'?s(?:\s+disease)?|stroke|"
    r"myocardial\s+infarction|heart\s+attack|autism\s+spectrum\s+disorder|ADHD|"
    r"COPD|multiple\s+sclerosis|sickle\s+cell(?:\s+disease)?|thalassa?emia|"
    r"dengue(?:\s+fever)?|endometriosis|lupus"
)
HEALTH_CONDITION_RE = re.compile(
    r"\b(?:"
    # Pattern A: named subject + diagnosis / condition verb.
    r"(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\s+"
    r"(?:has|had|reports|reported|is\s+diagnosed\s+with|was\s+diagnosed\s+with|"
    r"is\s+positive\s+for|tested\s+positive\s+for|is\s+being\s+treated\s+for)\s+"
    r"(?:a\s+|an\s+)?(?:" + _HEALTH_CONDITION_TERMS + r")"
    r"|"
    # Pattern B: explicit medical-field marker.
    r"(?:diagnosis|diagnoses|medical\s+condition|health\s+condition|clinical\s+condition|"
    r"problem\s+list|past\s+medical\s+history)\s*[:=]\s*"
    r"(?:a\s+|an\s+)?(?:" + _HEALTH_CONDITION_TERMS + r")"
    r"|"
    # Pattern C: canonical ICD diagnosis code, but only when anchored as a diagnosis code.
    r"(?:diagnosis\s+code|ICD-10(?:-CM)?\s+code|ICD\s+code)\s*[:#-]?\s*"
    r"[A-Z]\d{2}(?:\.\d{1,4})?"
    r")\b",
    re.IGNORECASE,
)

_MEDICATION_TERMS = (
    r"metformin|insulin|semaglutide|warfarin|heparin|sertraline|fluoxetine|"
    r"olanzapine|lithium|lamotrigine|levetiracetam|salbutamol|albuterol|"
    r"antiretroviral\s+therapy|PrEP|Truvada|chemotherapy|radiotherapy|dialysis|"
    r"lisinopril|amlodipine|atorvastatin|omeprazole|prednisolone|methotrexate|"
    r"adalimumab|antipsychotic|antidepressant|antiepileptic"
)
MEDICAL_TREATMENT_RE = re.compile(
    r"\b(?:"
    # Pattern A: named subject + treatment / prescription verb.
    r"(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\s+"
    r"(?:is\s+prescribed|was\s+prescribed|takes|took|is\s+taking|started|receives|"
    r"received|underwent|is\s+undergoing)\s+(?:" + _MEDICATION_TERMS + r")"
    r"|"
    # Pattern B: explicit treatment / medication field marker.
    r"(?:medication|medications|prescription|treatment|therapy|Rx)\s*[:=]\s*"
    r"(?:" + _MEDICATION_TERMS + r")"
    r"|"
    # Pattern C: procedure/treatment marker with a medical verb.
    r"(?:scheduled\s+for|underwent|receiving|received|referred\s+for)\s+"
    r"(?:chemotherapy|radiotherapy|dialysis|surgery|cognitive\s+behavio(?:u)?ral\s+therapy|CBT)"
    r")\b",
    re.IGNORECASE,
)

BIOMETRIC_IDENTIFIER_RE = re.compile(
    r"\b(?:"
    # GDPR Recital 51: photographs are biometric only when processed through specific
    # technical means for unique identification/authentication. Keep this anchored on
    # templates, enrollment, matching, or authentication language.
    r"biometric\s+(?:template|identifier|record|profile|enrol(?:l)?ment|authentication|match)"
    r"(?:\s*[:=]\s*(?:finger(?:print)?|voice\s*print|voiceprint|retina|iris|face|facial|palm\s+vein)"
    r"\s+(?:template|scan|hash|record|identifier|match))?"
    r"|"
    r"finger(?:print)?\s+(?:template|scan|hash|record|enrol(?:l)?ment|authentication|match)"
    r"|"
    r"voice\s*print|voiceprint|"
    r"(?:retina|retinal|iris)\s+(?:scan|template|pattern|recognition|match)|"
    r"(?:facial\s+recognition|face\s+recognition|faceprint)\s+"
    r"(?:template|embedding|identifier|match|authentication)|"
    r"palm\s+vein\s+(?:template|scan|pattern)|"
    r"gait\s+(?:signature|recognition|template)"
    r")\b",
    re.IGNORECASE,
)

GENETIC_DATA_RE = re.compile(
    r"\b(?:"
    r"(?:genetic|genomic|DNA)\s+(?:test(?:ing)?(?:\s+result)?|result|profile|sequence|data|report|marker)"
    r"(?:\s*[:=]\s*(?:BRCA[12]|APOE\s*e[234]|HLA[-\s]?(?:B\*?1502|[A-Z0-9]+)|"
    r"LDLR|CFTR|PALB2|TP53|MLH1|MSH2)\s+"
    r"(?:positive|negative|carrier|variant|mutation|status))?"
    r"|"
    r"(?:BRCA[12]|APOE\s*e[234]|HLA[-\s]?(?:B\*?1502|[A-Z0-9]+)|LDLR|CFTR|PALB2|TP53|MLH1|MSH2)\s+"
    r"(?:positive|negative|carrier|variant|mutation|status)"
    r"|"
    r"(?:carrier\s+status|pathogenic\s+variant|likely\s+pathogenic\s+variant|"
    r"germline\s+mutation|pharmacogenomic\s+result|whole\s+genome\s+sequence)"
    r")\b",
    re.IGNORECASE,
)

_SEXUAL_ORIENTATION_TERMS = (
    r"gay|lesbian|bisexual|queer|homosexual|heterosexual|asexual|pansexual|"
    r"LGBTQ\+?|LGBTIQ\+?"
)
SEXUAL_ORIENTATION_RE = re.compile(
    r"\b(?:"
    r"(?:sexual\s+orientation|orientation)\s*[:=]\s*(?:" + _SEXUAL_ORIENTATION_TERMS + r")"
    r"|"
    r"(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\s+"
    r"(?:identifies\s+as|identified\s+as|came\s+out\s+as|is|was)\s+"
    r"(?:a\s+|an\s+)?(?:" + _SEXUAL_ORIENTATION_TERMS + r")"
    r"|"
    r"(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\s+"
    r"(?:has|listed|named|disclosed)\s+(?:a\s+)?same[- ]sex\s+(?:partner|spouse)"
    r")\b",
    re.IGNORECASE,
)

SEX_LIFE_RE = re.compile(
    r"\b(?:"
    r"(?:sexual\s+history|sex\s+life|sexual\s+activity|STI\s+status|contraception\s+use)"
    r"\s*[:=]\s*[A-Za-z0-9][^\n.;]{0,80}"
    r"|"
    r"(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\s+"
    r"(?:disclosed|reported|confirmed|denied)\s+"
    r"(?:sexual\s+history|sexual\s+activity|STI\s+status|contraception\s+use)"
    r")\b",
    re.IGNORECASE,
)

_RACIAL_ETHNIC_TERMS = (
    r"Chinese|Han\s+Chinese|Malay|Indian|Tamil|Eurasian|Arab|Bedouin|Persian|Kurdish|"
    r"Hui|Uyghur|Uighur|Tibetan|Mongol|Manchu|Zhuang|Korean|Japanese|Roma|Romani|"
    r"Hispanic|Latino|Latina|Black|African|Afro[- ]Caribbean|White|Caucasian|"
    r"Aboriginal|Torres\s+Strait\s+Islander|Māori|Maori|Samoan|Javanese|Sundanese|"
    r"汉族|回族|维吾尔族|藏族|蒙古族|满族|壮族|朝鲜族|"
    r"عربي|بدوي|فارسي|كردي|أفريقي|آسيوي"
)
RACIAL_ETHNIC_ORIGIN_RE = re.compile(
    r"\b(?:"
    r"(?:racial\s+origin|ethnic\s+origin|race|ethnicity|ethnic\s+group|ethnic\s+background)\s*[:=]\s*"
    r"(?:" + _RACIAL_ETHNIC_TERMS + r")"
    r"|"
    r"(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\s+"
    r"(?:is\s+ethnically|has\s+ethnic\s+origin\s+listed\s+as|is\s+of)\s+"
    r"(?:" + _RACIAL_ETHNIC_TERMS + r")(?:\s+(?:descent|origin|background|ethnicity))?"
    r"|"
    r"(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}'?s\s+"
    r"(?:race|ethnicity|ethnic\s+origin|racial\s+origin|ethnic\s+background)\s+"
    r"(?:is|was|listed\s+as|recorded\s+as|:|=)\s*(?:" + _RACIAL_ETHNIC_TERMS + r")"
    r"|"
    r"(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\s+"
    r"(?:is|was|identifies\s+as)\s+(?:an?\s+)?(?:ethnic\s+)?"
    r"(?:" + _RACIAL_ETHNIC_TERMS + r")\s+(?:person|employee|patient|client)"
    r"|"
    r"(?:民族|种族|族裔|族群)\s*[:：]\s*(?:" + _RACIAL_ETHNIC_TERMS + r")"
    r"|"
    r"(?:العرق|الأصل\s+العرقي|الأصل\s+الإثني|الإثنية)\s*[:：]\s*(?:"
    + _RACIAL_ETHNIC_TERMS + r")"
    r")",
    re.IGNORECASE,
)
MULTILINGUAL_RELIGION_RE = re.compile(
    r"(?:宗教信仰|宗教|信仰)\s*[:：]\s*(?:佛教|基督教|伊斯兰教|穆斯林|天主教|道教|印度教|锡克教|犹太教)"
    r"|(?:الدين|المعتقد\s+الديني)\s*[:：]\s*(?:مسلم|إسلام|مسيحي|يهودي|هندوسي|بوذي|سيخي)",
    re.IGNORECASE,
)
MULTILINGUAL_TRADE_UNION_RE = re.compile(
    r"(?:工会会员|工会成员|工会代表|集体谈判代表)[ \t]*[:：][ \t]*[\u4e00-\u9fffA-Za-z0-9 -]{1,40}"
    r"|加入工会[^\n.;]{0,20}"
    r"|(?:労働組合員|労組員|組合員)[ \t]*[:：][ \t]*[\u3040-\u30ff\u4e00-\u9fffA-Za-z0-9 -]{1,40}"
    r"|(?:노동조합원|노조원|노조\s+가입)[ \t]*[:：]?[ \t]*[\uac00-\ud7afA-Za-z0-9 -]{0,40}"
    r"|(?:عضو\s+نقابة|عضوية\s+النقابة|ممثل\s+نقابي|انضم\s+إلى\s+النقابة|مفاوضة\s+جماعية)",
    re.IGNORECASE,
)
MULTILINGUAL_POLITICAL_RE = re.compile(
    r"(?:政治观点|政治立场|政党成员|党派|党员|政党隶属)[ \t]*[:：][ \t]*[\u4e00-\u9fffA-Za-z0-9 -]{1,40}"
    r"|(?:政治的見解|支持政党|政党所属)[ \t]*[:：][ \t]*[\u3040-\u30ff\u4e00-\u9fffA-Za-z0-9 -]{1,40}"
    r"|(?:정치적\s+견해|정당\s+소속|지지\s+정당)[ \t]*[:：][ \t]*[\uac00-\ud7afA-Za-z0-9 -]{1,40}"
    r"|(?:الانتماء\s+السياسي|الرأي\s+السياسي|الانتماء\s+الحزبي)[ \t]*[:：][ \t]*[\u0600-\u06ffA-Za-z0-9 -]{1,50}"
    r"|عضو\s+حزب(?:[ \t]*[:：][ \t]*[\u0600-\u06ffA-Za-z0-9 -]{1,50})?",
    re.IGNORECASE,
)
MULTILINGUAL_HEALTH_CONDITION_RE = re.compile(
    r"(?:诊断|健康状况|医疗健康信息|病史)[ \t]*[:：][ \t]*(?:糖尿病|高血压|癌症|艾滋病|HIV|乙肝|慢性肾病)"
    r"|(?:診断|健康状態|病歴)[ \t]*[:：][ \t]*(?:糖尿病|高血圧|がん|癌|HIV|慢性腎臓病)"
    r"|(?:진단|건강\s+상태|병력)[ \t]*[:：][ \t]*(?:당뇨병|고혈압|암|HIV|만성\s+신장질환)"
    r"|(?:التشخيص|الحالة\s+الصحية|المعلومات\s+الصحية)\s*[:：]\s*"
    r"(?:السكري|ارتفاع\s+ضغط\s+الدم|السرطان|فيروس\s+نقص\s+المناعة|مرض\s+كلوي)",
    re.IGNORECASE,
)
MULTILINGUAL_MEDICAL_TREATMENT_RE = re.compile(
    r"(?:用药|药物|处方|治疗|治疗方案)[ \t]*[:：][ \t]*(?:胰岛素|二甲双胍|化疗|放疗|透析|舍曲林)"
    r"|(?:服薬|薬剤|処方|治療)[ \t]*[:：][ \t]*(?:インスリン|メトホルミン|化学療法|放射線治療|透析)"
    r"|(?:복용약|약물|처방|치료)[ \t]*[:：][ \t]*(?:인슐린|메트포르민|항암치료|방사선치료|투석)"
    r"|(?:العلاج|الدواء|الوصفة\s+الطبية)[ \t]*[:：][ \t]*"
    r"(?:إنسولين|ميتفورمين|علاج\s+كيميائي|غسيل\s+الكلى|سيرترالين)",
    re.IGNORECASE,
)
MULTILINGUAL_BIOMETRIC_RE = re.compile(
    r"(?:生物识别(?:模板|信息|记录)?|指纹模板|虹膜扫描|人脸识别模板|声纹)\s*[:：]?\s*"
    r"(?:指纹|虹膜|人脸|面部|声纹|掌静脉)?"
    r"|(?:生体認証(?:テンプレート|情報)?|指紋テンプレート|虹彩スキャン|顔認証テンプレート|声紋)\s*[:：]?\s*"
    r"|(?:생체정보|생체\s+인식\s+템플릿|지문\s+템플릿|홍채\s+스캔|얼굴\s+인식\s+템플릿|성문)\s*[:：]?\s*"
    r"|(?:قالب\s+بصمة|بصمة\s+إصبع|مسح\s+القزحية|قالب\s+التعرف\s+على\s+الوجه|بصمة\s+صوتية)",
    re.IGNORECASE,
)
MULTILINGUAL_GENETIC_RE = re.compile(
    r"(?:基因检测结果|遗传检测结果|DNA检测结果|基因数据)\s*[:：]\s*"
    r"(?:BRCA[12]|APOE\s*e[234]|HLA[-\s]?[A-Z0-9]+)[^\n.;]{0,20}(?:阳性|携带者|突变|变异)"
    r"|(?:遺伝子検査結果|遺伝情報|DNA検査結果)\s*[:：]\s*"
    r"(?:BRCA[12]|APOE\s*e[234]|HLA[-\s]?[A-Z0-9]+)[^\n.;]{0,20}(?:陽性|保因|変異)"
    r"|(?:유전자\s+검사\s+결과|유전\s+정보|DNA\s+검사\s+결과)\s*[:：]\s*"
    r"(?:BRCA[12]|APOE\s*e[234]|HLA[-\s]?[A-Z0-9]+)[^\n.;]{0,20}(?:양성|보인자|변이)"
    r"|(?:نتيجة\s+الاختبار\s+الجيني|بيانات\s+جينية|ملف\s+DNA)\s*[:：]?\s*"
    r"(?:(?:BRCA[12]|APOE\s*e[234]|HLA[-\s]?[A-Z0-9]+)[^\n.;]{0,20}(?:إيجابي|حامل|طفرة))?",
    re.IGNORECASE,
)
MULTILINGUAL_SEXUAL_ORIENTATION_RE = re.compile(
    r"(?:性取向|取向)[ \t]*[:：][ \t]*(?:同性恋|双性恋|女同性恋|男同性恋|异性恋|泛性恋|无性恋)"
    r"|(?:性的指向|性的嗜好)[ \t]*[:：][ \t]*(?:同性愛|両性愛|レズビアン|ゲイ|異性愛|無性愛)"
    r"|(?:성적\s+지향|성향)[ \t]*[:：][ \t]*(?:동성애|양성애|레즈비언|게이|이성애|무성애)"
    r"|(?:الميول\s+الجنسية|التوجه\s+الجنسي)[ \t]*[:：][ \t]*"
    r"(?:مثلي|مثلية|ثنائي\s+الميول|مغاير|لاجنسي)",
    re.IGNORECASE,
)
MULTILINGUAL_SEX_LIFE_RE = re.compile(
    r"(?:性史|性生活|性行为|性传播感染状态|避孕使用)[ \t]*[:：][ \t]*[\u4e00-\u9fffA-Za-z0-9 -]{1,60}"
    r"|(?:性歴|性生活|性行為|性感染症状態|避妊使用)[ \t]*[:：][ \t]*[\u3040-\u30ff\u4e00-\u9fffA-Za-z0-9 -]{1,60}"
    r"|(?:성생활|성관계|성병\s+상태|피임\s+사용)[ \t]*[:：][ \t]*[\uac00-\ud7afA-Za-z0-9 -]{1,60}"
    r"|(?:التاريخ\s+الجنسي|الحياة\s+الجنسية|النشاط\s+الجنسي|حالة\s+الأمراض\s+المنقولة\s+جنسياً)[ \t]*[:：][ \t]*"
    r"[\u0600-\u06ffA-Za-z0-9 -]{1,70}",
    re.IGNORECASE,
)


# item 107: jurisdiction-age-cliff minors detector. Single rule with per-juris severity
# resolution via _MINOR_AGE_CLIFFS map (research-recommended; avoids duplicate findings).
#
# Statutes (verified 2026-05-27):
#  - DPDPA India 2023 s2(f) + s9: "child" = under 18; verifiable parental consent;
#    s9(3) prohibits behavioural monitoring / targeted ads to children
#  - GDPR Art 8: default 16; member states may lower to ≥13
#  - PIPL China Art 31: under 14 = minor requiring guardian consent
#  - COPPA US 16 CFR Part 312: under 13 (Jan 2025 amendments — data retention + third-party opt-in)
#  - PDPC SG Advisory Guidelines on Children's Personal Data (Mar 2024): default under 18;
#    under-13 cannot give valid consent
#  - UK ICO Age-Appropriate Design Code: under 18 in force Sept 2021
#  - AU OAIC Children's Online Privacy Code: under 18 (mandated by Privacy Amendment Act 2024;
#    OAIC phase-3 consultation ran 31 Mar 2026 to 5 Jun 2026; code due Dec 2026)
#  - HK PCPD Guidance Note on Personal Data of Minors: under 18
#  - UAE PDPL: no explicit cliff; defers to Wadeema Law (Federal Law 3/2016) under 18
#  - KSA PDPL: child = under 18 via Saudi Child Protection Law
#  - LGPD Brazil Art 14: under 18 + special protection for under-12
_MINOR_AGE_CLIFFS: dict[str, int] = {
    "IN": 18,  # DPDPA s2(f)
    "SG": 18,  # PDPC Children's Data Advisory Guidelines (Mar 2024)
    "UK": 18,  # ICO Age-Appropriate Design Code
    "AU": 18,  # OAIC Children's Code (pending Dec 2026)
    "HK": 18,  # PCPD Minors Guidance Note
    "AE": 18,  # Wadeema Law
    "SA": 18,  # Saudi Child Protection Law
    "BR": 18,  # LGPD Art 14
    "EU": 16,  # GDPR Art 8 default (member states may lower to 13)
    "CN": 14,  # PIPL Art 31
    "US": 13,  # COPPA
    # SEA baseline conservatively follows the strictest SG/MY/ID/TH/PH/VN default
    "SEA": 18,
    "MY": 18,
    "ID": 18,
    "TH": 18,
    "PH": 18,
    "VN": 18,
    "JP": 18,
    "KR": 18,
}

# Match explicit age/grade/minor lexicon. Captures the age digit so the post-pass can resolve
# severity against the applicable jurisdiction cliff.
MINOR_DATA_RE = re.compile(
    r"\b(?:"
    # Pattern A: "age N" / "aged N" / "N years old" / "N-year-old" with N in 0-19
    r"(?:age[ds]?|aged)\s*[:=]?\s*(?P<age_a>\d{1,2})\b"
    r"|"
    r"(?P<age_b>\d{1,2})[- ]year[- ]old"
    r"|"
    r"(?P<age_c>\d{1,2})\s+years?\s+old"
    r"|"
    # Pattern B: "under N" / "below N" / "younger than N"
    r"(?:under|below|younger\s+than)\s+(?P<age_d>1[0-8]|[1-9])\s+(?:years?\s+of\s+age|years?\s+old|"
    r"$|[,\.\)\]\;])"
    r"|"
    # Pattern C: minor/juvenile/child lexicon — must be adjacent to data/processing marker
    # OR parental-consent marker to avoid "child labour law" / "children's clothing" FPs
    r"(?:minor|child(?:ren)?|juvenile|underage|ward)(?:'?s)?\s+"
    r"(?:personal\s+data|data|information|profile|account|consent|details)"
    r"|"
    r"(?:personal\s+data|data|information|account|profile)\s+of\s+(?:a\s+|the\s+)?"
    r"(?:minors?|child(?:ren)?|juveniles?|underage\s+(?:user|customer|individual)s?)"
    r"|"
    r"(?:child(?:ren)?|minor(?:s)?|underage\s+users?)(?:'?s)?\s+"
    r"(?:online\s+activity|location\s+data|photos?|videos?)"
    r"|"
    r"(?:online\s+activity|location\s+data|photos?|videos?)\s+of\s+"
    r"(?:minors?|child(?:ren)?|underage\s+users?)"
    r"|"
    r"(?:age\s+assurance|age[- ]gating|age\s+verification)\s+(?:for|of)\s+"
    r"(?:minors?|child(?:ren)?|under[- ]?18s?|underage\s+users?|online\s+service\s+users)"
    r"|"
    r"(?:behaviou?ral\s+monitoring|tracking)\s+of\s+"
    r"(?:minors?|child(?:ren)?|underage\s+users?)"
    r"|"
    r"targeted\s+advertis(?:ing|ements?)\s+(?:to|at|for|directed\s+at)\s+"
    r"(?:minors?|child(?:ren)?|underage\s+users?)"
    r"|"
    # Pattern D: school-grade markers (SG / UK / US)
    r"(?:primary|secondary)\s+(?P<grade_sg>[1-6])\b"
    r"|"
    r"Year\s+(?P<grade_uk>[1-9]|1[0-3])\s+(?:student|pupil|class)"
    r"|"
    r"(?P<grade_us>\d{1,2})(?:st|nd|rd|th)\s+grade(?:\s+(?:student|class|teacher))?"
    r"|"
    r"(?:kindergarten|nursery|preschool|playgroup|elementary\s+school|"
    r"middle\s+school|junior\s+high|high\s+school)\s+"
    r"(?:student|pupil|class|enrolment|enrollment|register|roster)"
    r"|"
    # Pattern E: verifiable parental consent / VPC / guardian consent
    r"verifiable\s+parental\s+consent|"
    r"\bVPC\b|"
    r"parental\s+consent|"
    r"guardian(?:'s)?\s+consent|"
    r"consent\s+of\s+(?:a\s+|the\s+)?parent(?:\s+or\s+guardian)?|"
    r"in\s+loco\s+parentis"
    r")",
    re.IGNORECASE,
)

# Reject "for 18+ years (of experience|in the industry)" and "Year N of the contract"
# false positives via post-match context check. Keep this here so the regex stays readable.
_MINOR_FP_TRAILING = re.compile(
    r"^\s*(?:\+|of\s+(?:experience|service|industry|tenure|the\s+(?:contract|agreement|"
    r"term|lease|policy|grade)))",
    re.IGNORECASE,
)
_MINOR_FP_LEADING_GRADE = re.compile(
    r"\b(?:grade|category|level|class|rating|tier)\s*$",
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
# junas.configs.runtime once enough journal-replay data exists.
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
# meaningful concept for personal data.
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
    metadata: dict[str, Any] = field(default_factory=dict)


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


def _drain_privacy_ledger_events(component: Any | None) -> list[dict[str, Any]]:
    if component is None or not hasattr(component, "pop_privacy_ledger_events"):
        return []
    events = component.pop_privacy_ledger_events()
    if not isinstance(events, list):
        raise ReviewLayerError("privacy_ledger", "component returned non-list privacy ledger events")
    return [dict(event) for event in events if isinstance(event, dict)]


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
    metadata: dict[str, Any] | None = None,
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
        metadata=dict(metadata or {}),
    )


# Narrow negation-window check used by the MAC/MAE rule. Looks ~20 chars left of the match
# for a negator that immediately precedes it. Catches the common forms — "no MAC", "not a
# MAC clause", "without any MAC clause" — without trying to be a general parser. Anything
# more nuanced (subordinate clauses, double negatives) is deliberately left to the LLM tier.
_NEGATION_LOOKBACK = re.compile(
    r"\b(?:no|nor|not|without|never|absent|excluding|neither)\b[\s\w]{0,15}\Z",
    re.IGNORECASE,
)
_ASSERTION_NEGATION_LOOKBACK = re.compile(
    r"\b(?:nothing|no\s+(?:statement|language|draft|section|clause))\b[^\n.;]{0,80}"
    r"\b(?:asserts?|states?|constitutes?|indicates?|confirms?|says)\s+"
    r"(?:a|an|any|the)?\s*\Z",
    re.IGNORECASE,
)
_FUNCTIONAL_CONTACT_CONTEXT_RE = re.compile(
    r"\b(?:"
    r"role[-\u2010-\u2015 ]only|role[-\u2010-\u2015 ]based|role\s+mailbox|functional\s+mailbox|"
    r"role/functional\s+mailbox|shared\s+inbox|treasury\s+contact|"
    r"generic\s+mailboxes?|generic\s+organi[sz]ational\s+mailbox|"
    r"generic\s+supplier\s+contact(?:s|\s+examples?)?|generic\s+intake\s+email|"
    r"public\s+contacts?|procedural\s+queries\s+only|"
    r"placeholder\s+email|form\s+labels?|marketing\s+emails?|"
    r"public,?\s+non[- ]transactional|"
    r"compliance\s+desk|deal\s+desk|contact\s+compliance|route\s+enquiries|"
    r"queries\s+(?:to|contact)|rout(?:e|ed)\s+to\s+legal|via\s+docroom|"
    r"public\s+(?:queries|enquiries)|enquiries\s*:|regulatory\s+liaison|"
    r"generic\s+help\s*desk|public(?:-facing)?\s+help\s*desk|public\s+helpdesk|"
    r"secretariat\s+mailbox|public\s+helplines?|public[^\n.;]{0,60}helplines?|"
    r"general\s+(?:queries|enquiries)|"
    r"not\s+personal\s+data|"
    r"non[- ]PII|not\s+PII|"
    r"not\s+linked\s+to\s+an?\s+identifiable\s+individual"
    r")\b",
    re.IGNORECASE,
)
_PUBLIC_PHONE_CONTEXT_RE = re.compile(
    r"\b(?:"
    r"compliance\s+desk|deal\s+desk|"
    r"public(?:-facing)?\s+help\s*desk|public\s+helpdesk|public\s+helplines?|"
    r"public[^\n.;]{0,60}helplines?|"
    r"public\s+hotline|public\s+line|public\s+service\s+line|"
    r"consumer\s+hotline|"
    r"public\s+enquir(?:y|ies)\s+hotline|enquiries\s+line|procedural\s+queries\s+only|"
    r"public\s+(?:queries|enquiries)|"
    r"service\s+line\s+only|"
    r"call\s+cent(?:er|re)|"
    r"DSAR\s+hotline|"
    r"support\s+hotline|switchboard|reception|information\s+line|contact\s+centre|client\s+services|"
    r"(?:privacy|ethics)\s+helplines?|assistance\s+line|published\s+contacts?|"
    r"generic\s+(?:in[-\u2010-\u2015 ]house\s+)?ivr|in[-\u2010-\u2015 ]house\s+ivr|"
    r"hr\s+help\s*desk|general\s+line|general\s+help\s+lines?|"
    r"hotline\s+investor|nomor\s+publik|bukan\s+nomor\s+pribadi|"
    r"tổng\s+đài|công\s+khai|không\s+dùng\s+số\s+cá\s+nhân|"
    r"general\s+(?:queries|enquiries)|queries\s+contact|general\s+hotline|label\s+only|"
    r"not\s+be\s+captured\s+as\s+PII|"
    r"not\s+personal\s+data|"
    r"public,?\s+non[- ]personal|"
    r"not\s+a\s+deal\s+contact|not\s+MNPI"
    r")\b",
    re.IGNORECASE,
)
_ALWAYS_ROLE_MAILBOX_LOCAL_PARTS = frozenset({
    "admin", "ap", "ar", "billing", "capitalmarkets", "corpsec", "cosec",
    "compliance", "dealroom", "disclosure", "docroom", "dpo", "help", "helpdesk",
    "irmailbox", "listings", "media", "mna", "press", "privacy", "privacydesk",
    "role", "room", "secretariat", "service", "servicedesk", "support", "treasury", "walloffice",
})
_CONTEXTUAL_ROLE_MAILBOX_LOCAL_PARTS = frozenset({
    "contact", "cybersecurity", "info", "legal", "project", "service", "traders",
})
_ROLE_MAILBOX_LOCAL_RE = re.compile(
    r"^(?:"
    r"(?:sg|hk|au|jp|kr|my|id|th|ph|vn|uk|eu|us|in)?compliance|"
    r".*[._-]compliance|"
    r"ir|investor[._-]?relations|grievance|noreply|no-reply|procurement|infosec|"
    r"privacyoffice|pitcompliance|pit-code|hr[._-]?notify|"
    r".*[._-](?:support|helpdesk|procurement|infosec|grievance)$"
    r")$"
)
_DATE_LIKE_PHONE_RE = re.compile(
    r"(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:\s+\d{1,2})?|"
    r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}(?:\s+\d{1,2})?|"
    r"\d{1,2}\.\d{1,2}\.\d{2,4}|"
    r"\d{4}-\d{4}|"
    r"\d{4}-\d{2}-\d{2}-\d{2}|"
    r"\d{1,2}[-/]\d{1,2}[-/]\d{4}\s+\(\d+(?:\.\d+)?)\Z"
)
_THAI_ID_LIKE_PHONE_RE = re.compile(r"\d-\d{4}-\d{5}-\d{2}-\d\Z")
_IPV4_LITERAL_RE = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}\Z")
_NON_PHONE_NUMERIC_CONTEXT_RE = re.compile(
    r"\b(?:UEN|NRIC|FIN|MyKad|NIK|NPWP|NIB|passport|UKPA|EIN|ISIN|LEI|a/c|acc\s*t|account|"
    r"bank\s*acct|payroll\s*acct|A\s*/\s*c|"
    r"rekening|national\s+id|national\s+identifier|member[- ]state\s+ID|"
    r"CNP|cod\s+numeric\s+personal|company\s+no|co\.\s+no|"
    r"reg\.\s+no|registration\s+no|\bCR\b|CRN|CIN|C\s*I\s*N|commercial\s+registration|"
    r"filing\s+ref|tax\s+id|tax\s+ref|tax\s+no|TINs?|VAT|V\s*A\s*T|ZATCA|GAZT|MST|EPF|SWIFT|"
    r"TRN|CRN|trade\s+licen[cs]e|commercial\s+licen[cs]e|Emirates\s+I\s*D|EID|"
    r"national\s+address|Bldg|Iqama|IQA\s*MA|National\s+ID|NID|AP\s+No|"
    r"serial|device\s+serial|IMEI|IP|DOB|dated|"
    r"Pag-?IBIG|PhilHealth|MID|doc\s*code|doccode|OCR|artifacts?|"
    r"Rp|IDR|harga|nilai|miliar|triliun|billion|million|RSU|"
    r"Aadhaar|PAN|GSTIN|placeholder|sample|specimen|test\s+fields?|training\s+placeholder|"
    r"template\s+packet|form\s+labels?|"
    r"session\s+ref|vpn\s+ref|access\s+token|internal\s+user\s+id|ticket|"
    r"employee\s+nos?\.?|employee\s+id|payroll\s+ref|SSA\s+ref|job\s+ID|"
    r"asset\s+tag|badge)\b",
    re.IGNORECASE,
)
_LARGE_NUMBER_IDENTIFIER_CONTEXT_RE = re.compile(
    r"\b(?:UEN|NRIC|FIN|MyKad|NIK|NPWP|NIB|passport|postal|IMEI|IP|"
    r"national\s+id|national\s+identifier|member[- ]state\s+ID|"
    r"CNP|cod\s+numeric\s+personal|company\s+no|co\.\s+no|"
    r"Companies\s+House|Companies?\s+Register|Delaware\s+Div(?:ision)?\.?\s+of\s+Corporations|"
    r"File\s+No\.?|ISIN|LEI|"
    r"FRN|firm\s+reference|HMRC\s+UTR|payroll\s+ref|"
    r"reg\.\s+no|registration\s+no|\bCR\b|CRN|commercial\s+registration|"
    r"tax\s+id|tax\s+ref|TINs?|VAT|ZATCA|GAZT|MST|EPF|SWIFT|TRN|CRN|UTR|"
    r"trade\s+licen[cs]e|commercial\s+licen[cs]e|Emirates\s+I\s*D|EID|"
    r"serial|device\s+serial|account\s+no|a/c|"
    r"acc\s*t|rekening|rek\.?|escrow|bank\s+account|akun\s+internal|non-bank|"
    r"internal\s+wallet|wa\.me|session\s+ref|SSA\s+ref|job\s+ID|generic\s+label)\b",
    re.IGNORECASE,
)
_URL_PARAM_IDENTIFIER_CONTEXT_RE = re.compile(
    r"[?&](?:id|uid|co|ref|nik|npwp|nib|cr|nid|iqama)=",
    re.IGNORECASE,
)
_PLACEHOLDER_IDENTIFIER_CONTEXT_RE = re.compile(
    r"\b(?:invalid\s+placeholder|placeholder\s+with\s+an\s+invalid\s+checksum|"
    r"template\s+field|test\s+fields?|generic\s+placeholder|training\s+placeholder|"
    r"placeholder|test[- ]only|system\s+bucket|not\s+real\s+data|"
    r"specimen\s+values?|screenshots?\s+only|"
    r"format\s+example|"
    r"sample\s+(?:PAN|GSTIN|Aadhaar|NRIC|identifier|values?)|"
    r"invalid(?:/dummy)?|for\s+illustration|illustrative)\b",
    re.IGNORECASE,
)
_VIETNAMESE_PLACEHOLDER_IDENTIFIER_CONTEXT_RE = re.compile(
    r"\b(?:minh\s+họa|mẫu|không\s+hợp\s+lệ|không\s+kiểm\s+tra\s+được)\b",
    re.IGNORECASE,
)
_PH_TIN_NON_TAX_CONTEXT_RE = re.compile(
    r"\b(?:account|acct|bank|escrow|settlement|routing|sub[- ]?acct|account\s+no)\b",
    re.IGNORECASE,
)
_PH_TIN_TAX_CONTEXT_RE = re.compile(r"\b(?:TIN|tax|BIR|withholding)\b", re.IGNORECASE)
_PRIVACY_REQUEST_CLOSED_CONTEXT_RE = re.compile(
    r"\b(?:"
    r"fulfilled|closed|completed|executed|resolved|"
    r"zero\s+open\s+tickets|0\s+open\s+tickets|"
    r"no\s+(?:data\s+subject\s+access\s+request|DSAR)[^\n.;]{0,80}(?:received|needed|triggered)|"
    r"no\s+outstanding[^\n.;]{0,120}(?:DSARs?|erasure\s+requests?|consent\s+withdrawal)|"
    r"no\s+DSARs?\s+are\s+pending|no\s+open\s+DSARs?|"
    r"no\s+(?:request|requests)\s+for\s+correction|"
    r"currently\s+in\s+flight|not\s+a\s+live\s+DSAR|no\s+residual\s+processing"
    r")\b",
    re.IGNORECASE,
)
_NON_ATTRIBUTIVE_IDENTIFIER_CONTEXT_RE = re.compile(
    r"\b(?:"
    r"non[- ]attribut(?:ive|able)|"
    r"(?:separated|unlinked)\s+weak\s+identifiers?|"
    r"sample\s+birth\s+date|"
    r"not\s+linked\s+to\s+(?:any\s+)?(?:an?\s+)?(?:identified\s+person|identifiable\s+individual|named\s+individual)"
    r")\b",
    re.IGNORECASE,
)
_PRIVACY_REQUEST_LIVE_CONTEXT_RE = re.compile(
    r"\b(?:received|requested|submitted|seeking|in[- ]progress|queued?|"
    r"access\s+request|erasure\s+request|full\s+extract\s+queued)\b",
    re.IGNORECASE,
)
_PUBLIC_OR_BENIGN_AMOUNT_CONTEXT_RE = re.compile(
    r"\b(?:"
    r"public[- ]source|public\s+(?:information|source|acra|annual\s+report|exchange\s+website)|"
    r"already\s+public|publicly\s+(?:available|announced|disclosed)|"
    r"public\s+and\s+stale|"
    r"per\s+public\s+ACRA|last\s+traded\s+price|"
    r"reimbursement|per\s+diem|wellness|spa[- ]day"
    r")\b",
    re.IGNORECASE,
)


def _is_negated_context(text: str, match_start: int) -> bool:
    window = text[max(0, match_start - 25):match_start]
    if _NEGATION_LOOKBACK.search(window):
        return True
    longer_window = text[max(0, match_start - 100):match_start]
    return bool(_ASSERTION_NEGATION_LOOKBACK.search(longer_window))


def _is_functional_contact_context(text: str, start: int, end: int) -> bool:
    left = max(text.rfind("\n", 0, start), text.rfind(";", 0, start)) + 1
    right_candidates = [
        pos for pos in (text.find("\n", end), text.find(";", end)) if pos >= 0
    ]
    right = min(right_candidates) if right_candidates else len(text)
    context = text[left:right].strip()
    local_part = text[start:end].split("@", 1)[0].casefold()
    if local_part in {"firstname.lastname", "first.last", "name", "name.surname", "given.family"}:
        return True
    role_like = local_part in _CONTEXTUAL_ROLE_MAILBOX_LOCAL_PARTS or bool(
        re.match(r"^(?:project|room|dealroom|docroom)[._-]", local_part)
    )
    if role_like and re.search(r"\benquiries\s*:\s*", context, re.IGNORECASE):
        return True
    if local_part == "traders" and re.search(r"\bcompany\s+emails?\s+such\s+as\b", context, re.IGNORECASE):
        return True
    if _FUNCTIONAL_CONTACT_CONTEXT_RE.search(context):
        strong_public_context = re.search(
            r"\b(?:generic\s+mailboxes?|public\s+contacts?|procedural\s+queries\s+only|"
            r"generic\s+organi[sz]ational\s+mailbox|generic\s+supplier\s+contact(?:s|\s+examples?)?|"
            r"generic\s+intake\s+email|placeholder\s+email|form\s+labels?|"
            r"marketing\s+emails?|non[- ]PII|not\s+PII|public\s+helplines?|"
            r"public[^\n.;]{0,60}helplines?|enquiries\s*:|enquiries\s+line)\b",
            context,
            re.IGNORECASE,
        )
        if strong_public_context:
            return True
    if local_part == "info" and re.search(r"\bpublic\s+channels?\b", context, re.IGNORECASE):
        return True
    if (
        local_part in _ALWAYS_ROLE_MAILBOX_LOCAL_PARTS
        or bool(_ROLE_MAILBOX_LOCAL_RE.fullmatch(local_part))
    ):
        return True
    if role_like and _FUNCTIONAL_CONTACT_CONTEXT_RE.search(context):
        return True
    next_clause = text[end:min(len(text), end + 120)]
    return (
        role_like
        and next_clause.lstrip().startswith(";")
        and bool(_FUNCTIONAL_CONTACT_CONTEXT_RE.search(next_clause))
    )


def _is_obfuscated_email_fragment_context(text: str, start: int, end: int) -> bool:
    before = text[max(0, start - 24):start]
    return bool(re.search(r"[A-Z0-9._%+-]*\.[A-Z0-9._%+-]*[ \t]{2,}\Z", before, re.IGNORECASE))


def _trim_phone_span(text: str, start: int, end: int) -> tuple[int, int]:
    matched = text[start:end]
    newline_offset = matched.find("\n")
    if newline_offset >= 0:
        end = start + newline_offset
    while end > start and text[end - 1] in " \t.,;:":
        end -= 1
    return start, end


def _is_spaced_passport_numeric_context(text: str, start: int, end: int) -> bool:
    before = text[max(0, start - 36):start]
    return bool(re.search(
        r"p\s*a\s*s\s*s\s*p\s*o\s*r\s*t(?:\s*[-:]?\s*[A-Z]){0,4}\s*\Z",
        before,
        re.IGNORECASE,
    ))


def _is_placeholder_passport_context(text: str, start: int, end: int) -> bool:
    left = max(text.rfind("\n", 0, start), text.rfind(";", 0, start)) + 1
    right_candidates = [
        pos for pos in (text.find("\n", end), text.find(";", end)) if pos >= 0
    ]
    right = min(right_candidates) if right_candidates else len(text)
    context = text[left:right]
    return bool(re.search(
        r"\b(?:placeholder|format\s+example|example\s+only|invalid(?:\s+length)?|non[- ]operative)\b",
        context,
        re.IGNORECASE,
    ))


def _is_public_or_generic_phone_context(text: str, start: int, end: int) -> bool:
    digits = _digits_only(text[start:end])
    local_digits = digits[2:] if digits.startswith("65") else digits
    if local_digits.startswith(("1800", "0800", "00800")):
        return True
    context = _line_context(text, start, end)
    if text[start:end].lstrip().startswith("+") and local_digits.startswith("800"):
        return bool(_PUBLIC_PHONE_CONTEXT_RE.search(context))
    return bool(_PUBLIC_PHONE_CONTEXT_RE.search(context))


def _is_non_phone_numeric_context(text: str, start: int, end: int) -> bool:
    matched = text[start:end].strip()
    digits = _digits_only(matched)
    if digits and set(digits) == {"0"}:
        return True
    if digits and len(set(digits)) == 1 and len(digits) >= 8:
        return True
    if _DATE_LIKE_PHONE_RE.fullmatch(matched):
        return True
    if _THAI_ID_LIKE_PHONE_RE.fullmatch(matched):
        return True
    if _IPV4_LITERAL_RE.fullmatch(matched) and _ip_version(matched) == 4:
        return True
    if _is_spaced_passport_numeric_context(text, start, end):
        return True
    if re.search(r"\+[A-Z0-9]*[A-Z][A-Z0-9]*[-\s]*\Z", text[max(0, start - 12):start], re.IGNORECASE):
        return True
    if len(digits) >= 14 and not matched.startswith("+"):
        return True
    if matched.startswith("+"):
        return False
    context = text[max(0, start - 90): min(len(text), end + 90)]
    return bool(
        _NON_PHONE_NUMERIC_CONTEXT_RE.search(context)
        or _URL_PARAM_IDENTIFIER_CONTEXT_RE.search(context)
    )


def _is_closed_or_historical_privacy_request_context(text: str, start: int, end: int) -> bool:
    context = _line_context(text, start, end)
    if re.search(
        r"\b(?:"
        r"no\s+(?:data\s+subject\s+access\s+request|DSAR)[^\n.;]{0,80}(?:received|needed|triggered)|"
        r"no\s+outstanding[^\n.;]{0,120}(?:DSARs?|erasure\s+requests?|consent\s+withdrawal)"
        r")\b",
        context,
        re.IGNORECASE,
    ):
        return True
    if _PRIVACY_REQUEST_LIVE_CONTEXT_RE.search(context):
        return False
    return bool(_PRIVACY_REQUEST_CLOSED_CONTEXT_RE.search(context))


def _is_ph_tin_non_tax_context(text: str, start: int, end: int) -> bool:
    context = _line_context(text, start, end)
    return (
        bool(_PH_TIN_NON_TAX_CONTEXT_RE.search(context))
        and not _PH_TIN_TAX_CONTEXT_RE.search(context)
    )


def _is_negated_mac_address_context(text: str, start: int, end: int) -> bool:
    context = _line_context(text, start, end)
    return bool(re.search(r"\bnot\s+(?:a\s+|an\s+|the\s+)?MAC\s+address\b", context, re.IGNORECASE))


def _is_non_attributive_identifier_context(text: str, start: int, end: int) -> bool:
    context = _line_context(text, start, end)
    return bool(_NON_ATTRIBUTIVE_IDENTIFIER_CONTEXT_RE.search(context))


def _is_negated_material_adverse_change_context(text: str, start: int, end: int) -> bool:
    if _is_negated_context(text, start):
        return True
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)
    context = text[line_start:line_end]
    prefix = text[line_start:end]
    if re.search(
        r"\b(?:"
        r"no\s+event\s+has\s+occurred[^\n.;]{0,120}material\s+adverse\s+change|"
        r"no\s+mac[^\n.;]{0,100}material\s+adverse\s+change|"
        r"not\s+expected\s+to\s+constitute[^\n.;]{0,120}material\s+adverse\s+(?:change|effect)|"
        r"not\s+expected\s+to\s+have[^\n.;]{0,120}material\s+adverse\s+(?:change|effect)|"
        r"does\s+not\s+constitute[^\n.;]{0,140}material\s+adverse\s+(?:change|effect)|"
        r"does\s+not\s+contain[^\n.;]{0,140}material\s+adverse\s+(?:change|effect)|"
        r"shall\s+not\s+constitute[^\n.;]{0,140}material\s+adverse\s+(?:change|effect)|"
        r"nothing\s+in\s+this\s+(?:notice|workflow|document|memo)[^\n.;]{0,120}"
        r"constitutes[^\n.;]{0,120}material\s+adverse\s+(?:change|effect)|"
        r"nothing\s+herein\s+constitutes[^\n.;]{0,80}material\s+adverse\s+(?:change|effect)|"
        r"nothing\s+herein\s+constitutes\s+or\s+admits[^\n.;]{0,80}material\s+adverse\s+(?:change|effect)|"
        r"not\s+intended\s+to\s+trigger[^\n.;]{0,80}(?:mac|mae)|"
        r"negates\s+inference\s+of\s+a\s+material\s+adverse\s+(?:change|effect)|"
        r"không\s+phải\s+là[^\n.;]{0,80}material\s+adverse\s+(?:change|effect)|"
        r"tidak[^\n.;]{0,80}material\s+adverse\s+change"
        r")\b",
        prefix,
        re.IGNORECASE,
    ):
        return True
    return bool(re.search(
        r"\b(?:"
        r"no\s+[\"“]?material\s+adverse\s+effect[\"”]?\s+occurred|"
        r"(?:mac|mae)\s+clause[^\n.;]{0,80}has\s+not\s+been\s+triggered|"
        r"(?:mac|mae)\s+clause[^\n.;]{0,80}(?:was\s+not\s+invoked|not\s+invoked)|"
        r"material\s+adverse\s+change[^\n.;]{0,80}not\s+triggered|"
        r"do\s+not\s+(?:currently\s+)?assess[^\n.;]{0,120}material\s+adverse\s+change|"
        r"does\s+not\s+include\s+any[^\n.;]{0,120}material\s+adverse\s+change(?:\s+trigger)?|"
        r"(?:mac|mae)[- ]?like\s+clause[^\n.;]{0,100}material\s+adverse\s+change(?:\s+trigger)?|"
        r"mac\s+clause[^\n.;]{0,160}(?:is\s+negated|does\s+not\s+by\s+itself\s+signal)"
        r"[^\n.;]{0,80}material\s+adverse\s+change|"
        r"bukan\s+mac|not\s+a\s+mac"
        r")\b",
        context,
        re.IGNORECASE,
    ))


def _is_negated_contingent_mnpi_context(text: str, start: int, end: int) -> bool:
    context = _line_context(text, start, end)
    return bool(re.search(
        r"\bno\s+event\s+has\s+occurred[^\n.;]{0,120}"
        r"(?:expected|reasonably\s+expected)\s+to\s+result\s+in\b",
        context,
        re.IGNORECASE,
    ))


def _is_negated_nonpublic_marker_context(text: str, start: int, end: int) -> bool:
    context = _line_context(text, start, end)
    return bool(re.search(
        r"\b(?:not\s+(?:mnpi|upsi|inside\s+information|price[- ]sensitive\s+information)|"
        r"not[^\n.;]{0,40}price[- ]sensitive\s+information|"
        r"no\s+(?:new\s+)?(?:upsi|mnpi|inside\s+information|price[- ]sensitive\s+information|"
        r"market[- ]sensitive\s+information|unpublished\s+material\s+information)|"
        r"no\s+material\s+non[- ]public\s+information|"
        r"(?:contains?\s+no|do(?:es)?\s+not\s+contain)[^\n.;]{0,120}"
        r"(?:inside\s+information|price[- ]sensitive\s+information|market[- ]sensitive\s+information|"
        r"material\s+non[- ]public\s+information|unpublished\s+material\s+information|"
        r"undisclosed\s+(?:financial\s+metrics|material\s+facts))|"
        r"tidak\s+ada\s+mnpi|no\s+material\s+non[- ]public\s+information\s+remains|"
        r"not[^\n.;]{0,80}\bmnpi|mnpi\s+controls|none\s+are\s+included\s+herein|"
        r"no\s+non[- ]public\s+analyst\s+notes[^\n.;]{0,80}(?:attached|included)|"
        r"no\s+undisclosed\s+material\s+facts\s+remain|"
        r"references?\s+to\s+[\"“]?undisclosed[\"”]?[^\n.;]{0,80}definitional\s+only|"
        r"references?\s+to[^\n.;]{0,80}inside\s+information[^\n.;]{0,80}procedural|"
        r"do\s+not\s+summari[sz]e\s+non[- ]public\s+consultations|"
        r"do\s+not\s+disclose[^\n.;]{0,80}inside\s+information|"
        r"does\s+not\s+rely\s+on\s+non[- ]public\s+data|"
        r"avoid[^\n.;]{0,80}\b(?:inside\s+information|undisclosed\s+assumptions)|"
        r"excludes[^\n.;]{0,80}inside\s+information|"
        r"could\s+be\s+construed\s+as\s+mnpi|"
        r"[\"“]?\bmnpi\b[\"”]?\s+means|"
        r"references?\s+to[^\n.;]{0,100}\bmnpi\b[^\n.;]{0,100}generic\s+risk\s+categor(?:y|ies)|"
        r"references?\s+to[^\n.;]{0,100}\bmnpi\b[^\n.;]{0,120}generic|"
        r"\bmnpi\b[^\n.;]{0,100}generic\s+risk\s+categor(?:y|ies)|"
        r"do\s+not\s+indicate\s+we\s+hold\s+any\s+non[- ]public\s+deal\s+terms|"
        r"mnpi\s+screening[^\n.;]{0,80}does\s+not\s+trigger|"
        r"does\s+not\s+add\s+unpublished\s+price[- ]sensitive\s+information|"
        r"unless\s+upsi\s+is\s+actually\s+present|mnpi\s+markers?:|"
        r"\bmnpi\b[^\n.;]{0,120}training\s+context|"
        r"\bmnpi\s+reminder\b[^\n.;]{0,120}(?:do(?:es)?\s+not|not)\b|"
        r"terms?\s+like[^\n.;]{0,120}\bmnpi\b[^\n.;]{0,120}training\s+context|"
        r"contains\s+only\s+public[^\n.;]{0,120}\bmnpi\b|"
        r"defines?\s+inside\s+information\s+for\s+staff|"
        r"(?:TDnet|DART|KRX|HKEX|ASX)[^\n.;]{0,80}public\s+website\s+labels?|"
        r"disclosed\s+in\s+annual\s+reports|disclosed\s+via\s+public\s+notice)\b",
        context,
        re.IGNORECASE,
    ))


def _is_benign_transaction_codename_context(text: str, start: int, end: int) -> bool:
    context = _line_context(text, start, end)
    matched = text[start:end].casefold()
    if matched == "project code":
        return True
    return bool(re.search(
        r"\b(?:generic\s+form\s+labels?|sample\s+values?|placeholders?\s+only|"
        r"public/stale|public\s+and\s+stale|already[-\s]+announced|"
        r"public\s+(?:reference|archive|baseline))\b",
        context,
        re.IGNORECASE,
    ))


def _is_benign_definitive_agreement_context(text: str, start: int, end: int) -> bool:
    context = _line_context(text, start, end)
    return bool(re.search(
        r"\b(?:not\s+(?:material|upsi|mnpi)|are\s+not\s+upsi|"
        r"routine\s+lease\s+renewal|disclosed\s+via\s+public\s+notice|"
        r"closed\s+in\s+\d{4}|fully\s+announced|"
        r"hkexnews|placeholder|"
        r"does\s+not\s+modify\s+any\s+definitive\s+agreement|"
        r"not\s+a\s+term\s+sheet|"
        r"as\s+disclosed[^\n.;]{0,80}executed\s+on\s+\d{4}|"
        r"as\s+announced[^\n]{0,160}no\s+binding\s+commercial\s+terms|"
        r"publicly\s+announced\s+mou[^\n]{0,180}no\s+binding\s+obligations|"
        r"public\s+mou[^\n.;]{0,160}(?:non[- ]price\s+sensitive|not\s+issuer[- ]level)|"
        r"Sha[’'‘ʻʿ]?ban|"
        r"does\s+not\s+vary\s+any\s+SPA\s+MAC\s+clause|"
        r"not\s+a\s+definitive\s+agreement|"
        r"(?:does\s+not\s+concern|excludes?)[^\n.;]{0,120}definitive\s+agreement|"
        r"no\s+executed[^\n.;]{0,60}term\s+sheet\s+exists|"
        r"no\s+annexes[^\n.;]{0,80}\bSPA\b|"
        r"term\s+sheet\s+sample[^\n.;]{0,120}training[^\n.;]{0,120}public[- ]source|"
        r"not\s+an\s+actual\s+client\s+identifier|"
        r"illustrative\s+case\s+studies|public\s+journals|do\s+not\s+pertain)\b",
        context,
        re.IGNORECASE,
    ))


def _is_special_category_false_positive_context(rule_name: str, text: str, start: int, end: int) -> bool:
    context = _line_context(text, start, end)
    if re.search(r"\b(?:do\s+not\s+include\s+any|no\s+individual\s+profiles?)\b", context, re.IGNORECASE):
        return True
    if rule_name == "racial_ethnic_origin" and re.search(
        r"\b(?:do\s+not\s+(?:collect|process|store|record)[^\n.;]{0,80}(?:race|racial|ethnic|ethnicity)|"
        r"no\s+(?:race|racial|ethnic|ethnicity)[^\n.;]{0,80}(?:data|information|profiles?)|"
        r"race\s+to\s+(?:sign|close|finish)|black[- ]letter\s+law|white\s+paper|"
        r"asian\s+option|not\s+about\s+any\s+person|category\s+label\s+only)\b",
        context,
        re.IGNORECASE,
    ):
        return True
    if rule_name == "genetic_data" and re.search(
        r"\b(?:no\s+genetic\s+data[^\n.;]{0,80}(?:collected|stored|processed)|"
        r"no\s+genetic\s+data[^\n.;]{0,80}(?:kept|held|retained)|"
        r"does\s+not\s+process[^\n.;]{0,120}genetic\s+data|"
        r"synthetic\s+datasets[^\n.;]{0,120}genetic\s+data|"
        r"do\s+not\s+request[^\n.;]{0,140}genetic\s+data|"
        r"genetic\s+algorithms?|software\s+features?|not\s+about\s+any\s+person|"
        r"category\s+label\s+only|does\s+not\s+describe\s+any\s+person|"
        r"genetics?\s+of\s+innovation[^\n.;]{0,80}metaphors?|"
        r"not\s+personal\s+data)\b",
        context,
        re.IGNORECASE,
    ):
        return True
    return False


def _is_identifier_like_large_number_context(text: str, start: int, end: int) -> bool:
    matched = text[start:end].strip()
    digits = _digits_only(matched)
    if digits and set(digits) == {"0"}:
        return True
    line = _line_context(text, start, end)
    line_match_start = max(0, line.find(matched))
    line_match_end = line_match_start + len(matched)
    context = line[max(0, line_match_start - 40): min(len(line), line_match_end + 16)]
    wider_context = line[max(0, line_match_start - 120): min(len(line), line_match_end + 16)]
    if "http" in wider_context.casefold() and "," not in matched:
        return True
    return bool(
        _LARGE_NUMBER_IDENTIFIER_CONTEXT_RE.search(context)
        or _LARGE_NUMBER_IDENTIFIER_CONTEXT_RE.search(wider_context)
        or _URL_PARAM_IDENTIFIER_CONTEXT_RE.search(context)
    )


def _is_identifier_like_financial_amount(text: str, start: int, end: int) -> bool:
    matched = text[start:end].strip()
    if re.fullmatch(r"\d{6,}\s*[KMBT]", matched, re.IGNORECASE):
        return True
    if re.fullmatch(r"\d{1,3}[KMBT]", matched, re.IGNORECASE):
        context = _line_context(text, start, end)
        after = text[end:end + 1]
        return bool(
            after in "-\u2010\u2011\u2012\u2013\u2014\u2015"
            or re.search(
                r"\b(?:Rule\s+10b|10b[-\u2010-\u2015]?5|Phase\s+\d+[a-z]|Trial|"
                r"ticket|log\s+id|sess(?:ion)?|internal\s+payroll|payroll\s+code)\b",
                context,
                re.IGNORECASE,
            )
        )
    return False


def _is_placeholder_identifier_context(text: str, start: int, end: int) -> bool:
    context = _line_context(text, start, end)
    return bool(
        _PLACEHOLDER_IDENTIFIER_CONTEXT_RE.search(context)
        or _VIETNAMESE_PLACEHOLDER_IDENTIFIER_CONTEXT_RE.search(context)
    )


def _is_public_or_benign_amount_context(text: str, start: int, end: int) -> bool:
    context = _line_context(text, start, end)
    return bool(_PUBLIC_OR_BENIGN_AMOUNT_CONTEXT_RE.search(context))


def _is_public_or_benign_percentage_context(text: str, start: int, end: int) -> bool:
    left = max(text.rfind("\n", 0, start), text.rfind(";", 0, start)) + 1
    right_candidates = [
        pos for pos in (text.find("\n", end), text.find(";", end)) if pos >= 0
    ]
    right = min(right_candidates) if right_candidates else len(text)
    context = text[left:right]
    return bool(_PUBLIC_OR_BENIGN_AMOUNT_CONTEXT_RE.search(context))


def _is_educational_mnpi_marker_context(text: str, start: int, end: int) -> bool:
    context = _line_context(text, start, end)
    return bool(re.search(
        r"\b(?:"
        r"training\s+materials?\s+only|policy\s+training\s+examples?|"
        r"training\s+(?:weeks|decks|drills)|tabletop\s+drills|"
        r"general\s+education\s+only|"
        r"definitions?\s+training|generic\s+compliance\s+education|"
        r"hanya\s+sebagai\s+definisi\s+pelatihan|"
        r"e[- ]?learning[^\n.;]{0,120}(?:insider\s+lists?|information\s+barriers?)|"
        r"educational/marketing\s+materials?[^\n.;]{0,180}"
        r"(?:insider[- ]list\s+management|information\s+barriers?|blackout\s+windows)|"
        r"(?:marketing|education|educational)\s+only[^\n.;]{0,120}do\s+not\s+announce|"
        r"(?:information\s+barriers?|insider\s+lists?)[^\n.;]{0,120}generic\s+compliance\s+education|"
        r"references?\s+to[^\n.;]{0,160}(?:insider\s+lists?|blackout\s+windows)[^\n.;]{0,120}"
        r"primarily\s+educational|"
        r"primarily\s+educational[^\n.;]{0,80}not\s+price\s+sensitive|"
        r"(?:information\s+barriers?|insider\s+lists?)[^\n.;]{0,120}only\s+as\s+definitions?\s+training|"
        r"educational\s+and\s+not\s+transaction[- ]related|training\s+rosters?|"
        r"training[^\n.;]{0,120}generic\s+examples?|"
        r"terms?\s+[\"“]?insider\s+list[\"”]?[^\n.;]{0,120}generic|"
        r"insider\s+list[^\n.;]{0,120}generic[^\n.;]{0,80}(?:policy|controls?)|"
        r"does\s+not\s+specify[^\n.;]{0,120}\binsider\s+lists?|"
        r"insider\s+lists?[^\n.;]{0,80}illustrative\s+only|"
        r"public\s+webinar[^\n.;]{0,160}\binsider\s+lists?|"
        r"public\s+webinar[^\n.;]{0,160}generic\s+case\s+studies|"
        r"for\s+educational\s+purposes\s+only|"
        r"not\s+as\s+market[- ]moving\s+events?|educational\s+example\s+only|"
        r"educational\s+note\s+only|educational\s+note[^\n.;]{0,120}purely\s+instructional"
        r")\b",
        context,
        re.IGNORECASE,
    ))


def _is_percent_encoded_fragment(text: str, start: int, end: int) -> bool:
    return end < len(text) - 1 and text[end:end + 2].lower() in {
        "20", "21", "22", "23", "24", "25", "26", "27", "28", "29",
        "2a", "2b", "2c", "2d", "2e", "2f", "3a", "3b", "3c", "3d",
        "3e", "3f", "40",
    }


def _is_spa_day_reference(text: str, start: int, end: int) -> bool:
    if text[start:end].casefold() != "spa":
        return False
    if text[end:end + 4].casefold() in {"-day", " day"}:
        return True
    if re.match(r"[\u2010-\u2015]day\b", text[end:end + 5], re.IGNORECASE):
        return True
    context = _line_context(text, start, end)
    return bool(re.search(
        r"\b(?:wellness|voucher|pantry|conference\s+room|spa\s+day|not\s+the\s+spa|book\s+the\s+spa)\b",
        context,
        re.IGNORECASE,
    ))


def _digits_only(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _ip_version(value: str) -> int | None:
    try:
        return ipaddress.ip_address(value).version
    except ValueError:
        return None


def _clamped_llm_warning_severity(warning: dict[str, Any]) -> str:
    requested = str(warning.get("severity") or "").strip().lower()
    if requested == "low":
        return "low"
    return "medium"


def _structured_reason_for_warning(warning: dict[str, Any]) -> str:
    from junas.advisory.llm_adjudicator.structured_query import STRUCTURED_REASONS

    candidate = str(
        warning.get("structured_reason")
        or warning.get("materiality_reason")
        or ""
    ).strip().lower()
    if candidate in STRUCTURED_REASONS:
        return candidate
    return "ambiguous_unconstrained"


def _category_for_llm_warning(warning: dict[str, Any]) -> str:
    category = str(warning.get("category") or "").strip().upper()
    if category == "PII":
        return "PII"
    return "MNPI"


def _llm_raised_findings_from_warnings(
    *,
    warnings: list[dict[str, Any]],
    jurisdiction: str,
    pii_legal_basis: str,
    mnpi_legal_basis: str,
    idx_start: int,
) -> list[ReviewFinding]:
    out: list[ReviewFinding] = []
    for offset, warning in enumerate(warnings):
        rule_guess = str(warning.get("rule_guess") or "unknown").strip() or "unknown"
        why = str(warning.get("why") or "").strip()
        category = _category_for_llm_warning(warning)
        finding = _new_finding(
            idx=idx_start + offset,
            category=category,
            rule="llm_raised_finding",
            jurisdiction=jurisdiction,
            severity=_clamped_llm_warning_severity(warning),
            matched_text="[LLM_COVERAGE_WARNING]",
            start=0,
            end=0,
            reason=f"LLM coverage audit raised possible {rule_guess}: {why}".strip(),
            legal_basis=pii_legal_basis if category == "PII" else mnpi_legal_basis,
            metadata={
                "origin": "llm",
                "coverage_warning_id": f"coverage_warning:{offset}",
                "llm_rule_guess": rule_guess,
                "llm_confidence": warning.get("confidence"),
                "requested_severity": str(warning.get("severity") or ""),
                "structured_reason": _structured_reason_for_warning(warning),
                "context_window_hash": str(warning.get("context_window_hash") or warning.get("body_hash") or ""),
                "context_window_hash_kind": "body_hash",
                "body_hash": str(warning.get("body_hash") or ""),
                "coverage_warning": dict(warning),
            },
        )
        finding.source = "llm_coverage_audit"
        out.append(finding)
    return out


# Rules whose span "wins" over phone_number when the two overlap on the same bytes.
# These are all primary-identifier detectors: a NRIC or UEN that happens to match the
# loose PHONE_RE alternation is canonically the identifier, not a phone number.
_HIGHER_PRIORITY_THAN_PHONE = frozenset({
    "sg_nric_fin", "sg_uen",
    "my_mykad", "id_nik", "th_national_id", "ph_philsys", "ph_tin", "vn_cccd",
    "hk_hkid", "hk_cr_no", "au_tfn", "au_abn", "au_acn",
    "jp_my_number", "jp_corporate_number", "kr_rrn", "kr_business_registration",
    "in_aadhaar", "in_pan", "in_gstin", "in_voter_id",
    "cn_resident_id", "cn_uscc", "cn_passport",
    "ae_emirates_id", "ae_trade_licence", "ae_passport",
    "sa_national_id", "sa_iqama", "sa_commercial_registration",
    "passport_number", "bank_account", "us_itin", "us_driver_license", "imei",
})
_HIGHER_PRIORITY_THAN_LARGE_NUMBER = _HIGHER_PRIORITY_THAN_PHONE | frozenset({
    "phone_number",
    "financial_percentage", "date_of_birth", "age_reference",
    "ip_address", "mac_address", "cookie_id", "advertising_id", "device_serial_number",
    "sg_postal_address", "medical_record_number", "eu_national_id",
})


_HK_MARKET_KNOWN_DOMAINS = (
    "hkexnews.hk",
    "hkex.com.hk",
    "sfc.hk",
    "hksi.org",
    "aastocks.com",
    "etnet.com.hk",
    "reuters.com",
    "bloomberg.com",
)
_HK_MARKET_KNOWN_TEXT = (
    "hkex",
    "stock exchange of hong kong",
    "securities and futures commission",
    "issuer announcement",
    "inside information announcement",
    "regulatory announcement",
    "press release",
    "investor relations",
)


def _hk_market_known_source(source: Any) -> bool:
    if not isinstance(source, dict):
        return False
    text = " ".join(
        str(source.get(key) or "")
        for key in ("url", "title", "author", "source", "site_name", "text")
    ).casefold()
    return any(domain in text for domain in _HK_MARKET_KNOWN_DOMAINS) or any(
        marker in text for marker in _HK_MARKET_KNOWN_TEXT
    )


def _apply_retrieval_verification(
    findings: list["ReviewFinding"],
    public_evidence: dict[str, Any] | None,
    *,
    jurisdiction: str = "",
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
    jurisdiction_key = (jurisdiction or "").upper()
    hk_available_only = False
    if sources and jurisdiction_key == "HK":
        market_known = [_hk_market_known_source(source) for source in sources]
        if any(market_known):
            verdict = SOURCE_VERIFICATION_PUBLIC_SOURCE_MATCHED
        else:
            verdict = SOURCE_VERIFICATION_AMBIGUOUS
            hk_available_only = True
    elif sources:
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
        if hk_available_only:
            f.metadata = {
                **f.metadata,
                "hk_public_status": "available_but_not_generally_known",
            }


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
    "cyber_incident_pre_disclosure", "pharma_trial_mnpi",
    "financial_services_regulatory_mnpi", "energy_reserves_mnpi",
    "legal_proceeding_mnpi",
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


# items 78 + 99: pseudonymised-but-linkable identifier rules. Escalate medium → high when a
# named_person finding co-occurs anywhere in the same document. The linking-key risk that
# makes GDPR Recital 26 / PDPC Anonymisation Advisory treat these as personal data is
# document-scoped, not span-local — once a named person + an internal ID both appear in
# the same doc, the re-link is trivial.
_PSEUDONYMISED_LINKABLE_RULES = frozenset({
    "employee_id", "customer_account_number", "medical_record_number",
    "internal_session_id", "bank_customer_reference", "insurance_member_id",
})


# items 109/110/111: PII-handling-event rules that require a lookback-25 negation guard.
# These describe data flows / retention triggers / over-collection language; "no cross-border
# transfer is contemplated", "consent has not been withdrawn", "we are not over-collecting"
# should not fire. Parallel to the MNPI-side `_negation_guarded` set in `_mnpi_findings`.
_PII_NEGATION_GUARDED = frozenset({
    "cross_border_transfer_marker",
    "consent_withdrawal_marker",
    "data_minimisation_marker",
    "personal_data_security_safeguards",
    "personal_data_breach_notification",
})


# Special-category PII opt-out. Tenants with high false-positive sensitivity can disable
# individual categories via JUNAS_SPECIAL_CATEGORY_DISABLE=religion,union,political,
# health,biometric,genetic,sexual.
# Default-enabled in strict + audit_grade. Categories are casefolded comma-separated.
_SPECIAL_CATEGORY_RULES = frozenset({
    "religious_belief", "trade_union_membership", "political_opinion",
    "health_condition", "medical_treatment", "biometric_identifier", "genetic_data",
    "sexual_orientation", "sex_life_reference", "racial_ethnic_origin",
})


def _disabled_special_categories() -> frozenset[str]:
    import os
    raw = os.environ.get("JUNAS_SPECIAL_CATEGORY_DISABLE", "")
    if not raw.strip():
        return frozenset()
    disabled: set[str] = set()
    for token in raw.split(","):
        token = token.strip().casefold()
        # map shorthand category names to actual rule names
        if token == "religion":
            disabled.add("religious_belief")
        elif token == "union":
            disabled.add("trade_union_membership")
        elif token == "political":
            disabled.add("political_opinion")
        elif token in {"health", "medical"}:
            disabled.update({"health_condition", "medical_treatment"})
        elif token == "biometric":
            disabled.add("biometric_identifier")
        elif token == "genetic":
            disabled.add("genetic_data")
        elif token in {"sexual", "sex"}:
            disabled.update({"sexual_orientation", "sex_life_reference"})
        elif token == "orientation":
            disabled.add("sexual_orientation")
        elif token in {"race", "racial", "ethnic", "ethnicity"}:
            disabled.add("racial_ethnic_origin")
        elif token in _SPECIAL_CATEGORY_RULES:
            disabled.add(token)
    return frozenset(disabled)


# item 107: minor-data severity resolver. Walks applicable jurisdiction packs and picks the
# strictest cliff that the extracted age falls below. Returns the highest severity tier across
# all packs where age < cliff. Falls back to medium when no jurisdiction matches (e.g., a
# `parental consent` reference without an age digit — the marker alone is medium-severity PII).
def _resolve_minor_severity(
    extracted_age: int | None,
    applicable_juris: list[str],
) -> tuple[str, list[str]]:
    """Return (severity, triggered_juris_codes). `triggered_juris_codes` is the list of
    jurisdictions where extracted_age falls under the cliff — empty when the matcher was a
    parental-consent / minor-lexicon hit with no explicit age (severity stays at high because
    the marker is unambiguous)."""
    if extracted_age is None:
        # Pure marker hit (`parental consent`, `minor`, `kindergarten student`, etc.) — high
        # under every cliff that ships in _MINOR_AGE_CLIFFS, because the absence of an age
        # digit + an explicit minor-context marker is conservatively a minor-data reference.
        return "high", applicable_juris
    triggered: list[str] = []
    for code in applicable_juris:
        cliff = _MINOR_AGE_CLIFFS.get(code)
        if cliff is not None and extracted_age < cliff:
            triggered.append(code)
    if not triggered:
        return "low", []  # age explicitly above all applicable cliffs — adult-data reference
    # Strictest jurisdiction wins severity. Under-13 references are high
    # everywhere; under-16 references are high under IN/SG/UK/AU/HK but medium under EU/CN/US.
    if extracted_age < min(_MINOR_AGE_CLIFFS.get(code, 99) for code in applicable_juris):
        return "high", triggered  # below the strictest cliff in scope → high everywhere
    return "medium", triggered


def _detect_minor_data_references(
    text: str,
    *,
    packs: list[JurisdictionRulePack],
    jurisdiction: str,
    legal_basis: str,
    idx_start: int,
) -> list["ReviewFinding"]:
    """Fire `minor_data_reference` per item 107. Single rule with per-jurisdiction-resolved
    severity. False-positive guards: rejects `18+ years of experience`, `Grade A / Grade 1`
    without school context, `Year N of the contract`."""
    applicable = [pack.code for pack in packs if pack.code in _MINOR_AGE_CLIFFS]
    if not applicable:
        # Synthesised baseline pack outside the cliffs registry — be conservative, use SG cliff
        applicable = ["SG"]

    out: list["ReviewFinding"] = []
    idx = idx_start
    seen_spans: set[tuple[int, int]] = set()
    for m in MINOR_DATA_RE.finditer(text):
        # FP guard A: "for 18+ years of experience" / "18+ years of service"
        trailing = text[m.end():m.end() + 40]
        if _MINOR_FP_TRAILING.match(trailing):
            continue
        # FP guard B: "Grade 1" preceded by Grade/Category/Level/Class — caught by the regex
        # itself for school-context patterns; this catches the broader case.
        leading = text[max(0, m.start() - 12):m.start()]
        if _MINOR_FP_LEADING_GRADE.search(leading) and m.group("grade_us"):
            continue

        # Extract the age digit if any of the age groups matched. If an explicit
        # adult age matched the broad age regex, suppress it immediately instead of
        # treating it like a marker-only minor reference.
        extracted_age: int | None = None
        explicit_age_seen = False
        for group_name in ("age_a", "age_b", "age_c", "age_d"):
            if m.group(group_name):
                explicit_age_seen = True
                try:
                    candidate = int(m.group(group_name))
                except ValueError:
                    continue
                # Sanity-clamp to 0-25 — outside this range it's not a human age in context
                if 0 <= candidate <= 25:
                    extracted_age = candidate
                break

        # Reject "26 years old" / "75 years old" etc. — adult references; not a minor signal
        if explicit_age_seen and (extracted_age is None or extracted_age > 19):
            continue

        # School-grade markers imply minor; estimate age from grade number so per-juris cliff
        # resolution picks the right severity. Approximate mappings:
        #   SG Primary N → age N+6 (P1 ~ 7, P6 ~ 12); Secondary N → age N+12
        #   UK Year N    → age N+4 (Y1 ~ 5, Y13 ~ 17-18)
        #   US Grade N   → age N+5 (G1 ~ 6, G12 ~ 17-18)
        if extracted_age is None:
            if m.group("grade_sg"):
                try:
                    extracted_age = int(m.group("grade_sg")) + 6  # SG primary
                except ValueError:
                    extracted_age = 10
            elif m.group("grade_uk"):
                try:
                    extracted_age = int(m.group("grade_uk")) + 4
                except ValueError:
                    extracted_age = 12
            elif m.group("grade_us"):
                try:
                    extracted_age = int(m.group("grade_us")) + 5
                except ValueError:
                    extracted_age = 11

        severity, triggered_juris = _resolve_minor_severity(extracted_age, applicable)
        if severity == "low":
            continue  # explicit adult-data reference; not surfaced

        span = (m.start(), m.end())
        if span in seen_spans:
            continue
        seen_spans.add(span)

        reason_parts = []
        if extracted_age is not None:
            reason_parts.append(f"explicit age reference ({extracted_age}) detected")
        else:
            reason_parts.append("minor-data marker detected without explicit age")
        if triggered_juris:
            cliff_strs = [
                f"{code} (<{_MINOR_AGE_CLIFFS[code]})" for code in triggered_juris
            ]
            reason_parts.append(
                f"falls under children's-data regime for: {', '.join(cliff_strs)}"
            )
        out.append(
            _new_finding(
                idx=idx,
                category="PII",
                rule="minor_data_reference",
                jurisdiction=jurisdiction,
                severity=severity,
                matched_text=m.group(),
                start=m.start(),
                end=m.end(),
                reason="; ".join(reason_parts),
                legal_basis=legal_basis,
                metadata={"rule_jurisdictions": triggered_juris or applicable},
            )
        )
        idx += 1
    return out


def _detect_special_category_findings(
    text: str,
    *,
    packs: list[JurisdictionRulePack],
    jurisdiction: str,
    legal_basis: str,
    idx_start: int,
) -> list["ReviewFinding"]:
    """Fire special-category PII findings. Each pattern carries built-in context anchors so a strict-profile pass is
    safe. Per-category opt-out via JUNAS_SPECIAL_CATEGORY_DISABLE env var.

    Jurisdiction posture:
      - GDPR Art 9 + PIPA Art 23 + LGPD Art 5(II) + UAE PDPL Art 15 + KSA PDPL Art 6 cover
        all three.
      - APPI Japan ('creed') covers religion + political; union is NOT explicitly enumerated.
      - PIPL China Art 28 covers religion; political is NOT explicitly enumerated.
      - GDPR Art 9 covers health; HIPAA 45 CFR 164.514 and PDPC healthcare guidance anchor
        medical identifiers and treatment narratives.
      - GDPR Art 9 covers genetic data and uniquely identifying biometric data; HIPAA 45 CFR
        164.514 safe harbor enumerates biometric identifiers including finger and voice prints.
      - GDPR Art 9 covers sex life and sexual orientation directly.
      - PDPC SG / DPDPA IN treat these as warranting higher protection but not as a distinct
        statutory class.

    Severity is high under GDPR Art 9 / PIPA Art 23 / LGPD / UAE / KSA / SG higher-standard.
    """
    disabled = _disabled_special_categories()
    out: list["ReviewFinding"] = []
    idx = idx_start
    seen_spans: set[tuple[str, int, int]] = set()

    rules: list[tuple[str, "re.Pattern[str]", str]] = [
        ("religious_belief", RELIGION_RE,
         "Religious-belief reference detected; special-category personal data"),
        ("religious_belief", MULTILINGUAL_RELIGION_RE,
         "Religious-belief reference detected; special-category personal data"),
        ("trade_union_membership", TRADE_UNION_RE,
         "Trade-union membership reference detected; special-category personal data"),
        ("trade_union_membership", MULTILINGUAL_TRADE_UNION_RE,
         "Trade-union membership reference detected; special-category personal data"),
        ("political_opinion", POLITICAL_RE,
         "Political-opinion / party-affiliation reference detected; special-category personal data"),
        ("political_opinion", MULTILINGUAL_POLITICAL_RE,
         "Political-opinion / party-affiliation reference detected; special-category personal data"),
        ("racial_ethnic_origin", RACIAL_ETHNIC_ORIGIN_RE,
         "Racial or ethnic-origin reference detected; special-category personal data"),
        ("health_condition", HEALTH_CONDITION_RE,
         "Health condition / diagnosis reference detected; special-category personal data"),
        ("health_condition", MULTILINGUAL_HEALTH_CONDITION_RE,
         "Health condition / diagnosis reference detected; special-category personal data"),
        ("medical_treatment", MEDICAL_TREATMENT_RE,
         "Medical treatment / medication reference detected; special-category personal data"),
        ("medical_treatment", MULTILINGUAL_MEDICAL_TREATMENT_RE,
         "Medical treatment / medication reference detected; special-category personal data"),
        ("biometric_identifier", BIOMETRIC_IDENTIFIER_RE,
         "Biometric identifier reference detected; special-category personal data"),
        ("biometric_identifier", MULTILINGUAL_BIOMETRIC_RE,
         "Biometric identifier reference detected; special-category personal data"),
        ("genetic_data", GENETIC_DATA_RE,
         "Genetic-data reference detected; special-category personal data"),
        ("genetic_data", MULTILINGUAL_GENETIC_RE,
         "Genetic-data reference detected; special-category personal data"),
        ("sexual_orientation", SEXUAL_ORIENTATION_RE,
         "Sexual-orientation reference detected; special-category personal data"),
        ("sexual_orientation", MULTILINGUAL_SEXUAL_ORIENTATION_RE,
         "Sexual-orientation reference detected; special-category personal data"),
        ("sex_life_reference", SEX_LIFE_RE,
         "Sex-life reference detected; special-category personal data"),
        ("sex_life_reference", MULTILINGUAL_SEX_LIFE_RE,
         "Sex-life reference detected; special-category personal data"),
    ]
    for rule_name, pattern, reason in rules:
        if rule_name in disabled:
            continue
        for m in pattern.finditer(text):
            if rule_name == "biometric_identifier" and m.group().strip().casefold() in {
                "biometric authentication",
                "biometric match",
            }:
                continue
            if _is_special_category_false_positive_context(rule_name, text, m.start(), m.end()):
                continue
            key = (rule_name, m.start(), m.end())
            if key in seen_spans:
                continue
            seen_spans.add(key)
            out.append(
                _new_finding(
                    idx=idx,
                    category="PII",
                    rule=rule_name,
                    jurisdiction=jurisdiction,
                    severity="high",
                    matched_text=m.group(),
                    start=m.start(),
                    end=m.end(),
                    reason=reason,
                    legal_basis=legal_basis,
                )
            )
            idx += 1
    return out


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
    "sg_postal_address", "uk_postal_address", "us_postal_address", "hk_postal_address",
    "au_postal_address", "jp_postal_code", "jp_postal_address", "kr_postal_address", "eu_postal_address",
    # SG / SEA / HK / AU / JP / KR / US / UK local government / company IDs
    "sg_nric_fin", "sg_uen", "passport_number",
    "my_mykad", "id_nik", "th_national_id", "ph_philsys", "ph_tin", "vn_cccd",
    "hk_hkid", "hk_cr_no", "au_tfn", "au_abn", "au_acn",
    "jp_my_number", "jp_corporate_number", "kr_rrn", "kr_business_registration",
    "us_ssn", "us_ein", "us_itin", "us_driver_license", "uk_nin",
    # pseudonymised-but-linkable (items 78 + 99)
    "employee_id", "customer_account_number", "medical_record_number",
    "internal_session_id", "bank_customer_reference", "insurance_member_id",
    # item 33 mini-slice: DOB/age + online/device identifiers.
    "date_of_birth", "age_reference", "ip_address", "mac_address", "imei",
    "cookie_id", "advertising_id", "device_serial_number", "eu_national_id",
    # SG wedge direct matter references
    "sg_insurance_policy_number", "crypto_wallet_address", "sg_tribunal_reference",
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
    document_structure: Any | None = None,
) -> list["ReviewFinding"]:
    """Emit quasi-identifier combination findings.

    strict uses item 70 v2 population-prior scoring when validated jurisdiction tables
    exist. audit_grade keeps the item 101 structural proxy fallback."""
    if review_profile == "strict":
        from junas.review.singling_out import detect_singling_out

        out: list["ReviewFinding"] = []
        idx = idx_start
        for spec in detect_singling_out(
            findings,
            jurisdiction=jurisdiction,
            legal_basis=legal_basis,
            document_structure=document_structure,
        ):
            out.append(
                _new_finding(
                    idx=idx,
                    category="PII",
                    rule="quasi_identifier_combination",
                    jurisdiction=jurisdiction,
                    severity=spec.severity,
                    matched_text=spec.matched_text,
                    start=spec.start_char,
                    end=spec.end_char,
                    reason=spec.reason,
                    legal_basis=legal_basis,
                    metadata=spec.metadata,
                )
            )
            idx += 1
        return out

    # Greedy left-to-right sliding window over quasi-identifier findings sorted by
    # start_char. Emits at most one combination finding per cluster — once a window with
    # ≥3 distinct rules is emitted, the left pointer advances past the cluster to avoid
    # overlapping emissions. audit_grade only; strict outside SG stays span-local.
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
                    metadata={
                        "layer": "quasi_identifier_seed",
                        "singling_out_scope": "char_window",
                    },
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
# numeric trigger — junas surfaces the percentage as advisory only for those jurisdictions
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
_MATERIALITY_ADVISORY_ONLY: frozenset[str] = frozenset(
    {"SG", "HK", "UK", "EU", "MY", "ID", "TH", "PH", "VN", "JP", "KR"}
)

_MATERIALITY_SCALED_RULES: frozenset[str] = frozenset({"financial_amount", "financial_percentage"})


class EntitySizeLookup:
    """Protocol for entity revenue / market-cap lookups (item 73).

    Returns a dict with at least one of `revenue` or `market_cap` in the entity's reporting
    currency. Subclasses may attach `is_asx_300: bool` for AU jurisdiction halving. Implementers
    are responsible for currency normalisation against the matched value's currency — the engine
    treats `revenue`/`market_cap` as already in the same denomination as the finding text.

    Engine auto-loads the operator CSV / JSON lookup only when env configured. Without
    one, financial_amount and financial_percentage findings keep their default severity
    and the engine emits a `materiality_lookup_not_configured` degraded mode rather than
    guess."""

    def lookup(self, entity_id: str, jurisdiction: str) -> dict[str, Any] | None:
        raise NotImplementedError


_ENTITY_SIZE_CSV_ENV = "JUNAS_ENTITY_SIZE_CSV"
_ENTITY_SIZE_JSON_ENV = "JUNAS_ENTITY_SIZE_JSON"
_ENTITY_ALIAS_FIELDS: tuple[str, ...] = (
    "entity_id", "issuer", "issuer_name", "name", "ticker", "stock_code", "counter",
)
_ENTITY_NUMERIC_FIELDS: tuple[str, ...] = ("revenue", "market_cap")


@dataclass(frozen=True)
class _EntitySizeRecord:
    aliases: frozenset[str]
    jurisdiction: str
    info: dict[str, Any]


def _normalize_entity_lookup_key(value: Any) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    if ":" in token:
        token = token.rsplit(":", 1)[-1]
    return re.sub(r"\s+", " ", token).casefold()


def _entity_lookup_jurisdiction_codes(value: str) -> set[str]:
    return {
        code
        for code in (
            normalize_jurisdiction(part, default="")
            for part in str(value or "").split("+")
        )
        if code
    }


def _coerce_entity_size_float(value: Any, *, label: str) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, int | float):
        return float(value)
    raw = str(value).strip().replace(",", "").replace("_", "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{label} must be numeric") from exc


def _coerce_entity_size_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y", "on"}


def _coerce_entity_aliases(raw: dict[str, Any]) -> frozenset[str]:
    aliases: set[str] = set()
    for alias_field in _ENTITY_ALIAS_FIELDS:
        value = raw.get(alias_field)
        values = value if isinstance(value, list | tuple | set) else [value]
        for item in values:
            key = _normalize_entity_lookup_key(item)
            if key:
                aliases.add(key)
    return frozenset(aliases)


def _normalize_entity_size_record(
    raw: dict[str, Any],
    *,
    row_label: str,
    source: str,
) -> _EntitySizeRecord:
    aliases = _coerce_entity_aliases(raw)
    if not aliases:
        raise ValueError(f"{row_label}: missing entity alias column")
    jurisdiction = normalize_jurisdiction(raw.get("jurisdiction"), default="")
    info: dict[str, Any] = {"entity_size_source": source}
    for numeric_field in _ENTITY_NUMERIC_FIELDS:
        parsed = _coerce_entity_size_float(
            raw.get(numeric_field),
            label=f"{row_label}.{numeric_field}",
        )
        if parsed is not None:
            info[numeric_field] = parsed
    if not any(field in info for field in _ENTITY_NUMERIC_FIELDS):
        raise ValueError(f"{row_label}: revenue or market_cap is required")
    if "is_asx_300" in raw:
        info["is_asx_300"] = _coerce_entity_size_bool(raw.get("is_asx_300"))
    return _EntitySizeRecord(aliases=aliases, jurisdiction=jurisdiction, info=info)


def _lookup_entity_size_record(
    records: tuple[_EntitySizeRecord, ...],
    *,
    entity_id: str,
    jurisdiction: str,
) -> dict[str, Any] | None:
    key = _normalize_entity_lookup_key(entity_id)
    if not key:
        return None
    requested = _entity_lookup_jurisdiction_codes(jurisdiction)
    fallback: _EntitySizeRecord | None = None
    for record in records:
        if key not in record.aliases:
            continue
        if not requested or not record.jurisdiction or record.jurisdiction in requested:
            return dict(record.info)
        fallback = fallback or record
    return dict(fallback.info) if fallback else None


class CSVEntitySizeLookup(EntitySizeLookup):
    """Operator-maintained issuer-size lookup loaded from CSV.

    Required columns: one alias column (`entity_id`, `issuer`, `ticker`, etc.) and at
    least one of `revenue` / `market_cap`. Optional: `jurisdiction`, `is_asx_300`.
    """

    def __init__(self, path: str):
        import csv

        self.path = path
        try:
            with open(path, newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                rows = [
                    _normalize_entity_size_record(
                        dict(row),
                        row_label=f"row {index}",
                        source="operator_csv",
                    )
                    for index, row in enumerate(reader, start=2)
                ]
        except OSError as exc:
            raise ValueError(f"{_ENTITY_SIZE_CSV_ENV} is unreadable: {exc}") from exc
        except csv.Error as exc:
            raise ValueError(f"{_ENTITY_SIZE_CSV_ENV} is malformed: {exc}") from exc
        if not rows:
            raise ValueError(f"{_ENTITY_SIZE_CSV_ENV} contains no issuer-size rows")
        self._records = tuple(rows)

    def lookup(self, entity_id: str, jurisdiction: str) -> dict[str, Any] | None:
        return _lookup_entity_size_record(
            self._records,
            entity_id=entity_id,
            jurisdiction=jurisdiction,
        )


class JSONEntitySizeLookup(EntitySizeLookup):
    """Operator-maintained issuer-size lookup loaded from JSON.

    Accepts either a list of row objects, `{"entities": [...]}`, or a mapping of
    entity id -> row object.
    """

    def __init__(self, path: str):
        import json

        self.path = path
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except OSError as exc:
            raise ValueError(f"{_ENTITY_SIZE_JSON_ENV} is unreadable: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"{_ENTITY_SIZE_JSON_ENV} is malformed: {exc}") from exc
        rows = tuple(self._iter_rows(payload))
        if not rows:
            raise ValueError(f"{_ENTITY_SIZE_JSON_ENV} contains no issuer-size rows")
        self._records = tuple(
            _normalize_entity_size_record(
                row,
                row_label=f"row {index}",
                source="operator_json",
            )
            for index, row in enumerate(rows, start=1)
        )

    @staticmethod
    def _iter_rows(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict) and isinstance(payload.get("entities"), list):
            rows = payload["entities"]
        elif isinstance(payload, dict):
            rows = [
                {**value, "entity_id": value.get("entity_id") or key}
                for key, value in payload.items()
                if isinstance(value, dict)
            ]
        else:
            raise ValueError(f"{_ENTITY_SIZE_JSON_ENV} must be a JSON object or array")
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError(f"{_ENTITY_SIZE_JSON_ENV} rows must be objects")
        return [dict(row) for row in rows]

    def lookup(self, entity_id: str, jurisdiction: str) -> dict[str, Any] | None:
        return _lookup_entity_size_record(
            self._records,
            entity_id=entity_id,
            jurisdiction=jurisdiction,
        )


def load_entity_size_lookup_from_env() -> EntitySizeLookup | None:
    import os

    csv_path = os.environ.get(_ENTITY_SIZE_CSV_ENV, "").strip()
    json_path = os.environ.get(_ENTITY_SIZE_JSON_ENV, "").strip()
    if csv_path and json_path:
        raise ValueError(f"set only one of {_ENTITY_SIZE_CSV_ENV} or {_ENTITY_SIZE_JSON_ENV}")
    if csv_path:
        return CSVEntitySizeLookup(csv_path)
    if json_path:
        return JSONEntitySizeLookup(json_path)
    return None


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
        f.metadata = {
            **f.metadata,
            "materiality_base": base,
            "materiality_fraction": fraction,
        }
        if entity_info.get("entity_size_source"):
            f.metadata["entity_size_source"] = entity_info["entity_size_source"]
        if ladder is None:
            # Advisory-only jurisdiction (MAR / SGX / HKEX): annotate reason, leave severity.
            f.reason = (
                f.reason
                + f" — entity-relative {fraction:.2%} "
                "(regulator declines numeric materiality threshold; review required)"
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
# v1 shipped per-juris explicit-date detection. v2 adds an operator-maintained CSV hook
# (`JUNAS_EARNINGS_CALENDAR_CSV`) for deterministic no-network ticker/entity lookups.
# External paid/provider lookup stays out of the local runtime path.

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
_EARNINGS_CALENDAR_ENV = "JUNAS_EARNINGS_CALENDAR_CSV"
_TICKER_CONTEXT_RE = re.compile(
    r"\b(?:ticker|stock\s+code|counter|SGX|HKEX|ASX|LSE|NYSE|NASDAQ)\s*[:#-]?\s*"
    r"(?:(?:SGX|HKEX|ASX|LSE|NYSE|NASDAQ)\s*[:#-]?\s*)?"
    r"(?P<ticker>[A-Z][A-Z0-9.]{0,9})\b"
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

    Implemented with stdlib only to keep `junas-local` torch-ban discipline intact.
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


@dataclass(frozen=True)
class _CalendarMatch:
    jurisdiction: str
    ticker: str
    issuer: str
    period: str
    announcement_date: tuple[int, int, int]
    start: int
    end: int
    matched_text: str


def _normalize_ticker(value: str) -> str:
    token = (value or "").strip().upper()
    if ":" in token:
        token = token.rsplit(":", 1)[-1]
    return re.sub(r"[^A-Z0-9.]", "", token)


def _ticker_contexts(text: str) -> dict[str, tuple[int, int, str]]:
    out: dict[str, tuple[int, int, str]] = {}
    for match in _TICKER_CONTEXT_RE.finditer(text):
        ticker = _normalize_ticker(match.group("ticker"))
        if ticker:
            out.setdefault(ticker, (match.start("ticker"), match.end("ticker"), match.group()))
    return out


def _operator_calendar_matches(
    text: str,
    *,
    applicable_juris: list[str],
    entity_id: str | None,
) -> list[_CalendarMatch]:
    import csv
    import os

    path = os.environ.get(_EARNINGS_CALENDAR_ENV, "").strip()
    if not path:
        return []

    ticker_contexts = _ticker_contexts(text)
    text_casefold = text.casefold()
    entity_key = (entity_id or "").strip().casefold()
    applicable = set(applicable_juris)
    matches: list[_CalendarMatch] = []
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            required = {"jurisdiction", "ticker", "period", "announcement_date"}
            fieldnames = set(reader.fieldnames or [])
            missing = required - fieldnames
            if missing:
                raise ValueError(f"missing columns: {', '.join(sorted(missing))}")
            for row_index, row in enumerate(reader, start=2):
                jurisdiction = normalize_jurisdiction(row.get("jurisdiction"), default="")
                if jurisdiction not in applicable:
                    continue
                period = (row.get("period") or "").strip().casefold()
                if period not in {"interim", "annual"}:
                    raise ValueError(f"row {row_index}: period must be interim or annual")
                announcement_date = _parse_date(row.get("announcement_date") or "")
                if announcement_date is None:
                    raise ValueError(f"row {row_index}: invalid announcement_date")
                ticker = _normalize_ticker(row.get("ticker") or "")
                issuer = (row.get("issuer") or "").strip()
                ticker_hit = ticker_contexts.get(ticker) if ticker else None
                issuer_hit = bool(issuer and issuer.casefold() in text_casefold)
                entity_hit = bool(entity_key and entity_key in {ticker.casefold(), issuer.casefold()})
                if not ticker_hit and not issuer_hit and not entity_hit:
                    continue
                if ticker_hit:
                    start, end, matched_text = ticker_hit
                else:
                    needle = issuer if issuer_hit else (issuer or ticker)
                    start = text_casefold.find(needle.casefold()) if needle else 0
                    if start < 0:
                        start = 0
                    end = start + len(needle)
                    matched_text = needle
                matches.append(
                    _CalendarMatch(
                        jurisdiction=jurisdiction,
                        ticker=ticker,
                        issuer=issuer,
                        period=period,
                        announcement_date=announcement_date,
                        start=start,
                        end=end,
                        matched_text=matched_text,
                    )
                )
    except OSError as exc:
        raise ValueError(f"{_EARNINGS_CALENDAR_ENV} is unreadable: {exc}") from exc
    except csv.Error as exc:
        raise ValueError(f"{_EARNINGS_CALENDAR_ENV} is malformed: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"{_EARNINGS_CALENDAR_ENV} is invalid: {exc}") from exc
    return matches


def _detect_blackout_period_references(
    text: str,
    *,
    packs: list[JurisdictionRulePack],
    jurisdiction: str,
    legal_basis: str,
    idx_start: int,
    entity_id: str | None = None,
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
                    metadata={
                        "rule_jurisdictions": [window_owner],
                        "blackout_window_owner": window_owner,
                        "blackout_window_days": applicable_window,
                        "period": period,
                        "document_date": doc_d.isoformat(),
                        "earnings_date": ed.isoformat(),
                        "earnings_calendar_source": "explicit_document_text",
                    },
                )
            )
            idx += 1
    seen_calendar: set[tuple[str, str, tuple[int, int, int], str]] = set()
    for calendar_match in _operator_calendar_matches(
        text,
        applicable_juris=applicable_juris,
        entity_id=entity_id,
    ):
        ed = _dt.date(*calendar_match.announcement_date)
        delta = (ed - doc_d).days
        if delta < 0:
            continue
        window = _BLACKOUT_WINDOW_DAYS[calendar_match.jurisdiction][calendar_match.period]
        if delta > window:
            continue
        key = (
            calendar_match.jurisdiction,
            calendar_match.ticker,
            calendar_match.announcement_date,
            calendar_match.period,
        )
        if key in seen_calendar:
            continue
        seen_calendar.add(key)
        out.append(
            _new_finding(
                idx=idx,
                category="MNPI",
                rule="blackout_period_reference",
                jurisdiction=jurisdiction,
                severity="medium",
                matched_text=calendar_match.matched_text,
                start=calendar_match.start,
                end=calendar_match.end,
                reason=(
                    f"Document dated {doc_d.isoformat()}; operator earnings calendar has "
                    f"{calendar_match.period} results announcement on {ed.isoformat()} "
                    f"within {calendar_match.jurisdiction} {window}-day blackout window "
                    f"(delta={delta} days)"
                ),
                legal_basis=legal_basis,
                metadata={
                    "rule_jurisdictions": [calendar_match.jurisdiction],
                    "blackout_window_owner": calendar_match.jurisdiction,
                    "blackout_window_days": window,
                    "period": calendar_match.period,
                    "document_date": doc_d.isoformat(),
                    "earnings_date": ed.isoformat(),
                    "earnings_calendar_source": "operator_csv",
                    "ticker": calendar_match.ticker,
                    "issuer": calendar_match.issuer,
                },
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


def _suppress_redundant_numeric_findings(text: str, findings: list["ReviewFinding"]) -> list["ReviewFinding"]:
    """Drop broad numeric MNPI findings already owned by stronger identifier/amount rules."""
    spans_to_beat_large: list[tuple[int, int]] = [
        (f.start_char, f.end_char)
        for f in findings
        if f.rule in _HIGHER_PRIORITY_THAN_LARGE_NUMBER
    ]
    kept: list["ReviewFinding"] = []
    for f in findings:
        if f.rule == "large_number":
            if any(lo <= f.start_char and f.end_char <= hi for lo, hi in spans_to_beat_large):
                continue
            if _is_identifier_like_large_number_context(text, f.start_char, f.end_char):
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


def _rule_jurisdictions_for_finding(
    finding: "ReviewFinding",
    packs: list[JurisdictionRulePack],
) -> list[str]:
    pack_codes = [pack.code for pack in packs]
    pack_set = set(pack_codes)
    raw = finding.metadata.get("rule_jurisdictions")
    if isinstance(raw, str):
        codes = [normalize_jurisdiction(raw, default="") or raw.upper()]
    elif isinstance(raw, list):
        codes = [
            normalize_jurisdiction(str(item), default="") or str(item).upper()
            for item in raw
            if str(item).strip()
        ]
    else:
        codes = []
    filtered = [code for code in codes if code in pack_set]
    if filtered:
        return list(dict.fromkeys(filtered))
    if finding.rule == "selective_disclosure_risk" and "US" in pack_set:
        return ["US"]
    prefix = finding.rule.split("_", 1)[0].upper()
    if prefix in pack_set:
        return [prefix]
    return pack_codes


def _annotate_jurisdiction_attribution(
    findings: list["ReviewFinding"],
    *,
    packs: list[JurisdictionRulePack],
    source_jurisdiction: str,
    destination_jurisdiction: str,
) -> None:
    considered = [pack.code for pack in packs]
    source_code = normalize_jurisdiction(source_jurisdiction, default="SG")
    destination_code = normalize_jurisdiction(destination_jurisdiction, default="SG")
    for finding in findings:
        rule_juris = _rule_jurisdictions_for_finding(finding, packs)
        finding.metadata = {
            **finding.metadata,
            "jurisdictions_considered": considered,
            "rule_jurisdictions": rule_juris,
            "source_jurisdiction": source_code,
            "destination_jurisdiction": destination_code,
            "source_juris_finding": source_code in rule_juris,
            "destination_juris_finding": destination_code in rule_juris,
            "jurisdiction_policy": "strictest_wins",
        }


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
        # item 73: entity revenue / market-cap source. env providers are operator-driven;
        # without one, financial_amount / financial_percentage findings keep their default
        # severity and emit a materiality_lookup_not_configured degraded mode.
        self.entity_size_lookup = entity_size_lookup or load_entity_size_lookup_from_env()
        self.pii_pre_named_registry = self._build_pii_pre_named_registry()
        self.pii_post_named_registry = self._build_pii_post_named_registry()

    def _build_pii_pre_named_registry(self) -> DetectorRegistry:
        registry = DetectorRegistry()
        registry.register(
            name="core_identifier_fields",
            family="pii",
            detect=lambda ctx, idx: detect_core_identifier_findings(
                ctx,
                idx,
                _new_finding,
                is_non_attributive_identifier_context=_is_non_attributive_identifier_context,
                is_negated_mac_address_context=_is_negated_mac_address_context,
            ),
        )
        registry.register(
            name="address_signals",
            family="pii",
            detect=lambda ctx, idx: detect_address_findings(ctx, idx, _new_finding),
        )
        registry.register(
            name="us_driver_license",
            family="pii",
            detect=lambda ctx, idx: detect_us_driver_license_findings(ctx, idx, _new_finding),
        )
        registry.register(
            name="sg_wedge_remainder",
            family="pii",
            detect=lambda ctx, idx: detect_sg_wedge_remainder_findings(ctx, idx, _new_finding),
        )
        return registry

    def _build_pii_post_named_registry(self) -> DetectorRegistry:
        registry = DetectorRegistry()
        registry.register(
            name="semantic_pii_fallback",
            family="pii",
            detect=lambda ctx, idx: detect_semantic_pii_fallback_findings(ctx, idx, _new_finding),
        )
        registry.register(
            name="special_category_pii",
            family="pii",
            detect=lambda ctx, idx: _detect_special_category_findings(
                text=ctx.text,
                packs=list(ctx.packs),
                jurisdiction=ctx.jurisdiction,
                legal_basis=ctx.legal_basis,
                idx_start=idx,
            ),
        )
        registry.register(
            name="minor_data_reference",
            family="pii",
            detect=lambda ctx, idx: _detect_minor_data_references(
                text=ctx.text,
                packs=list(ctx.packs),
                jurisdiction=ctx.jurisdiction,
                legal_basis=ctx.legal_basis,
                idx_start=idx,
            ),
        )
        return registry

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
                ("bank_account", BANK_ACCOUNT_ENDING_RE, "high", "Bank/account-like financial identifier"),
                # item 99: pseudonymised-but-linkable identifiers. medium standalone; amplified
                # to high when a named_person finding co-occurs anywhere in the document.
                ("employee_id", EMPLOYEE_ID_RE, "medium",
                 "Employee identifier — pseudonymised-but-linkable personal data"),
                ("customer_account_number", CUSTOMER_ACCOUNT_RE, "medium",
                 "Customer account / member identifier — pseudonymised-but-linkable personal data"),
                ("medical_record_number", MEDICAL_RECORD_RE, "high",
                 "Medical record / patient identifier — special-category personal data"),
                ("internal_session_id", INTERNAL_SESSION_ID_RE, "medium",
                 "Internal session / user token — pseudonymised-but-linkable personal data"),
                ("bank_customer_reference", BANK_CUSTOMER_REFERENCE_RE, "medium",
                 "Bank customer reference — pseudonymised-but-linkable personal data"),
                ("insurance_member_id", INSURANCE_MEMBER_ID_RE, "medium",
                 "Insurance member identifier — pseudonymised-but-linkable personal data"),
                # items 109/110/111: PII-handling-event markers. medium standalone; negation
                # guard via `_PII_NEGATION_GUARDED` lookback-25.
                ("cross_border_transfer_marker", CROSS_BORDER_TRANSFER_RE, "medium",
                 "Cross-border personal-data transfer marker"),
                ("consent_withdrawal_marker", CONSENT_WITHDRAWAL_RE, "medium",
                 "Consent-withdrawal / data-subject-rights marker"),
                ("data_minimisation_marker", DATA_MINIMISATION_RE, "medium",
                 "Data-minimisation / over-collection marker"),
                ("personal_data_security_safeguards", PERSONAL_DATA_SECURITY_SAFEGUARDS_RE, "medium",
                 "Personal-data security-safeguards marker"),
                ("personal_data_breach_notification", PERSONAL_DATA_BREACH_NOTIFICATION_RE, "medium",
                 "Personal-data breach / notification marker"),
            ]
        )

        idx = 0
        for rule, pattern, severity, reason in patterns:
            for match in pattern.finditer(text):
                if match.lastindex:
                    start, end = next(
                        (
                            match.span(group_idx)
                            for group_idx in range(1, match.lastindex + 1)
                            if match.group(group_idx)
                        ),
                        match.span(),
                    )
                else:
                    start, end = match.span()
                if end <= start:
                    continue
                if rule == "phone_number":
                    start, end = _trim_phone_span(text, start, end)
                    if end <= start:
                        continue
                if rule in _PII_NEGATION_GUARDED and _is_negated_context(text, start):
                    continue
                if (
                    rule == "consent_withdrawal_marker"
                    and _is_closed_or_historical_privacy_request_context(text, start, end)
                ):
                    continue
                if rule == "sg_nric_fin" and _is_placeholder_identifier_context(text, start, end):
                    continue
                if rule == "bank_account":
                    digits = _digits_only(text[start:end])
                    if digits and set(digits) == {"0"}:
                        continue
                    if _is_placeholder_identifier_context(text, start, end):
                        continue
                    if "X" in text[start:end].upper() and _is_placeholder_identifier_context(text, start, end):
                        continue
                if rule == "customer_account_number" and _is_placeholder_identifier_context(text, start, end):
                    continue
                if rule == "employee_id":
                    digits = _digits_only(text[start:end])
                    if digits and set(digits) == {"0"}:
                        continue
                    if re.search(r"\baudit\s+hash\b", _line_context(text, start, end), re.IGNORECASE):
                        continue
                if rule == "email_address" and (
                    _is_functional_contact_context(text, start, end)
                    or _is_obfuscated_email_fragment_context(text, start, end)
                ):
                    continue
                if rule == "passport_number" and _is_placeholder_passport_context(text, start, end):
                    continue
                if rule == "phone_number" and _is_public_or_generic_phone_context(text, start, end):
                    continue
                if rule == "phone_number" and _is_non_phone_numeric_context(text, start, end):
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
                    digits = _digits_only(text[start:end])
                    if digits and set(digits) == {"0"}:
                        continue
                    if not recognizer.is_valid(text[start:end]):
                        continue
                    if _is_placeholder_identifier_context(text, start, end):
                        continue
                    if recognizer.rule_name == "ph_tin" and _is_ph_tin_non_tax_context(text, start, end):
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

        detector_context = DetectorContext(
            text=text,
            packs=tuple(packs),
            jurisdiction=jurisdiction,
            legal_basis=legal_basis,
            document_type=document_type,
            defined_terms=frozenset(defined),
        )
        findings.extend(self.pii_pre_named_registry.run(detector_context, idx_start=len(findings)))

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

        findings.extend(self.pii_post_named_registry.run(detector_context, idx_start=len(findings)))

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
            if _MATERIAL_EVENT_NEGATED_CONTEXT_RE.search(context):
                continue
            if (
                _MATERIAL_EVENT_PUBLIC_CONTEXT_RE.search(context)
                and not NONPUBLIC_RE.search(context)
                and "not generally available" not in context.casefold()
            ):
                continue
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
            (CONTRACT_UNIT_PRICE_RE, "contract_unit_price", "medium",
             "Contract unit price / per-unit economics may be commercially sensitive MNPI"),
            (CONTRACT_DISCOUNT_RE, "contract_discount_rate", "medium",
             "Contract discount or rebate rate may be commercially sensitive MNPI"),
            (VOLUME_COMMITMENT_RE, "volume_commitment", "medium",
             "Contract volume commitment may be commercially sensitive MNPI"),
            (ROYALTY_RATE_RE, "royalty_rate", "medium",
             "Royalty rate may be commercially sensitive MNPI"),
            (TOTAL_CONTRACT_VALUE_RE, "total_contract_value", "medium",
             "Total contract value may be commercially sensitive MNPI"),
        ]:
            effective_severity = MNPI_DOC_TYPE_SEVERITY_OVERRIDES.get((rule, doc_type_key), severity)
            for match in pattern.finditer(text):
                if rule in suppressible_rules and is_defined_term(match.group(), defined):
                    continue
                if rule == "nonpublic_marker" and _is_negated_nonpublic_marker_context(
                    text, match.start(), match.end()
                ):
                    continue
                if rule == "transaction_codename" and _is_benign_transaction_codename_context(
                    text, match.start(), match.end()
                ):
                    continue
                if rule == "definitive_agreement" and _is_benign_definitive_agreement_context(
                    text, match.start(), match.end()
                ):
                    continue
                if rule == "definitive_agreement" and _is_spa_day_reference(
                    text, match.start(), match.end()
                ):
                    continue
                # narrow negation guard for MAC/MAE-style rules. catches the most common
                # "no MAC clause concerns" / "not subject to MAC clause" patterns. doesn't
                # try to be a general NLP solver — that's the audit_grade LLM tier's job.
                if rule == "material_adverse_change" and _is_negated_material_adverse_change_context(
                    text, match.start(), match.end()
                ):
                    continue
                if rule == "financial_amount" and _is_identifier_like_financial_amount(
                    text, match.start(), match.end()
                ):
                    continue
                if rule == "financial_amount" and _is_public_or_benign_amount_context(
                    text, match.start(), match.end()
                ):
                    continue
                if rule == "financial_percentage" and _is_percent_encoded_fragment(
                    text, match.start(), match.end()
                ):
                    continue
                if rule == "financial_percentage" and _is_public_or_benign_percentage_context(
                    text, match.start(), match.end()
                ):
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
            (PHARMA_TRIAL_MNPI_RE, "pharma_trial_mnpi",
             "Pharma clinical-trial / regulatory marker; amplifies when adjacent to MNPI substrate"),
            (FINANCIAL_SERVICES_REGULATORY_MNPI_RE, "financial_services_regulatory_mnpi",
             "Financial-services regulatory-capital / enforcement marker; amplifies when adjacent to MNPI substrate"),
            (ENERGY_RESERVES_MNPI_RE, "energy_reserves_mnpi",
             "Energy reserve / production-guidance marker; amplifies when adjacent to MNPI substrate"),
            (LEGAL_PROCEEDING_MNPI_RE, "legal_proceeding_mnpi",
             "Legal proceeding / settlement marker; amplifies when adjacent to MNPI substrate"),
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
            "cyber_incident_pre_disclosure", "pharma_trial_mnpi",
            "financial_services_regulatory_mnpi", "energy_reserves_mnpi",
            "legal_proceeding_mnpi",
        }
        for pattern, rule, reason in post_pass_rules:
            for match in pattern.finditer(text):
                if rule in _negation_guarded and _is_negated_context(text, match.start()):
                    continue
                if rule == "contingent_mnpi_language" and _is_negated_contingent_mnpi_context(
                    text, match.start(), match.end()
                ):
                    continue
                if rule in {"insider_list_marker", "information_barrier_marker"} and (
                    _is_educational_mnpi_marker_context(text, match.start(), match.end())
                ):
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
            result = self.public_evidence_retriever.retrieve(text=text, entity_id=entity_id, lexicon=None)
        except Exception as exc:
            raise ReviewLayerError("public_evidence", f"public-evidence retrieval failed: {exc}") from exc
        if isinstance(result, dict) and result.get("status") == "error":
            detail = str(result.get("detail") or result.get("review_recommendation") or "provider returned error")
            raise ReviewLayerError("public_evidence", f"public-evidence retrieval failed: {detail}")
        if isinstance(result, dict) and result.get("status") == "skipped":
            detail = str(result.get("detail") or "")
            if "key" in detail.lower() and "not configured" in detail.lower():
                raise ReviewLayerError("public_evidence", f"public-evidence retrieval failed: {detail}")
        return result

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
            result = self.llm_adjudicator.adjudicate(
                text=text,
                current_classification=overall_risk.value,
                public_evidence=public_evidence,
                findings=findings,
                entity_id=entity_id,
            )
        except TypeError:
            # backwards-compat shim: older adjudicators reject the new kwargs.
            try:
                result = self.llm_adjudicator.adjudicate(
                    text=text,
                    current_classification=overall_risk.value,
                    public_evidence=public_evidence,
                )
            except Exception as retry_exc:
                raise ReviewLayerError("llm_adjudicator", f"LLM adjudication failed: {retry_exc}") from retry_exc
        except Exception as exc:
            raise ReviewLayerError("llm_adjudicator", f"LLM adjudication failed: {exc}") from exc
        if isinstance(result, dict) and result.get("status") == "error":
            detail = str(result.get("review_recommendation") or result.get("detail") or "provider returned error")
            raise ReviewLayerError("llm_adjudicator", f"LLM adjudication failed: {detail}")
        return result

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
        document_structure: Any | None = None,
    ) -> ReviewResult:
        if review_profile not in VALID_REVIEW_PROFILES:
            raise ValueError(
                f"review_profile must be one of {sorted(VALID_REVIEW_PROFILES)}; got {review_profile!r}"
            )
        packs = resolve_rule_packs(source_jurisdiction, destination_jurisdiction)
        privacy_ledger: list[dict[str, Any]] = []
        defined_terms = extract_defined_terms(text)
        # audit_grade-only LLM pre-pass over the preamble to catch defined terms the regex
        # misses. cached by document hash; raw doc body is not sent (the helper sees only
        # the first PREAMBLE_CHAR_CAP characters).
        if review_profile == "audit_grade" and self.llm_defined_term_extractor is not None:
            from junas.review.llm_defined_terms import extract_with_cache

            try:
                defined_terms = defined_terms | extract_with_cache(
                    text=text,
                    extractor=self.llm_defined_term_extractor,
                    fail_closed=True,
                )
                privacy_ledger.extend(_drain_privacy_ledger_events(self.llm_defined_term_extractor))
            except Exception as exc:
                _drain_privacy_ledger_events(self.llm_defined_term_extractor)
                raise ReviewLayerError("llm_defined_terms", f"LLM defined-term extraction failed: {exc}") from exc
        # cross-doc defined-term inheritance: merge prior session-scoped terms into the current
        # document's set, then persist the current document's terms back to the session store so
        # the next related-doc review inherits them too. SPA defines `the "Purchaser"` once;
        # a paired disclosure schedule reviewed in the same session inherits that suppression.
        if session_id:
            from junas.review.session_store import add_defined_terms, load_defined_terms

            try:
                inherited = load_defined_terms(session_id, tenant_id=tenant_id)
                defined_terms = defined_terms | inherited
                if defined_terms - inherited:
                    add_defined_terms(session_id, defined_terms - inherited, tenant_id=tenant_id)
            except Exception as exc:
                raise ReviewLayerError("session_defined_terms", f"session defined-term store failed: {exc}") from exc
        # item 55: matter-scoped inheritance sits above session-scope. Sessions belong to a matter;
        # defined terms accumulate at matter level and inherit into every session within that matter.
        # Closes the 30+ document M&A case where session-scope loses inheritance once the session
        # rotates. matter terms persist across reviewers / weeks / sessions under the same matter_id.
        if matter_id:
            from junas.review.matter_store import (
                add_defined_terms as add_matter_terms,
            )
            from junas.review.matter_store import (
                load_defined_terms as load_matter_terms,
            )

            try:
                matter_inherited = load_matter_terms(matter_id, tenant_id=tenant_id)
                defined_terms = defined_terms | matter_inherited
                if defined_terms - matter_inherited:
                    add_matter_terms(matter_id, defined_terms - matter_inherited, tenant_id=tenant_id)
            except Exception as exc:
                raise ReviewLayerError("matter_defined_terms", f"matter defined-term store failed: {exc}") from exc
        document_structure = document_structure or parse_document_structure(text)
        findings = self._pii_findings(text, packs, document_type, defined_terms) + self._mnpi_findings(
            text, packs, defined_terms, document_type
        )
        findings.extend(
            detect_personal_attribute_inferences(
                text,
                jurisdiction=_pack_scope(packs),
                legal_basis=_legal_basis(packs, "pii_rules"),
                idx_start=len(findings),
                document_structure=document_structure,
                new_finding=_new_finding,
            )
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
        degraded_modes.extend(semantic_pii_degraded_modes())

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
                entity_id=entity_id,
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
                document_structure=document_structure,
            )
        )
        findings = _suppress_redundant_numeric_findings(text, findings)
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
        _apply_retrieval_verification(findings, public_evidence, jurisdiction=jurisdiction_label)
        for spec in detect_conjunctive_mnpi(
            text=text,
            findings=findings,
            jurisdiction=jurisdiction_label,
            legal_basis=mnpi_legal_basis,
            entity_id=entity_id,
        ):
            findings.append(
                _new_finding(
                    idx=len(findings),
                    category="MNPI",
                    rule="conjunctive_mnpi",
                    jurisdiction=jurisdiction_label,
                    severity="medium",
                    matched_text=spec.matched_text,
                    start=spec.start_char,
                    end=spec.end_char,
                    reason=spec.reason,
                    legal_basis=mnpi_legal_basis,
                    source_verification=spec.source_verification,
                    metadata=spec.metadata,
                )
            )
        _apply_retrieval_verification(findings, public_evidence, jurisdiction=jurisdiction_label)
        pii_score = self._score(findings, "PII")
        mnpi_score = self._score(findings, "MNPI")
        document_score = max(pii_score, mnpi_score)
        overall_risk = _risk_from_score(document_score)
        privacy_ledger.extend(list((public_evidence or {}).get("privacy_ledger", [])))
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

        # inverse-audit "what did we miss?" — audit_grade only. warnings still surface
        # as coverage_warning events; LLM warnings are also promoted to capped, reviewer-
        # adjudicated findings so missed recalls are visible in the normal decision path.
        coverage_warnings: list[dict[str, Any]] = driver_license_coverage_warnings(
            text,
            packs=packs,
            review_profile=review_profile,
        )
        llm_coverage_warnings: list[dict[str, Any]] = []
        if engage_llm_tier and self.llm_coverage_auditor is not None:
            from junas.review.llm_coverage_audit import run_coverage_audit

            try:
                llm_coverage_warnings = run_coverage_audit(
                    text=text,
                    findings=findings,
                    document_type=document_type,
                    auditor=self.llm_coverage_auditor,
                    fail_closed=True,
                )
                coverage_warnings.extend(llm_coverage_warnings)
                privacy_ledger.extend(_drain_privacy_ledger_events(self.llm_coverage_auditor))
            except Exception as exc:
                _drain_privacy_ledger_events(self.llm_coverage_auditor)
                raise ReviewLayerError("llm_coverage_audit", f"LLM coverage audit failed: {exc}") from exc
        if llm_coverage_warnings:
            findings.extend(
                _llm_raised_findings_from_warnings(
                    warnings=llm_coverage_warnings,
                    jurisdiction=jurisdiction_label,
                    pii_legal_basis=pii_legal_basis,
                    mnpi_legal_basis=mnpi_legal_basis,
                    idx_start=len(findings),
                )
            )
            pii_score = self._score(findings, "PII")
            mnpi_score = self._score(findings, "MNPI")
            document_score = max(pii_score, mnpi_score)
            overall_risk = _risk_from_score(document_score)
        _annotate_jurisdiction_attribution(
            findings,
            packs=packs,
            source_jurisdiction=source_jurisdiction,
            destination_jurisdiction=destination_jurisdiction,
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
