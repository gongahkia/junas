"""Local contextual targets, separate from broad risk findings and their scores."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from junas.review.contextual_identifiers import (
    MONTH_NAME,
    identifier_fields,
    nonpersonal,
    personal_email_link,
    personal_link,
)
from junas.review.contextual_mnpi import contextual_mnpi
from junas.review.contextual_people import person_names

TARGET_VERSION = "junas.sensitivity.v4"
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
    r"registry|secretariat|announcements|disclosures?|press|media|operations|ops|records|board|companysecretary|"
    r"intake|governance|payroll|policy|policy[-_]?desk|research|research[-_]?desk|editorial|editor|"
    r"review|consultations?|recalls?|escrow|shareplans?|taxdesk|listingdesk|capmarkets|issuer[-_]?records)"
    r"(?:[._+-].*)?$",
    re.I,
)
FUNCTION_MAILBOX = re.compile(
    r"(?:^|[._+-])(?:ops|operations|education|licensing|settlements?|reconciliation|publications|refunds|filings)(?:$|[._+-])",
    re.I,
)


def evidence(text: str, start: int, end: int, label: str, rule: str, reason: str) -> dict:
    if not 0 <= start < end <= len(text):
        raise ValueError("invalid contextual evidence bounds")
    return dict(start_char=start, end_char=end, matched_text=text[start:end], label=label, rule=rule, reason=reason)


RECORD_CONTEXT = re.compile(
    r"(?i:\b(?P<kind>staff|employee|patient|medical record|insurance member|individual verification|"
    r"contact record|contact reference|contact ref\.?|contact ID|client contact|internal contact|"
    r"personal record|client reference|customer reference|"
    r"intake|holder|register|portal|secretariat|shareholder|collection|client|customer|"
    r"personnel|deal-team|reader|correspondence|staff ref\.?|identity document|respondent|party|verification|record|"
    r"claim|folio|reviewer|investor)"
    r"\s*(?P<qualifier>ID|number|no\.?|reference|ref\.?)?\s*(?:\([^\n)]{1,25}\))?"
    r"\s*(?:as|is|:|\#)?[ \t]+\(?)"
    r"(?P<value>[A-Z0-9]+(?:[-/][A-Z0-9]+)*)\b"
)
DOB_CONTEXT = re.compile(
    r"(?i:\b(?:date of birth|DOB|born|birth month and year)(?:[ \t]*\([^\n)]{0,50}\))?\s*(?:as|is|in|on|:|=)?[ \t]+\(?)"
    rf"(?P<value>\d{{1,2}}[ /-](?:[A-Za-z]+|\d{{1,2}})[ /-]\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}}|"
    rf"(?i:{MONTH_NAME})\s+\d{{4}})\b"
)


def valid_birth_date(value: str) -> bool:
    return any(
        _date_matches(value, fmt)
        for fmt in ("%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%B %Y", "%b %Y")
    )


def _date_matches(value: str, fmt: str) -> bool:
    try:
        datetime.strptime(value, fmt)
        return True
    except ValueError:
        return False


def contextual_pii(text: str, findings: list[Any]) -> tuple[list[dict], list[dict]]:
    people = person_names(text)
    spans, excluded = identifier_fields(text, people), []
    spans.extend(people)
    for pattern, label, rule in (
        (RECORD_CONTEXT, "PERSONAL_RECORD_ID", "contextual_personal_record"),
        (DOB_CONTEXT, "DATE_OF_BIRTH", "contextual_birth_date"),
    ):
        for match in pattern.finditer(text):
            value = match.group("value")
            if nonpersonal(text, *match.span("value"), label):
                continue
            if label == "DATE_OF_BIRTH" and not valid_birth_date(value):
                continue
            if label == "PERSONAL_RECORD_ID" and not any(c.isdigit() for c in value):
                continue
            if label == "PERSONAL_RECORD_ID" and (
                value.isdecimal()
                and not match.group("qualifier")
                or match.group("kind").casefold() in {"party", "respondent", "verification", "record"}
                and not personal_link(text, *match.span("value"), people)
            ):
                continue
            spans.append(evidence(text, *match.span("value"), label, rule, "explicit person-linked field"))
    if re.search(r"\b(?:individual|private)[- ]client\b|\bclient capacity\s*:|\bretail shareholder\b", text, re.I):
        header = text.split("\n\n", 1)[0]
        actual_client = bool(
            people
            or re.search(
                r"\bclient capacity\s*:|\b(?:client|analyst|applicant)\s+"
                r"(?:seeks|asks|reports|says|placed|is|works|holds)\b|"
                r"\bapplicant[’']s details\b",
                text,
                re.I,
            )
        )
        for m in re.finditer(
            r"\b(?:Ref\.?|File|Matter)\s*[:#]?\s+(?P<value>[A-Z0-9]+(?:[-/][A-Z0-9]+)+)\b", header, re.I
        ):
            if (
                actual_client
                and not re.search(r"\btemplate\s*$", header[max(0, m.start() - 20) : m.start()], re.I)
                and any(c.isdigit() for c in m.group("value"))
            ):
                spans.append(
                    evidence(
                        text,
                        *m.span("value"),
                        "PERSONAL_RECORD_ID",
                        "contextual_client_file",
                        "individual-client case reference",
                    )
                )
    for match in re.finditer(r"\bUnder reference\s+(?P<value>[A-Z0-9]+(?:[-/][A-Z0-9]+)+)", text, re.I):
        if personal_link(text, *match.span("value"), people):
            spans.append(
                evidence(
                    text,
                    *match.span("value"),
                    "PERSONAL_RECORD_ID",
                    "contextual_record_reference",
                    "locally linked individual reference",
                )
            )
    record_ids = {s["matched_text"] for s in spans if s["label"] == "PERSONAL_RECORD_ID"}
    for match in re.finditer(r"\b[A-Z][A-Z0-9]{1,}(?:[-/][A-Z0-9]+)*\b", text):
        if match.group() in record_ids:
            spans.append(
                evidence(
                    text,
                    *match.span(),
                    "PERSONAL_RECORD_ID",
                    "contextual_record_reference",
                    "repeated identifier anchored by a person-linked record field",
                )
            )
    mapping = {rule: label for label, rules in PII_RULE_MAP.items() for rule in rules}
    for finding in findings:
        if finding.category != "PII" or finding.rule not in mapping:
            continue
        if mapping[finding.rule] in {"QUASI_IDENTIFIER_COMBINATION", "POSTAL_ADDRESS", "PERSON_NAME"}:
            continue  # broad inferred findings are signals; contextual extraction supplies target spans.
        if nonpersonal(text, finding.start_char, finding.end_char, mapping[finding.rule]):
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
            shared = (
                SHARED_MAILBOX.fullmatch(local)
                or FUNCTION_MAILBOX.search(local)
                or re.search(
                    r"(?:^|[._+-])(?:intake|governance|payroll|disclosures?|secretariat|registry|policy|research|"
                    r"editorial|editor|review|consultation|taxdesk|listingdesk|capmarkets|records)(?:$|[._+-])",
                    local,
                    re.I,
                )
            )
            if shared:
                reason = "role/shared mailbox is outside the personal-email target"
            elif not (
                re.fullmatch(r"[^\W\d_]+[._-][^\W\d_.-]+", local)
                or personal_link(text, finding.start_char, finding.end_char, people)
                or personal_email_link(text, finding.start_char, finding.end_char, people)
            ):
                reason = "person association not established"
        elif item["label"] in {"PHONE", "POSTAL_ADDRESS", "BANK_ACCOUNT"}:
            if not any(
                s["label"] == item["label"]
                and s["start_char"] == item["start_char"]
                and s["end_char"] == item["end_char"]
                for s in spans
            ):
                continue
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
