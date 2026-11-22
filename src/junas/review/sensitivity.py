"""Local contextual targets, separate from broad risk findings and their scores."""

from __future__ import annotations

import re
from typing import Any

TARGET_VERSION = "junas.sensitivity.v1"
PII_RULE_MAP = {
    "GOVERNMENT_ID": ("sg_nric_fin", "us_ssn", "uk_nin", "au_tfn", "passport_number"),
    "PERSON_NAME": ("named_person",),
    "EMAIL": ("email_address",),
    "PHONE": ("phone_number",),
    "POSTAL_ADDRESS": ("sg_postal_address", "au_postal_address"),
    "BANK_ACCOUNT": ("bank_account",),
    "PERSONAL_RECORD_ID": (
        "employee_id",
        "customer_account_number",
        "bank_customer_reference",
        "medical_record_number",
        "insurance_member_id",
    ),
    "DATE_OF_BIRTH": ("date_of_birth",),
    "QUASI_IDENTIFIER_COMBINATION": ("quasi_identifier_combination",),
}
SHARED_MAILBOX = re.compile(
    r"^(?:info|contact|support|sales|admin|office|help|hello|enquiries|inquiries|"
    r"compliance|legal|privacy|ir|investor[._-]?relations|reception|billing|noreply|no-reply)(?:[._+-].*)?$",
    re.I,
)


def evidence(text: str, start: int, end: int, label: str, rule: str, reason: str) -> dict:
    if not 0 <= start < end <= len(text):
        raise ValueError("invalid contextual evidence bounds")
    return dict(start_char=start, end_char=end, matched_text=text[start:end], label=label, rule=rule, reason=reason)


def contextual_pii(text: str, findings: list[Any]) -> tuple[list[dict], list[dict]]:
    spans, excluded = [], []
    mapping = {rule: label for label, rules in PII_RULE_MAP.items() for rule in rules}
    for finding in findings:
        if finding.category != "PII" or finding.rule not in mapping:
            continue
        item = evidence(
            text,
            finding.start_char,
            finding.end_char,
            mapping[finding.rule],
            finding.rule,
            "configured person-linked identifier candidate",
        )
        if finding.rule == "email_address" and SHARED_MAILBOX.fullmatch(finding.matched_text.split("@")[0]):
            item["reason"] = "role/shared mailbox is outside the personal-email target"
            excluded.append(item)
        else:
            spans.append(item)
    return spans, excluded


def contextual_mnpi(text: str, findings: list[Any]) -> dict:
    return {
        "state": "unknown" if any(f.category == "MNPI" for f in findings) else "not_detected",
        "evidence": [],
        "reason": "broad signals alone do not establish contextual MNPI",
    }


def sensitivity(text: str, findings: list[Any]) -> dict:
    pii, excluded = contextual_pii(text, findings)
    return {
        "schema_version": TARGET_VERSION,
        "interpretation": "deterministic contextual candidates; no calibrated confidence or legal verification",
        "pii": {"state": "present" if pii else "not_detected", "evidence": pii, "excluded": excluded},
        "mnpi": contextual_mnpi(text, findings),
        "absence_verified": False,
    }
