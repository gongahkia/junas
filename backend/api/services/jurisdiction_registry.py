"""Singapore-only jurisdiction registry. Pattern preserved for future Commonwealth adjacency (MY)."""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class CitationPattern:
    kind: str
    regex: str  # regex string for the jurisdiction
    description: str

@dataclass
class JurisdictionConfig:
    id: str
    name: str
    short_name: str
    citation_patterns: list[CitationPattern]
    legal_source_domains: dict[str, list[str]]
    system_prompt_addition: str
    template_ids: list[str] = field(default_factory=list)

JURISDICTIONS: dict[str, JurisdictionConfig] = {
    "sg": JurisdictionConfig(
        id="sg", name="Singapore", short_name="SG",
        citation_patterns=[
            CitationPattern("slr_r", r"\[(\d{4})\]\s+(\d+)\s+SLR\(R\)\s+(\d+)", "Singapore Law Reports (Reissue)"),
            CitationPattern("slr", r"\[(\d{4})\]\s+(\d+)\s+SLR\s+(\d+)", "Singapore Law Reports"),
            CitationPattern("sgca", r"\[(\d{4})\]\s+SGCA\s+(\d+)", "Singapore Court of Appeal"),
            CitationPattern("sghc", r"\[(\d{4})\]\s+SGHC\s+(\d+)", "Singapore High Court"),
            CitationPattern("statute_cap", r"\b([A-Z][A-Za-z0-9&'/-]*(?:\s+[A-Z][A-Za-z0-9&'/-]*)*\s+Act)\s*\((Cap\.?\s*[0-9A-Z]+(?:\s*,\s*\d{4}\s+Rev\s+Ed)?)\)", "Singapore statute chapter"),
        ],
        legal_source_domains={
            "case_law": ["judiciary.gov.sg", "singaporelawwatch.sg", "elitigation.sg"],
            "statutes": ["sso.agc.gov.sg", "agc.gov.sg"],
        },
        system_prompt_addition="You are specialized in Singapore law. Use proper Singapore citation formats:\n- [YYYY] X SLR(R) XXX, [YYYY] SLR XXX, [YYYY] SGCA XX, [YYYY] SGHC XX\n- Statute format: Act Name (Cap. XX, YYYY Rev Ed)",
        template_ids=["nda-sg", "employment-sg", "mou-sg", "tenancy-sg", "board-resolution-sg", "share-transfer-sg"],
    ),
}

def get_jurisdiction(jurisdiction_id: str) -> JurisdictionConfig | None:
    return JURISDICTIONS.get(jurisdiction_id.lower())

def list_jurisdictions() -> list[JurisdictionConfig]:
    return list(JURISDICTIONS.values())
