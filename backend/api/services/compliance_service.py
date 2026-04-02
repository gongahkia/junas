"""Compliance checking service ported from Junas compliance/rules.ts."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class ComplianceRule:
    id: str
    name: str
    category: str
    description: str
    keywords: list[str]
    severity: str  # high | medium | low

@dataclass
class ComplianceCheckResult:
    rule_id: str
    rule_name: str
    status: str  # pass | warning | fail
    details: str
    severity: str

DEFAULT_SG_RULES: list[ComplianceRule] = [
    ComplianceRule("pdpa-consent", "PDPA Consent Clause", "Data Protection", "Document must reference consent for personal data collection under PDPA", ["consent", "personal data", "pdpa", "data protection"], "high"),
    ComplianceRule("pdpa-purpose", "PDPA Purpose Limitation", "Data Protection", "Data usage purpose must be clearly stated", ["purpose", "personal data", "collection", "use", "disclosure"], "high"),
    ComplianceRule("governing-law", "Governing Law Clause", "General", "Contract must specify governing law", ["governing law", "governed by", "laws of"], "medium"),
    ComplianceRule("dispute-resolution", "Dispute Resolution", "General", "Contract must include dispute resolution mechanism", ["dispute resolution", "arbitration", "mediation", "jurisdiction"], "medium"),
    ComplianceRule("termination", "Termination Clause", "General", "Contract must include termination provisions", ["termination", "terminate", "notice period"], "medium"),
    ComplianceRule("indemnification", "Indemnification", "Liability", "Indemnification provisions should be present", ["indemnify", "indemnification", "hold harmless"], "low"),
    ComplianceRule("force-majeure", "Force Majeure", "Risk", "Force majeure clause should be present for risk allocation", ["force majeure", "act of god", "unforeseeable", "beyond control"], "low"),
    ComplianceRule("confidentiality", "Confidentiality", "General", "Confidentiality obligations should be specified", ["confidential", "confidentiality", "non-disclosure", "proprietary"], "medium"),
    ComplianceRule("employment-act-notice", "Employment Act Notice Period", "Employment", "Employment contracts must comply with notice period requirements", ["notice period", "termination notice", "employment act"], "high"),
    ComplianceRule("cpf-contribution", "CPF Contribution Reference", "Employment", "Employment contracts should reference CPF obligations", ["cpf", "central provident fund", "employer contribution"], "medium"),
]

def check_compliance(text: str, rules: list[ComplianceRule] | None = None) -> list[ComplianceCheckResult]:
    if rules is None:
        rules = DEFAULT_SG_RULES
    lower = text.lower()
    results: list[ComplianceCheckResult] = []
    for rule in rules:
        match_count = sum(1 for kw in rule.keywords if kw.lower() in lower)
        ratio = match_count / len(rule.keywords) if rule.keywords else 0
        if ratio >= 0.5:
            status = "pass"
            details = f"Found {match_count}/{len(rule.keywords)} expected keywords"
        elif ratio > 0:
            status = "warning"
            details = f"Partial match: {match_count}/{len(rule.keywords)} keywords found"
        else:
            status = "fail"
            details = f"No matching keywords found — {rule.description}"
        results.append(ComplianceCheckResult(rule.id, rule.name, status, details, rule.severity))
    return results
