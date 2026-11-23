"""Person-linked field and prose identifiers with local organizational exclusions."""

from __future__ import annotations

import re
from bisect import bisect_left

from junas.review.conjunctive_mnpi import ORG_NAME_RE

PERSON = re.compile(
    r"\b(?:personal|individual|employee|patient|customer|client|resident|staff|holder|"
    r"director|shareholder|applicant|beneficiary|claimant|home|residential)\b",
    re.I,
)
PRONOUN = re.compile(r"\b(?:her|his|their|she|he)\b", re.I)
ORG_CONTACT = re.compile(
    r"\b(?:office|corporate|company|registered|firm|public|general|reception|switchboard|hotline)"
    r"(?:\s+(?:office|mailing|postal|bank|contact|telephone|phone|account|address|line|"
    r"number|no\.?|reference|ref\.?|passport|national|ID|NRIC|FIN)){0,5}\s*[:#=]?\s*$",
    re.I,
)
EXAMPLE = re.compile(
    r"\b(?:dummy|placeholder|mock company|corporate template|does not identify|not anyone[’']s)\b", re.I
)
FIELD_PATTERNS = {
    "BANK_ACCOUNT": re.compile(
        r"(?i:\b(?:personal\s+)?bank\s+account(?:\s*(?:number|no\.?|ID))?\s*[:#=]?\s*)"
        r"(?P<value>[A-Z]{0,2}\d(?:[A-Z0-9 -]{3,30}[A-Z0-9]))\b"
    ),
    "GOVERNMENT_ID": re.compile(
        r"(?i:\b(?:passport|national\s+ID|NRIC|FIN|taxpayer\s+ID|identity document reference)"
        r"\s*(?:number|no\.?|on file)?\s*[:#=]?\s*)(?P<value>[A-Z0-9][A-Z0-9•*…-]{4,24})\b"
    ),
    "PHONE": re.compile(
        r"(?i:\b(?:personal\s+(?:mobile|phone)|mobile|telephone|phone|direct\s+(?:line|extension))\s*"
        r"(?:number)?\s*[:#=]?\s*)(?P<value>\+?\d[\d ()-]{1,20}\d)\b"
    ),
}
BANK_NUMBER = re.compile(r"\baccount\s*,?\s+(?:no\.?|number)\s*[:#=]?\s*(?P<value>\d[\d -]{4,29}\d)\b", re.I)
PHONE_NUMBER = re.compile(r"(?<![\w\d])(?P<value>\+\d{1,3}[ -]\d[\d ()-]{5,18}\d)\b")
ADDRESS = re.compile(
    r"\b(?P<value>\d{1,5}(?:[ \t]+[^\W\d_][\w’'-]*){1,6}[ \t]+"
    r"(?:Road|Rd|Street|St|Lane|Ln|Walk|Quay|Grove|Drive|Dr|Avenue|Ave|Crescent|Close|Way|Terrace|Place|Rise|Reach|View|Link|Green|Square|Park)"
    r"(?:,?[ \t]+#\d{1,3}-\d{1,5})?(?:,?[ \t]+Singapore(?:[ \t]+\d{6})?)?)\b",
    re.I,
)
QUOTED_ADDRESS = re.compile(
    r"[“\"](?P<value>[^\n”\"]{2,70})[”\"]\s+under\s+(?:her\s+|his\s+|their\s+)?correspondence address\b", re.I
)
ROLE_EMPLOYER = re.compile(
    r"\b(?P<role>(?:board observer|treasury analyst|payroll lead|finance manager|sole administrator|"
    r"chief financial officer|general counsel))\s+(?:at|of)\s+",
    re.I,
)
QUASI_FIELDS = (
    re.compile(r"\bAge\s*:\s*\d{1,3}\b", re.I),
    re.compile(r"\b(?:postcode|postal code)\s*:\s*[A-Z0-9 -]{3,10}\b", re.I),
    re.compile(r"\b(?:occupation|job title)\s*:\s*[^;\n.]{2,50}", re.I),
)
MONTH_NAME = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
PROSE_QUASI = re.compile(
    rf"\b(?:\d{{1,3}}[- ]year[- ]old\s+resident\s+(?:of|in)\s+[^.\n;]{{2,60}}?"
    rf"\s+who\s+joined\s+in\s+{MONTH_NAME}\s+\d{{4}}\s+and\s+is\s+"
    r"(?:the\s+)?issuer[’']s\s+only\s+[^.\n;]{3,100}|"
    rf"born\s+in\s+{MONTH_NAME}\s+\d{{4}},?\s+resident\s+in\s+postal\s+"
    r"(?:sector|district)\s+\d{1,2},?\s+and\s+(?:formerly\s+)?"
    r"(?:(?:the\s+)?issuer[’']s\s+only\s+|assigned\s+to\s+)[^.\n;]{3,100})",
    re.I,
)


def local_bounds(text: str, start: int, end: int, distance: int = 180) -> tuple[int, int]:
    a = max(text.rfind("\n", max(0, start - distance), start) + 1, start - distance, 0)
    b = text.find("\n", end, end + distance)
    return a, min(b if b >= 0 else len(text), end + distance)


def paragraph_bounds(text: str, start: int, end: int, distance: int = 1200) -> tuple[int, int]:
    lower, upper = max(0, start - distance), min(len(text), end + distance)
    left = lower
    for match in re.finditer(r"\r?\n[ \t]*\r?\n", text[lower:start]):
        left = lower + match.end()
    following = re.search(r"\r?\n[ \t]*\r?\n", text[end:upper])
    return left, end + following.start() if following else upper


def nonpersonal(text: str, start: int, end: int, label: str) -> bool:
    a, b = local_bounds(text, start, end)
    before, after = text[a:start], text[end:b]
    if ORG_CONTACT.search(before[-65:].replace(",", " ")):
        return True
    if re.match(r"\s*\((?:sample|public|general|office|company|corporate|dummy|template|switchboard)\b", after, re.I):
        return True
    if label == "GOVERNMENT_ID" and (
        EXAMPLE.search(before[-90:] + after[:160])
        or re.search(r"\b(?:circular|company|corporate)\s+(?:case\s+)?(?:reference|registration)", after[:100], re.I)
        or re.search(
            r"\b(?:carton|packaging|artwork)\s+proof\s+shows\s*[“\"']?\s*"
            r"(?:ID\s+(?:No\.?|number)\s*[:#]?\s*)?$",
            before,
            re.I,
        )
        or re.search(
            r"\b(?:this|it|that (?:identifier|code))\s+(?:is|was)\s+(?:(?:the|an?)\s+)?"
            r"(?:artwork|product|batch|carton)\s+(?:reference|code|identifier)\b",
            after[:160],
            re.I,
        )
    ):
        return True
    if label == "DATE_OF_BIRTH" and re.search(
        r"\b(?:incorporation|establishment) date\b|not anyone[’']s birth", after[:200], re.I
    ):
        return True
    if label == "BANK_ACCOUNT" and re.search(
        r"(?i:\b(?:corporate|company|firm))\s+(?:[A-Z][\w’'-]*\s+){0,4}"
        r"(?i:bank\s+account\s*,?\s*(?:no\.?|number)?\s*[:#=]?\s*)$",
        before,
    ):
        return True
    if label == "BANK_ACCOUNT" and re.search(
        r"\b(?:specimen|sample|formatting example|not a payment destination)\b", before[-100:] + after[:100], re.I
    ):
        return True
    return bool(
        label == "BANK_ACCOUNT" and re.search(r"\b(?:dummy|placeholder|template)\b", before[-45:] + after[:60], re.I)
    )


def personal_link(text: str, start: int, end: int, people: list[dict]) -> bool:
    a, b = local_bounds(text, start, end)
    index = bisect_left(people, a, key=lambda s: s["start_char"])
    if index < len(people) and people[index]["start_char"] < b:
        return True
    value = text[a:b]
    if re.search(
        r"\b(?:personal|home|residential)\b|\b(?:individual|employee|patient|customer|client|staff)"
        r"(?:[’']s|\s+(?:mobile|phone|telephone|address|account|ID|number))\b",
        value,
        re.I,
    ):
        return True
    field = re.search(
        r"\b(?:mailing|correspondence) address\s*[:=]?\s*$|\b(?:bank account|mobile|phone|email)"
        r"(?: address| number)?\s*[:=]?\s*$",
        text[max(0, start - 60) : start],
        re.I,
    )
    # a personal pronoun needs an anchored person elsewhere in the paragraph.
    if field or PRONOUN.search(value):
        left, right = paragraph_bounds(text, start, end)
        index = bisect_left(people, left, key=lambda s: s["start_char"])
        return index < len(people) and people[index]["start_char"] < right
    return False


def personal_email_link(text: str, start: int, end: int, people: list[dict]) -> bool:
    """Link multi-part mailboxes to an anchored name in the same bounded paragraph."""
    local = text[start:end].split("@", 1)[0]
    parts = re.findall(r"[^\W\d_]+", local.casefold())
    if not 2 <= len(parts) <= 5 or re.search(r"\d", local):
        return False
    left, limit = paragraph_bounds(text, start, end)
    index = bisect_left(people, left, key=lambda s: s["start_char"])
    stop = bisect_left(people, limit, key=lambda s: s["start_char"])
    for position in range(index, stop):
        person = people[position]
        if parts == re.findall(r"[^\W\d_]+", person["matched_text"].casefold()):
            return True
    return False


def _span(text: str, start: int, end: int, label: str, reason: str) -> dict:
    return dict(
        label=label,
        rule="contextual_" + label.lower(),
        start_char=start,
        end_char=end,
        matched_text=text[start:end],
        reason=reason,
    )


def quasi_identifiers(text: str, people: list[dict]) -> list[dict]:
    spans = []
    linked_profiles = (
        rf"\bbirth month and year\s*\({MONTH_NAME}\s+\d{{4}}\),"
        rf"\s*home postal sector\s*\(\d{{1,2}}\),?\s*and\s+(?:her|his|their)\s+role\s+as\s+[^.\n;]{{3,120}}",
        rf"\b{MONTH_NAME}\s+\d{{4}}\),\s*home planning area\s*\([^)]{{2,50}}\)\s+and\s+role\s*\([^)]{{3,100}}\)",
        rf"\b(?:[\w’'-]+\s+){{1,7}}(?:lead|supervisor|approver|manager)"
        rf"\s*\(birth month and year:\s*{MONTH_NAME}\s+\d{{4}};\s*residential postal sector:\s*\d{{1,2}}",
    )
    for pattern in linked_profiles:
        for match in re.finditer(pattern, text, re.I):
            left, right = paragraph_bounds(text, *match.span())
            if not any(left <= person["start_char"] < right for person in people):
                continue
            start = match.start()
            article = re.match(r"the\s+", match.group(), re.I)
            if article:
                start += article.end()
            spans.append(
                _span(
                    text,
                    start,
                    match.end(),
                    "QUASI_IDENTIFIER_COMBINATION",
                    "person-linked birth, locality and employment profile; unverified",
                )
            )
    individual = bool(re.search(r"\b(?:individual|private)[- ]client\b|\bclient capacity\s*:", text, re.I))
    for match in PROSE_QUASI.finditer(text):
        left, right = paragraph_bounds(text, match.start(), match.end())
        index = bisect_left(people, left, key=lambda s: s["start_char"])
        anchored = index < len(people) and people[index]["start_char"] < right
        if anchored or re.search(r"\bissuer[’']s\s+only\b", match.group(), re.I):
            end = match.end()
            while end > match.start() and text[end - 1].isspace():
                end -= 1
            spans.append(
                _span(
                    text,
                    match.start(),
                    end,
                    "QUASI_IDENTIFIER_COMBINATION",
                    "linked age/birth, locality and employment attributes; identifying potential is unverified",
                )
            )
    for block in re.finditer(r"[^\n]+", text):
        value = block.group()
        fields = [p.search(value) for p in QUASI_FIELDS]
        if all(fields) and PERSON.search(value) and re.search(r"\b(?:only|unique|identif\w+)\b", value, re.I):
            matches = [m for m in fields if m is not None]
            spans.append(
                _span(
                    text,
                    block.start() + min(m.start() for m in matches),
                    block.start() + max(m.end() for m in matches),
                    "QUASI_IDENTIFIER_COMBINATION",
                    "three linked fields with an explicit singling-out claim; unverified",
                )
            )
    orgs = list(ORG_NAME_RE.finditer(text))
    org_at = {m.start(): m for m in orgs}
    for role in ROLE_EMPLOYER.finditer(text):
        org = org_at.get(role.end())
        if org and (individual or "lead" in role.group("role").casefold()):
            spans.append(
                _span(
                    text,
                    role.start(),
                    org.end(),
                    "QUASI_IDENTIFIER_COMBINATION",
                    "individual role and employer linkage; identifying potential is unverified",
                )
            )
    if individual:
        for org in orgs:
            tail = re.match(
                r",\s+a\s+[^.\n]{0,60}issuer\s+where\s+(?:she|he|the client)\s+works\s+as\s+"
                r"(?:a\s+)?(?:finance manager|treasury analyst|payroll lead)\b",
                text[org.end() :],
                re.I,
            )
            if tail:
                spans.append(
                    _span(
                        text,
                        org.start(),
                        org.end() + tail.end(),
                        "QUASI_IDENTIFIER_COMBINATION",
                        "employer, listing and personal role linkage; identifying potential is unverified",
                    )
                )
        for match in re.finditer(r"\b\d[\d,]*\s+[A-Z][\w-]*\s+shares through an employee plan\b", text):
            spans.append(
                _span(
                    text,
                    *match.span(),
                    "QUASI_IDENTIFIER_COMBINATION",
                    "personal holding amount, security and employment-plan linkage; unverified",
                )
            )
        for match in re.finditer(r"\blives in\s+[^.\n]{10,120};\s*works\s+[^.\n]{5,100}?\s+at\s+", text, re.I):
            org = org_at.get(match.end())
            if org:
                spans.append(
                    _span(
                        text,
                        match.start(),
                        org.end(),
                        "QUASI_IDENTIFIER_COMBINATION",
                        "linked housing, locality, work pattern and employer; unverified",
                    )
                )
        for match in re.finditer(
            r"\bIndividual investor holding shares in\s+[^\n]{5,180}?own-account brokerage account\. "
            r"The client also works in the issuer[’']s [^.\n]{2,50}\bteam\b",
            text,
            re.I,
        ):
            spans.append(
                _span(
                    text,
                    *match.span(),
                    "QUASI_IDENTIFIER_COMBINATION",
                    "linked ownership, account capacity and employer role; unverified",
                )
            )
    return spans


def identifier_fields(text: str, people: list[dict] | None = None) -> list[dict]:
    people = sorted(people or [], key=lambda s: s["start_char"])
    spans = []
    patterns = [(label, p) for label, p in FIELD_PATTERNS.items()] + [
        ("BANK_ACCOUNT", BANK_NUMBER),
        (
            "BANK_ACCOUNT",
            re.compile(
                r"\b(?:personal|her|his|their)\s+account\s+(?:at|with)\s+"
                r"[^.\n;]{2,70}?\bBank,?\s+no\.?\s*(?P<value>\d[\d -]{4,29}\d)\b",
                re.I,
            ),
        ),
        ("PHONE", PHONE_NUMBER),
        ("POSTAL_ADDRESS", ADDRESS),
        ("POSTAL_ADDRESS", QUOTED_ADDRESS),
    ]
    for label, pattern in patterns:
        for match in pattern.finditer(text):
            value = match.group("value").rstrip(" .,")
            start, end = match.start("value"), match.start("value") + len(value)
            if nonpersonal(text, start, end, label):
                continue
            if label != "GOVERNMENT_ID" and not personal_link(text, start, end, people):
                continue
            digits = sum(c.isdigit() for c in value)
            if label == "GOVERNMENT_ID" and not digits:
                continue
            if label == "PHONE" and not (
                7 <= digits <= 15
                or 3 <= digits <= 6
                and re.search(r"direct\s+extension\s*[:#]?\s*$", text[max(0, start - 30) : start], re.I)
            ):
                continue
            if label == "BANK_ACCOUNT" and not 6 <= digits <= 22:
                continue
            spans.append(_span(text, start, end, label, "locally person-linked field or prose identifier"))
    spans.extend(quasi_identifiers(text, people))
    return spans
