from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from noupe.backend.schemas import Classification
from noupe.review.jurisdictions import JurisdictionRulePack, resolve_rule_packs
from noupe.workflow.privacy_guard import EMAIL_RE, LONG_NUMBER_RE, MONEY_RE, PERCENT_RE, PHONE_RE


SG_NRIC_RE = re.compile(r"\b[STFGM]\d{7}[A-Z]\b", re.IGNORECASE)
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
    r"impairment|provision|resignation|ceo|cfo)\b",
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

    def _pii_findings(self, text: str, packs: list[JurisdictionRulePack]) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        jurisdiction = _pack_scope(packs)
        legal_basis = _legal_basis(packs, "pii_rules")
        patterns = []
        if any(pack.code == "SG" for pack in packs):
            patterns.extend(
                [
                    ("sg_nric_fin", SG_NRIC_RE, "high", "Singapore NRIC/FIN-like identifier"),
                    ("sg_postal_address", SG_POSTAL_RE, "medium", "Singapore postal-code address signal"),
                ]
            )
        patterns.extend(
            [
                ("email_address", EMAIL_RE, "medium", "Email address can identify an individual"),
                ("phone_number", PHONE_RE, "medium", "Phone number can identify or contact an individual"),
                ("passport_number", PASSPORT_RE, "high", "Passport-like identifier"),
                ("bank_account", BANK_ACCOUNT_RE, "high", "Bank/account-like financial identifier"),
                ("named_person", NAME_RE, "low", "Named person reference"),
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
        return findings

    def _mnpi_findings(self, text: str, packs: list[JurisdictionRulePack]) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        jurisdiction = _pack_scope(packs)
        legal_basis = _legal_basis(packs, "mnpi_rules")
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

        for pattern, rule, severity, reason in [
            (NONPUBLIC_RE, "nonpublic_marker", "high", "Explicit non-public/confidentiality marker"),
            (MONEY_RE, "financial_amount", "medium", "Specific financial amount may be material"),
            (PERCENT_RE, "financial_percentage", "medium", "Specific financial percentage may be material"),
            (LONG_NUMBER_RE, "large_number", "medium", "Large numeric value may be material"),
        ]:
            for match in pattern.finditer(text):
                findings.append(
                    _new_finding(
                        idx=idx,
                        category="MNPI",
                        rule=rule,
                        jurisdiction=jurisdiction,
                        severity=severity,
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
                rationale = "Remove or mask personal data unless it is necessary for the recipient and purpose."
            elif finding.severity == "high":
                action = "remove_or_hold"
                replacement = "[REMOVE UNTIL PUBLICLY DISCLOSED OR APPROVED]"
                rationale = "Hold or remove apparent non-public material information before sending."
            else:
                action = "verify_or_rewrite"
                replacement = "[CITE PUBLIC SOURCE OR GENERALISE CLAIM]"
                rationale = "Verify public availability or rewrite to remove unsupported specificity."

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

    def _maybe_public_evidence(self, *, text: str, entity_id: str | None, mnpi_score: float) -> dict[str, Any] | None:
        if mnpi_score <= 0 or self.public_evidence_retriever is None:
            return None
        return self.public_evidence_retriever.retrieve(text=text, entity_id=entity_id, lexicon=None)

    def _maybe_llm_adjudication(
        self,
        *,
        text: str,
        overall_risk: Classification,
        public_evidence: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
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
    ) -> ReviewResult:
        packs = resolve_rule_packs(source_jurisdiction, destination_jurisdiction)
        findings = self._pii_findings(text, packs) + self._mnpi_findings(text, packs)
        pii_score = self._score(findings, "PII")
        mnpi_score = self._score(findings, "MNPI")
        document_score = max(pii_score, mnpi_score)
        overall_risk = _risk_from_score(document_score)

        public_evidence = self._maybe_public_evidence(text=text, entity_id=entity_id, mnpi_score=mnpi_score)
        privacy_ledger = list((public_evidence or {}).get("privacy_ledger", []))
        llm_adjudication = self._maybe_llm_adjudication(
            text=text,
            overall_risk=overall_risk,
            public_evidence=public_evidence,
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
