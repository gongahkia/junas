from __future__ import annotations

from dataclasses import dataclass


JURISDICTION_ALIASES = {
    "SG": "SG",
    "SINGAPORE": "SG",
    "SEA": "SEA",
    "ASEAN": "SEA",
    "US": "US",
    "USA": "US",
    "UNITED STATES": "US",
    "UK": "UK",
    "GB": "UK",
    "UNITED KINGDOM": "UK",
    "EU": "EU",
    "EEA": "EU",
}


@dataclass(frozen=True)
class JurisdictionRulePack:
    code: str
    label: str
    pii_rules: tuple[str, ...]
    mnpi_rules: tuple[str, ...]
    references: tuple[str, ...]


RULE_PACKS: dict[str, JurisdictionRulePack] = {
    "SG": JurisdictionRulePack(
        code="SG",
        label="Singapore",
        pii_rules=("SG_PDPA_PERSONAL_DATA", "SG_PDPA_SENSITIVE_CONTEXT"),
        mnpi_rules=("SG_SFA_INSIDE_INFORMATION", "SG_SFA_GENERALLY_AVAILABLE"),
        references=(
            "Personal Data Protection Act 2012",
            "Securities and Futures Act 2001 sections 215, 218, 219",
        ),
    ),
    "SEA": JurisdictionRulePack(
        code="SEA",
        label="Southeast Asia baseline",
        pii_rules=("SEA_PERSONAL_DATA_BASELINE",),
        mnpi_rules=("SEA_MARKET_ABUSE_BASELINE",),
        references=("ASEAN-oriented cross-border privacy and market-abuse baseline",),
    ),
    "US": JurisdictionRulePack(
        code="US",
        label="United States",
        pii_rules=("US_PRIVACY_BASELINE",),
        mnpi_rules=("US_MNPI_INSIDER_TRADING", "US_REG_FD_PUBLIC_DISCLOSURE"),
        references=("SEC insider trading / MNPI guidance", "Regulation FD"),
    ),
    "UK": JurisdictionRulePack(
        code="UK",
        label="United Kingdom",
        pii_rules=("UK_GDPR_PERSONAL_DATA",),
        mnpi_rules=("UK_MAR_INSIDE_INFORMATION",),
        references=("UK GDPR", "UK Market Abuse Regulation"),
    ),
    "EU": JurisdictionRulePack(
        code="EU",
        label="European Union",
        pii_rules=("EU_GDPR_PERSONAL_DATA",),
        mnpi_rules=("EU_MAR_INSIDE_INFORMATION",),
        references=("GDPR Article 4", "EU Market Abuse Regulation"),
    ),
}


def normalize_jurisdiction(value: str | None, *, default: str = "SG") -> str:
    raw = (value or default).strip().upper()
    return JURISDICTION_ALIASES.get(raw, raw)


def resolve_rule_packs(source: str | None, destination: str | None) -> list[JurisdictionRulePack]:
    codes = [
        normalize_jurisdiction(source, default="SG"),
        normalize_jurisdiction(destination, default="SG"),
    ]
    packs: list[JurisdictionRulePack] = []
    seen: set[str] = set()
    for code in codes:
        pack = RULE_PACKS.get(code)
        if pack is None:
            pack = JurisdictionRulePack(
                code=code,
                label=code,
                pii_rules=(f"{code}_PERSONAL_DATA_BASELINE",),
                mnpi_rules=(f"{code}_MNPI_BASELINE",),
                references=(f"{code} customer-configured policy baseline",),
            )
        if pack.code not in seen:
            packs.append(pack)
            seen.add(pack.code)
    return packs
