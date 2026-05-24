from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from kaypoh.backend.schemas import Classification
from kaypoh.review.citations import mnpi_rationale, pii_rationale
from kaypoh.review.defined_terms import extract_defined_terms, is_defined_term
from kaypoh.review.entity_linker import canonical_person, strip_honorific
from kaypoh.review.jurisdictions import JurisdictionRulePack, resolve_rule_packs
from kaypoh.workflow.privacy_guard import EMAIL_RE, LONG_NUMBER_RE, MONEY_RE, PERCENT_RE, PHONE_RE


SG_NRIC_RE = re.compile(r"\b[STFGM]\d{7}[A-Z]\b", re.IGNORECASE)
SG_UEN_RE = re.compile(r"\b(?:\d{8,9}[A-Z]|T\d{2}[A-Z]{2}\d{4}[A-Z])\b")  # ACRA UEN: legacy 8-9 digit + check letter; new T-format
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
MAC_CLAUSE_RE = re.compile(
    r"\b(?:material\s+adverse\s+change|material\s+adverse\s+effect|MAC\s+clause|MAE\s+clause|MAC|MAE)\b",
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
    r"internal only|restricted|do not distribute|before announcement|pre-announcement|"
    r"quiet period|material non-public information|mnpi)\b",
    re.IGNORECASE,
)
PUBLIC_RE = re.compile(r"\b(publicly announced|press release|filed|disclosed|published|reported)\b", re.IGNORECASE)
NAME_RE = re.compile(r"\b(?:Mr|Ms|Mrs|Dr)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b")


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
    )


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
    ):
        self.public_evidence_retriever = public_evidence_retriever
        self.llm_adjudicator = llm_adjudicator

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
            ]
        )

        idx = 0
        for rule, pattern, severity, reason in patterns:
            for match in pattern.finditer(text):
                start, end = match.span(1) if match.lastindex else match.span()
                if end <= start:
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
            severity = "medium"
            reason = "Material corporate or market event language"
            if NONPUBLIC_RE.search(context):
                severity = "high"
                reason = "Material event appears tied to non-public or restricted context"
            elif PUBLIC_RE.search(context):
                severity = "low"
                reason = "Material event appears public, but source should be verified"

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
        return findings

    def _score(self, findings: list[ReviewFinding], category: str) -> float:
        matches = [finding.score for finding in findings if finding.category == category]
        if not matches:
            return 0.0
        return min(100.0, max(matches) + max(0, len(matches) - 1) * 3.0)

    def _suggestions(self, findings: list[ReviewFinding], include_suggestions: bool) -> list[ReviewSuggestion]:
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
                )
            elif finding.severity == "high":
                action = "remove_or_hold"
                replacement = "[REMOVE UNTIL PUBLICLY DISCLOSED OR APPROVED]"
                rationale = mnpi_rationale(
                    rule=finding.rule,
                    jurisdiction=finding.jurisdiction,
                    severity=finding.severity,
                    matched_text=finding.matched_text,
                )
            else:
                action = "verify_or_rewrite"
                replacement = "[CITE PUBLIC SOURCE OR GENERALISE CLAIM]"
                rationale = mnpi_rationale(
                    rule=finding.rule,
                    jurisdiction=finding.jurisdiction,
                    severity=finding.severity,
                    matched_text=finding.matched_text,
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
        if self.public_evidence_retriever is None and self.llm_adjudicator is None:
            return False
        return LLM_TIER_MNPI_LOWER <= mnpi_score < LLM_TIER_MNPI_UPPER

    def _maybe_public_evidence(
        self, *, text: str, entity_id: str | None, mnpi_score: float, engage: bool
    ) -> dict[str, Any] | None:
        if not engage:
            return None
        if mnpi_score <= 0 or self.public_evidence_retriever is None:
            return None
        return self.public_evidence_retriever.retrieve(text=text, entity_id=entity_id, lexicon=None)

    def _maybe_llm_adjudication(
        self,
        *,
        text: str,
        overall_risk: Classification,
        public_evidence: dict[str, Any] | None,
        engage: bool,
    ) -> dict[str, Any] | None:
        if not engage:
            return None
        if self.llm_adjudicator is None or overall_risk == Classification.SAFE:
            return None
        return self.llm_adjudicator.adjudicate(
            text=text,
            current_classification=overall_risk.value,
            public_evidence=public_evidence,
        )

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
        review_profile: str = "strict",
    ) -> ReviewResult:
        if review_profile not in VALID_REVIEW_PROFILES:
            raise ValueError(
                f"review_profile must be one of {sorted(VALID_REVIEW_PROFILES)}; got {review_profile!r}"
            )
        packs = resolve_rule_packs(source_jurisdiction, destination_jurisdiction)
        defined_terms = extract_defined_terms(text)
        # cross-doc defined-term inheritance: merge prior session-scoped terms into the current
        # document's set, then persist the current document's terms back to the session store so
        # the next related-doc review inherits them too. SPA defines `the "Purchaser"` once;
        # a paired disclosure schedule reviewed in the same session inherits that suppression.
        if session_id:
            from kaypoh.review.session_store import add_defined_terms, load_defined_terms

            inherited = load_defined_terms(session_id)
            defined_terms = defined_terms | inherited
            if defined_terms - inherited:
                add_defined_terms(session_id, defined_terms - inherited)
        findings = self._pii_findings(text, packs, document_type, defined_terms) + self._mnpi_findings(
            text, packs, defined_terms, document_type
        )
        pii_score = self._score(findings, "PII")
        mnpi_score = self._score(findings, "MNPI")
        document_score = max(pii_score, mnpi_score)
        overall_risk = _risk_from_score(document_score)

        engage_llm_tier = self._llm_tier_engaged(review_profile=review_profile, mnpi_score=mnpi_score)
        public_evidence = self._maybe_public_evidence(
            text=text, entity_id=entity_id, mnpi_score=mnpi_score, engage=engage_llm_tier
        )
        privacy_ledger = list((public_evidence or {}).get("privacy_ledger", []))
        llm_adjudication = self._maybe_llm_adjudication(
            text=text,
            overall_risk=overall_risk,
            public_evidence=public_evidence,
            engage=engage_llm_tier,
        )
        if llm_adjudication and llm_adjudication.get("status") == "adjudicated":
            label = llm_adjudication.get("risk_label")
            if label in Classification.__members__ and max(pii_score, mnpi_score) < 85.0:
                overall_risk = Classification(label)

        return ReviewResult(
            overall_risk=overall_risk,
            document_score=round(document_score, 3),
            pii_score=round(pii_score, 3),
            mnpi_score=round(mnpi_score, 3),
            jurisdictions_applied=[pack.code for pack in packs],
            jurisdiction_policy="strictest_wins",
            findings=findings,
            suggestions=self._suggestions(findings, include_suggestions),
            public_evidence=public_evidence,
            llm_adjudication=llm_adjudication,
            privacy_ledger=privacy_ledger,
        )
