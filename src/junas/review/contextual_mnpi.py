"""Linked, text-claimed issuer-event hypotheses; no legal or public-status verification."""

from __future__ import annotations

import re
from bisect import bisect_right
from typing import Any

from junas.review.conjunctive_mnpi import ORG_NAME_RE
from junas.review.document_structure import parse_document_structure
from junas.review.entity_linker import canonical_org

ISSUER = re.compile(
    r"\b(?:(?:SGX|Singapore|Catalist)[- ]listed\s+(?:issuer|company)|"
    r"listed\s+(?:issuer|company)|the\s+issuer|issuer[’']s|the\s+company)\b",
    re.I,
)
EVENT = re.compile(
    r"\b(?:acqui(?:re|red|res|sition)|merger|scheme (?:implementation|of arrangement)|"
    r"takeover|binding agreement|agreement to sell|termination|terminat\w*|largest[^.\n]{0,60}contract|"
    r"earnings|profit|revenue|guidance|forecast|insolvency|default|acceleration notice|"
    r"trial halt|cyber(?:attack| incident)|disposal|sale of)\b",
    re.I,
)
MATERIAL = re.compile(
    r"\b(?:price[- ]sensitive|material(?:ly)?|largest|controlling stake|"
    r"all (?:(?:outstanding|issued) )?shares)\b|\b\d{2,3}(?:\.\d+)?%[^.\n]{0,40}"
    r"(?:premium|above[^.\n]{0,15}(?:closing|traded|close))\b",
    re.I,
)
# percentages are evidence of potential significance, not a legal materiality threshold.
QUANT_MATERIAL = re.compile(
    r"\b(?P<pct>\d{1,3}(?:\.\d+)?)%\s+(?:of\s+)?[^.\n]{0,70}?"
    r"\b(?:revenue|operating profit|earnings|market capitalisation|EBITDA)\b",
    re.I,
)
NONPUBLIC = re.compile(
    r"\b(?:(?:has|have|had)\s+not\s+(?:yet\s+)?(?:(?:been|made)\s+)?(?:publicly\s+)?"
    r"(?:disclosed|announced|released)(?:[^.\n]{0,65}?publicly disclosed)?|"
    r"not\s+(?:yet\s+)?(?:(?:been|made)\s+)?publicly\s+(?:disclosed|announced|released)|"
    r"neither[^.\n]{0,140}(?:publicly\s+(?:disclosed|announced)|disclosed[^.\n]{0,35}publicly)|"
    r"unpublished|not\s+in\s+the\s+public\s+domain|"
    r"(?:exchange\s+|SGXNet\s+)?announcement\s+(?:is|remains)\s+(?:still\s+)?(?:in\s+)?draft|"
    r"no\s+(?:exchange\s+|SGXNet\s+)?announcement\s+has\s+been\s+(?:made|filed|released))\b",
    re.I,
)
PUBLIC = re.compile(
    r"\b(?:publicly\s+(?:disclosed|announced|released)|already\s+published|published\s+on\s+SGXNet)\b", re.I
)
HYPOTHETICAL = re.compile(
    r"\b(?:hypothetical|training example|for illustration|suppose|if\s+.{0,60}(?:were|would))\b", re.I
)
NEGATED_EVENT = re.compile(
    r"\b(?:no\s+(?:material\s+|binding\s+)?(?:acquisition|merger|takeover|offer|default|contract termination)|"
    r"(?:did|will|has|have)\s+not\s+(?:sign|acquire|merge)|no\s+price[- ]sensitive\s+(?:event|information))\b",
    re.I,
)
IMMATERIAL = re.compile(r"\b(?:immaterial|not\s+(?:financially\s+)?material|not\s+price[- ]sensitive)\b", re.I)
UNRELATED = re.compile(
    r"\b(?:unrelated|separate\s+(?:service|staff|employee|payroll|personal)|different\s+issuer)\b", re.I
)
TRANSITION = re.compile(
    r"\b(?:since|after|predates|separate development|following morning|did not mention|does not mention|"
    r"says nothing about|not mention|that statement was accurate when filed)\b",
    re.I,
)
TOPICS = {
    "transaction": re.compile(
        r"\b(?:acqui\w*|takeover|merger|agreement|offer|disposal|transaction|division|scheme)\b", re.I
    ),
    "contract": re.compile(r"\b(?:terminat\w*|contract|customer)\b", re.I),
    "earnings": re.compile(r"\b(?:profit|earnings|revenue|forecast|guidance|EBITDA|outlook)\b", re.I),
    "debt": re.compile(r"\b(?:debt|acceleration|default|refinancing)\b", re.I),
    "incident": re.compile(r"\b(?:cyberattack|cyber incident|trial halt)\b", re.I),
}


def _topics(value: str) -> set[str]:
    return {name for name, pattern in TOPICS.items() if pattern.search(value)}


def _sentences(text: str, start: int, end: int) -> list[tuple[int, int]]:
    spans = []
    a = start
    for match in re.finditer(r"[.!?](?=\s+[A-Z“])", text[start:end]):
        b = start + match.end()
        if re.search(r"\b(?:Ltd|Pte|Inc|Corp|Mr|Mrs|Ms|Dr|Prof)\.$", text[max(a, b - 8) : b]):
            continue
        spans.append((a, b))
        a = b
    if a < end:
        spans.append((a, end))
    return spans


def _sentence(text: str, sentences: list[tuple[int, int]], position: int) -> tuple[int, int]:
    for a, b in sentences:
        if a <= position < b:
            return a, b
    return position, position


def _item(text: str, a: int, b: int, kind: str) -> dict:
    return {"kind": kind, "start_char": a, "end_char": b, "matched_text": text[a:b]}


def contextual_mnpi(text: str, findings: list[Any]) -> dict:
    units = [(u.start_char, u.end_char) for u in parse_document_structure(text).units if u.kind != "document"]
    if not units:
        return {"state": "not_detected", "evidence": [], "public_status_verified": False, "reason": "no event evidence"}
    starts = [a for a, _ in units]
    sentences = [_sentences(text, a, b) for a, b in units]
    orgs = [[(a + m.start(), a + m.end()) for m in ORG_NAME_RE.finditer(text[a:b])] for a, b in units]
    private_matches = list(NONPUBLIC.finditer(text))
    public_matches = [
        m for m in PUBLIC.finditer(text) if not any(p.start() <= m.start() < p.end() for p in private_matches)
    ]
    hypotheses = []
    unresolved = False
    for private in private_matches:
        index = bisect_right(starts, private.start()) - 1
        if index < 0:
            continue
        a, b = units[index]
        sa, sb = _sentence(text, sentences[index], private.start())
        statement = text[sa:sb]
        if (
            UNRELATED.search(statement)
            or HYPOTHETICAL.search(statement)
            or IMMATERIAL.search(statement)
            or NEGATED_EVENT.search(statement)
        ):
            continue
        topics = _topics(statement)
        previous = []
        if topics or re.search(r"\b(?:it|this|(?:the|that) notice|both)\b", statement, re.I):
            for prev in range(max(0, index - 2), index):
                x, y = units[prev]
                value = text[x:y]
                if a - y <= 1600 and EVENT.search(value) and (_topics(value) & topics) and not UNRELATED.search(value):
                    previous.append(prev)
        indices = previous + [index]
        events = []
        material = []
        for frame in indices:
            x, y = units[frame]
            for event in EVENT.finditer(text, x, y):
                ea, eb = _sentence(text, sentences[frame], event.start())
                sentence = text[ea:eb]
                if HYPOTHETICAL.search(sentence) or NEGATED_EVENT.search(sentence) or IMMATERIAL.search(sentence):
                    continue
                events.append((event.start(), event.end()))
            for match in MATERIAL.finditer(text, x, y):
                ma, mb = _sentence(text, sentences[frame], match.start())
                if not (
                    IMMATERIAL.search(text[ma:mb])
                    or NEGATED_EVENT.search(text[ma:mb])
                    or HYPOTHETICAL.search(text[ma:mb])
                ):
                    material.append((match.start(), match.end()))
            material.extend(
                (m.start(), m.end()) for m in QUANT_MATERIAL.finditer(text, x, y) if 10 <= float(m.group("pct")) <= 100
            )
        if not topics and not re.search(r"\b(?:it|this|(?:the|that) notice|both)\b", statement, re.I):
            unresolved = True
            continue
        if topics:

            def related(span: tuple[int, int]) -> bool:
                frame = bisect_right(starts, span[0]) - 1
                x, y = _sentence(text, sentences[frame], span[0])
                witness_topics = _topics(text[x:y])
                return not witness_topics or bool(witness_topics & topics)

            events = [span for span in events if related(span)]
            material = [span for span in material if related(span)]
        if not events or not material:
            unresolved = True
            continue
        private_orgs = [(x, y) for x, y in orgs[index] if sa <= x < sb]
        local_events = [e for e in events if sa <= e[0] < sb]
        private_subjects = [(x, y) for x, y in private_orgs if local_events and x < local_events[0][0]]
        # public statements about the same event conflict unless a later development is explicit.
        conflicting = False
        for pub in public_matches:
            frame = bisect_right(starts, pub.start()) - 1
            if frame not in indices:
                continue
            pa, pb = _sentence(text, sentences[frame], pub.start())
            public_statement = text[pa:pb]
            public_orgs = [(x, y) for x, y in orgs[frame] if pa <= x < pb]
            if (
                private_subjects
                and public_orgs
                and not any(
                    canonical_org(text[x:y]) == canonical_org(text[u:v])
                    for x, y in private_subjects
                    for u, v in public_orgs
                )
            ):
                continue
            same_topics = bool(_topics(public_statement) & topics)
            if (pa == sa or same_topics) and not (
                pub.end() < private.start() and TRANSITION.search(text[pub.end() : private.start()])
            ):
                conflicting = True
                break
        if conflicting:
            unresolved = True
            continue
        # an explicit subject in the disclosure sentence cannot borrow another issuer's event.
        event_sentence = _sentence(text, sentences[index], events[-1][0]) if events[-1][0] >= a else None
        if private_orgs and event_sentence != (sa, sb):
            event_orgs = [span for frame in indices for span in orgs[frame] if span[0] < sa]
            if event_orgs and not any(
                canonical_org(text[x:y]) == canonical_org(text[u:v]) for x, y in private_orgs for u, v in event_orgs
            ):
                unresolved = True
                continue
        issuer: tuple[int, int] | None = None
        named_subjects = [
            (x, y)
            for x, y in private_orgs
            if local_events
            and x < local_events[0][0]
            and not re.search(r"\b(?:from|with|to|by)\s*$", text[max(sa, x - 20) : x], re.I)
        ]
        if named_subjects:
            issuer = named_subjects[0]
        if issuer is None:
            for frame in indices:
                for x, y in orgs[frame]:
                    if re.search(r"\b(?:from|with|to|by)\s*$", text[max(units[frame][0], x - 20) : x], re.I):
                        continue
                    issuer = (x, y)
                    break
                if issuer is not None:
                    break
        # an issuer/company reference may inherit a preceding named subject, never a new event.
        if issuer is None and ISSUER.search(text[min(units[i][0] for i in indices) : b]):
            for prev in range(index - 1, max(-1, index - 5), -1):
                if orgs[prev] and a - units[prev][1] <= 2000:
                    candidates = [
                        (x, y)
                        for x, y in orgs[prev]
                        if not re.search(r"\b(?:from|with|to|by)\s*$", text[max(units[prev][0], x - 20) : x], re.I)
                    ]
                    if len(candidates) == 1:
                        issuer = candidates[0]
                    break
        if issuer is None:
            for frame in indices:
                issuer_match = ISSUER.search(text, *units[frame])
                if issuer_match:
                    issuer = issuer_match.span()
                    break
        if issuer is None:
            unresolved = True
            continue
        event_span = events[-1]
        components = [
            _item(text, *issuer, "issuer"),
            _item(text, *event_span, "event"),
            _item(text, *material[-1], "materiality"),
            _item(text, *private.span(), "claimed_nonpublic"),
        ]
        start = min(c["start_char"] for c in components)
        end = max(c["end_char"] for c in components)
        hypotheses.append(
            {
                "start_char": start,
                "end_char": end,
                "matched_text": text[start:end],
                "label": "CONTEXTUAL_MNPI",
                "rule": "contextual_mnpi",
                "components": components,
                "reason": "linked issuer event, materiality evidence and nonpublic claim; unverified",
                "public_status_verified": False,
            }
        )
    resolved_negative = bool(public_matches) and not private_matches
    return {
        "state": "present"
        if hypotheses
        else "unknown"
        if unresolved or (not resolved_negative and any(f.category == "MNPI" for f in findings))
        else "not_detected",
        "evidence": hypotheses,
        "public_status_verified": False,
        "reason": "text-claimed event hypotheses; unresolved links and contradictory claims abstain",
    }
