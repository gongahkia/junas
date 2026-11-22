"""Local contextual targets, separate from broad risk findings and their scores."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from junas.review.contextual_identifiers import identifier_fields
from junas.review.contextual_mnpi import contextual_mnpi

TARGET_VERSION = "junas.sensitivity.v1"
PII_RULE_MAP = {
    "GOVERNMENT_ID": ("sg_nric_fin", "us_ssn", "uk_nin", "au_tfn", "passport_number"),
    "PERSON_NAME": ("named_person",),
    "EMAIL": ("email_address",),
    "PHONE": ("phone_number",),
    "POSTAL_ADDRESS": ("sg_postal_address", "au_postal_address", "postal_address"),
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
    r"compliance|legal|privacy|ir|investor[._-]?relations|reception|billing|noreply|no-reply|"
    r"registry|secretariat|announcements|disclosure|press|media|operations|ops|records|board|companysecretary)(?:[._+-].*)?$",
    re.I,
)


def evidence(text: str, start: int, end: int, label: str, rule: str, reason: str) -> dict:
    if not 0 <= start < end <= len(text):
        raise ValueError("invalid contextual evidence bounds")
    return dict(start_char=start, end_char=end, matched_text=text[start:end], label=label, rule=rule, reason=reason)


NAME_TOKEN = r"[^\W\d_][^\W\d_]*(?:[’'-][^\W\d_]+)*"
NAME_VALUE = rf"{NAME_TOKEN}(?:[ \t]+{NAME_TOKEN}){{0,4}}"
NAME_CONTEXT = re.compile(
    r"(?i:\b(?:name|client name|account holder|contact person|employee name|patient name|"
    r"from|to)\s*:\s*|\b(?:Mr|Mrs|Ms|Dr)\.?[ \t]+|\b(?:company secretary|counsel|"
    r"employee|patient|customer|client)[ \t]+)" + rf"(?P<value>{NAME_VALUE})"
)
ORG_WORDS = re.compile(r"\b(?:Ltd|Limited|Pte|Corp|Inc|LLC|Holdings|Group|Services|Team|Department)\b", re.I)
RECORD_CONTEXT = re.compile(
    r"(?i:\b(?:staff|employee|patient|medical record|insurance member|individual verification|"
    r"contact record|internal contact|personal record|client reference|customer reference)"
    r"\s*(?:ID|number|no\.?|reference)?\s*[:#]?[ \t]+)(?P<value>[A-Z0-9]+(?:[-/][A-Z0-9]+)*)\b"
)
DOB_CONTEXT = re.compile(
    r"(?i:\b(?:date of birth|DOB|born)(?:[ \t]*\([^\n)]{0,50}\))?\s*[:=]?[ \t]+)"
    r"(?P<value>\d{1,2}[ /-](?:[A-Za-z]+|\d{1,2})[ /-]\d{4}|\d{4}-\d{2}-\d{2})\b"
)


def valid_birth_date(value: str) -> bool:
    return any(_date_matches(value, fmt) for fmt in ("%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"))


def _date_matches(value: str, fmt: str) -> bool:
    try:
        datetime.strptime(value, fmt)
        return True
    except ValueError:
        return False


def personal_context(text: str, start: int, end: int) -> bool:
    local = text[max(0, start - 100) : min(len(text), end + 100)]
    return bool(
        re.search(r"\b(?:personal|individual|employee|patient|customer|client|resident|staff|holder)\b", local, re.I)
    )


def contextual_pii(text: str, findings: list[Any]) -> tuple[list[dict], list[dict]]:
    spans, excluded = identifier_fields(text), []
    for match in NAME_CONTEXT.finditer(text):
        # lower-case prose terminates a name; organization suffixes reject the whole candidate.
        raw = match.group("value")
        if ORG_WORDS.search(raw):
            continue
        tokens = list(re.finditer(NAME_TOKEN, raw))
        selected = []
        for token in tokens:
            if not token.group()[0].isupper():
                break
            selected.append(token)
        if selected:
            start, end = match.start("value"), match.start("value") + selected[-1].end()
            spans.append(
                evidence(text, start, end, "PERSON_NAME", "contextual_person_name", "explicit personal-name context")
            )
    for pattern, label, rule in (
        (RECORD_CONTEXT, "PERSONAL_RECORD_ID", "contextual_personal_record"),
        (DOB_CONTEXT, "DATE_OF_BIRTH", "contextual_birth_date"),
    ):
        for match in pattern.finditer(text):
            value = match.group("value")
            if label == "DATE_OF_BIRTH" and not valid_birth_date(value):
                continue
            if label == "PERSONAL_RECORD_ID" and not any(c.isdigit() for c in value):
                continue
            spans.append(evidence(text, *match.span("value"), label, rule, "explicit person-linked field"))
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
        reason = None
        if finding.rule == "email_address":
            local = finding.matched_text.split("@")[0]
            if SHARED_MAILBOX.fullmatch(local):
                reason = "role/shared mailbox is outside the personal-email target"
            elif not (
                re.fullmatch(r"[^\W\d_]+[._-][^\W\d_.-]+", local)
                or personal_context(text, finding.start_char, finding.end_char)
            ):
                reason = "person association not established"
        elif item["label"] in {"PHONE", "POSTAL_ADDRESS", "BANK_ACCOUNT"} and re.search(
            r"\b(?:office|corporate|company|public hotline)\b",
            text[text.rfind("\n", 0, finding.start_char) + 1 : finding.start_char],
            re.I,
        ):
            reason = "explicit organizational contact is outside the personal target"
        elif item["label"] in {"PHONE", "POSTAL_ADDRESS", "BANK_ACCOUNT"} and not personal_context(
            text, finding.start_char, finding.end_char
        ):
            reason = "person association not established"
        if reason:
            item["reason"] = reason
            excluded.append(item)
        else:
            spans.append(item)
    # prefer the explicit field detector when an older finding includes the field label.
    spans = [
        s
        for s in spans
        if s["rule"].startswith("contextual_")
        or not any(
            t["label"] == s["label"]
            and t["rule"].startswith("contextual_")
            and s["start_char"] <= t["start_char"] < t["end_char"] <= s["end_char"]
            for t in spans
        )
    ]
    unique = {(s["label"], s["start_char"], s["end_char"]): s for s in spans}
    return sorted(unique.values(), key=lambda s: (s["start_char"], s["end_char"], s["label"])), excluded


def sensitivity(text: str, findings: list[Any]) -> dict:
    pii, excluded = contextual_pii(text, findings)
    return {
        "schema_version": TARGET_VERSION,
        "interpretation": "deterministic contextual candidates; no calibrated confidence or legal verification",
        "pii": {
            "state": "present"
            if pii
            else "unknown"
            if any(e["reason"] == "person association not established" for e in excluded)
            else "not_detected",
            "evidence": pii,
            "excluded": excluded,
        },
        "mnpi": contextual_mnpi(text, findings),
        "absence_verified": False,
    }
