"""Linked, text-claimed issuer-event hypotheses; no legal or public-status verification."""

from __future__ import annotations

import re
from bisect import bisect_left, bisect_right
from decimal import Decimal
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
    r"takeover|proposal|offer|buy|binding agreement|agreement to sell|termination|terminat\w*|"
    r"largest[^.\n]{0,60}contract|"
    r"earnings|profit|revenue|guidance|forecast|insolvency|default|acceleration notice|"
    r"trial halt|cyber(?:attack| incident)|disposal|sale of|recall decision|recall of\s+\d[\d,]*|"
    r"(?:approved|ordered|initiated)\s+(?:a\s+)?recall|refinancing|bridge (?:loan|facility)|"
    r"rescue package|share placement|withdraw\w*|cancel\w*|refus\w*\s+to\s+(?:extend|roll)|"
    r"suspend\w*|suspension|deferr\w*|defer|moved\s+payment|"
    r"impairment|write[- ]down|non[- ]renewal|unblind\w*|"
    r"missed\s+(?:its\s+|the\s+)?primary\s+(?:efficacy\s+)?endpoint|"
    r"coupon\s+(?:increase|step[- ]up)|missed\s+(?:its\s+|the\s+)?(?:bond\s+)?target|"
    r"correction)\b",
    re.I,
)
EXPANDED_EVENT_WORDS = re.compile(
    r"refinancing|bridge|rescue|share placement|withdraw|cancel|refus|suspend|suspension|"
    r"deferr|defer|moved payment|impairment|write[- ]down|non[- ]renewal|unblind|coupon|missed|correction",
    re.I,
)
MATERIAL = re.compile(
    r"\b(?:price[- ]sensitive|material(?:ly)?|largest|controlling stake|"
    r"cash takeover|cash offer|all (?:(?:outstanding|issued) )?shares)\b|\b\d{2,3}(?:\.\d+)?%\s+"
    r"(?:premium|discount|(?:above|below)\s+(?:(?:the\s+)?(?:issuer|company)[’']s\s+|its\s+|the\s+)?"
    r"(?:(?:last|previous|prior)\s+)?(?:unaffected\s+)?(?:closing|traded|close)(?:\s+price)?)\b",
    re.I,
)
# percentages are evidence of potential significance, not a legal materiality threshold.
QUANT_MATERIAL = re.compile(
    r"\b(?P<pct>\d{1,3}(?:\.\d+)?)%\s+(?:of\s+)?[^;\n]{0,100}?"
    r"\b(?:revenue|operating profit|earnings|market capitalisation|EBITDA)\b",
    re.I,
)
# these are asserted financial consequences, not universal legal materiality cutoffs.
FINANCIAL_CONSEQUENCE = re.compile(
    r"\bturn\b[^.;\n]{0,120}\bprofit\s+into\s+(?:(?:a|an)\s+)?[^.;\n]{0,50}\bloss\b|"
    r"\b\d+(?:\.\d+)?%\s+of\s+(?:(?:the\s+)?issuer[’']s\s+|the\s+|its\s+)?"
    r"(?:last\s+)?traded\s+(?:share\s+)?price\b|"
    r"\b[1-9]\d*(?:\.\d+)?[- ]basis[- ]points?\s+"
    r"(?:(?:coupon\s+)?(?:increase|step[- ]up)|to\s+the\s+coupon)\b|"
    r"\b(?:pivotal|phase\s+(?:III|3))\b[^.;\n]{0,100}\b(?:trial|study)\b",
    re.I,
)
COMPARATIVE_COST = re.compile(
    r"\badd\s+(?P<cost_currency>S\$|SGD|USD|\$)\s*(?P<cost>\d+(?:\.\d+)?)\s+million\s+in\s+annual\s+interest,?\s+"
    r"against\s+[^.;\n]{0,50}?(?P<profit_currency>S\$|SGD|USD|\$)\s*(?P<profit>\d+(?:\.\d+)?)\s+million\s+"
    r"(?:in\s+)?(?:pre-tax\s+)?profit\b",
    re.I,
)
NONPUBLIC = re.compile(
    r"\b(?:(?:has|have|had)\s+not\s+(?:yet\s+)?(?:(?:been|made)\s+)?(?:publicly\s+)?"
    r"(?:disclosed|announced|released)(?:[^.\n]{0,65}?publicly disclosed)?|"
    r"not\s+(?:yet\s+)?(?:(?:been|made)\s+)?publicly\s+(?:disclosed|announced|released)|"
    r"neither[^.\n]{0,140}(?:publicly\s+(?:disclosed|announced)|disclosed[^.\n]{0,35}publicly)|"
    r"unpublished|not\s+in\s+the\s+public\s+domain|"
    r"(?:exchange\s+|SGXNet\s+)?announcement\s+(?:is|remains)\s+(?:still\s+)?(?:in\s+)?draft|"
    r"no\s+(?:exchange\s+|SGXNet\s+)?announcement\s+has\s+been\s+(?:made|filed|released)|"
    r"(?:has|have|had)\s+not\s+(?:yet\s+)?(?:been\s+)?(?:made\s+public|released\s+to\s+the\s+(?:market|exchange))|"
    r"(?:remains?|is|are)\s+(?:still\s+)?(?:unannounced|undisclosed))\b",
    re.I,
)
PUBLIC = re.compile(
    r"\b(?:publicly\s+(?:disclosed|announced|released)|already\s+published|published\s+on\s+SGXNet|"
    r"public register entry\s+(?:posted|published|confirmed)|made public|released to the (?:market|exchange))\b",
    re.I,
)
HYPOTHETICAL = re.compile(
    r"\b(?:hypothetical|training example|for illustration|suppose|if\s+.{0,60}(?:were|would))\b", re.I
)
NEGATED_EVENT = re.compile(
    r"\b(?:no\s+(?:material\s+|binding\s+)?(?:acquisition|merger|takeover|offer|default|contract termination)|"
    r"(?:did|will|has|have)\s+not\s+(?:sign|acquire|merge)|no\s+price[- ]sensitive\s+(?:event|information)|"
    r"no refinancing\s+(?:was\s+)?(?:proposed|approved)|"
    r"no\s+(?:material\s+)?(?:(?:dividend|distribution)\s+deferral|impairment|coupon increase))\b",
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
        r"\b(?:acqui\w*|takeover|merger|agreement|offer|proposal|deal|sale|disposal|transaction|division|scheme|withdraw\w*)\b",
        re.I,
    ),
    "contract": re.compile(r"\b(?:terminat\w*|contract|customer)\b", re.I),
    "earnings": re.compile(r"\b(?:profit|earnings|revenue|forecast|guidance|EBITDA|outlook)\b", re.I),
    "debt": re.compile(
        r"\b(?:debt|acceleration|default|refinancing|financing|bridge|loan|placement|funding|shortfall)\b", re.I
    ),
    "incident": re.compile(r"\b(?:cyberattack|cyber incident|trial halt|recall)\b", re.I),
    "licence": re.compile(r"\b(?:licen[cs]e|suspend\w*|suspension)\b", re.I),
    "distribution": re.compile(r"\b(?:dividend|distribution|deferr\w*|defer|payment date)\b", re.I),
    "trial": re.compile(r"\b(?:trial|clinical study|unblind\w*|endpoint|readout)\b", re.I),
    "impairment": re.compile(
        r"\b(?:impairment|write[- ]down|recoverable amount|carrying value|non[- ]renewal|the charge)\b", re.I
    ),
    "sustainability": re.compile(
        r"\b(?:correction|miss(?:ed|ing)\s+(?:(?:the|its|bond)\s+)?target|coupon|sustainability|emissions)\b", re.I
    ),
}
BOARD_EVENT = re.compile(
    r"\b(?:the board|management)\s+(?:(?:has|have|had|now)\s+)?"
    r"(?:(?:separately|unanimously|already)\s+)?"
    r"(?:approved|decided|confirmed|ordered|initiated|resolved|deferred|moved)\b",
    re.I,
)
EVENT_REFERENCE = re.compile(
    r"\b(?:the|this|that)\s+(?:(?:bidder|issuer|board|company)[’']s\s+)?(?:price[- ]sensitive\s+)?"
    r"(?:decision|approval|terms|notice|recall|termination|withdrawal|suspension|cancellation|"
    r"finding|information|result|deferral|impairment|write[- ]down|correction|missed target)\b",
    re.I,
)
NON_SUBJECT = re.compile(r"\b(?:from|with|to|by)\s*$|\bcounterparty\s*:\s*$", re.I)
NO_LIVE_EVENT = re.compile(
    r"\b(?:did|does)\s+not\s+relate\s+to\s+(?:any\s+)?live\b"
    r"(?:(?!\b(?:but|however)\b)[^.;\n]){0,140}$",
    re.I,
)


def non_subject(prefix: str) -> bool:
    # a sponsor is the issuer subject of its trial, rather than a counterparty.
    return bool(NON_SUBJECT.search(prefix) and not re.search(r"\bsponsored\s+by\s*$", prefix, re.I))


def comparative_material(match: re.Match) -> bool:
    currencies = [match.group(key).upper().replace("S$", "SGD") for key in ("cost_currency", "profit_currency")]
    profit = Decimal(match.group("profit"))
    return currencies[0] == currencies[1] and profit > 0 and Decimal(match.group("cost")) >= profit * Decimal("0.1")


def non_event_statement(value: str) -> bool:
    actual = re.search(
        r"\b(?:signed|received|served|terminated|accepted|confirmed|approved|decided|forecasts|expects|"
        r"resolved|deferred|missed|unblinded|recognised|recognized|cancelled|canceled|shows|puts)\b",
        value,
        re.I,
    )
    normative = re.search(
        r"\b(?:should|must|generally|in principle|for example|may need|could|might|ordinarily)\b", value, re.I
    )
    query = re.search(r"\b(?:query\s+about\s+whether|asked\s+whether)\b", value, re.I)
    decision = re.search(
        r"\b(?:board|issuer|company)\b[^.;\n]{0,60}\b(?:approved|confirmed|decided|deferred|resolved)\b", value, re.I
    )
    definition = re.search(r"\brecoverable amount\s+is\s+the\s+higher\s+of\b", value, re.I)
    return bool(hypothetical_statement(value) or normative and not actual or query and not decision or definition)


def hypothetical_statement(value: str) -> bool:
    for match in HYPOTHETICAL.finditer(value):
        before = value[: match.start()]
        # a confirmed decision can remain effective even if a separate condition changes.
        concession = match.group().lower().startswith("if") and re.search(r"\beven\s+$", before, re.I)
        confirmed = re.search(r"\b(?:confirmed|decided|resolved|approved|told)\b", before, re.I)
        if concession and confirmed and EVENT.search(before):
            continue
        return True
    return False


def _org_references(
    text: str, units: list[tuple[int, int]]
) -> tuple[list[list[tuple[int, int]]], dict[tuple[int, int], str], list[list[tuple[int, int]]]]:
    orgs = []
    for a, b in units:
        spans = []
        for match in ORG_NAME_RE.finditer(text[a:b]):
            prefix = re.match(r"(?:Singapore|SGX|Catalist)[- ]listed\s+", match.group(), re.I)
            spans.append((a + match.start() + (prefix.end() if prefix else 0), a + match.end()))
        orgs.append(spans)
    identities = {span: canonical_org(text[span[0] : span[1]]) for spans in orgs for span in spans}
    anchors: dict[tuple[str, ...], list[tuple[int, str]]] = {}
    for span, identity in identities.items():
        parts = tuple(re.findall(r"\w+", identity))
        if len(parts) < 2 or any(len(p) < 2 for p in parts[:2]):
            continue
        short = len(parts[0]) >= 5 and parts[0] not in {"singapore", "company", "issuer", "group", "holdings", "listed"}
        for width in range(1 if short else 2, len(parts) + 1):
            anchors.setdefault(parts[:width], []).append((span[1], identity))
    for entries in anchors.values():
        entries.sort()
    ambiguous: list[list[tuple[int, int]]] = [[] for _ in units]
    for frame, (a, b) in enumerate(units):
        qualified = orgs[frame][:]
        qualified_starts = [x for x, _ in qualified]
        tokens = list(re.finditer(r"\b[A-Z][\w’'-]*\b", text[a:b]))
        occupied: set[int] = set()
        for i, token in enumerate(tokens):
            if i in occupied:
                continue
            start = a + token.start()
            owner = bisect_right(qualified_starts, start) - 1
            if owner >= 0 and start < qualified[owner][1]:
                continue
            for width in range(min(6, len(tokens) - i), 0, -1):
                run = tokens[i : i + width]
                if any(not re.fullmatch(r"\s+", text[a + x.end() : a + y.start()]) for x, y in zip(run, run[1:])):
                    continue
                end = a + run[-1].end()
                possessive = text[start:end].endswith(("’s", "'s"))
                if (
                    width == 1
                    and not possessive
                    and not re.match(r"\s+(?:missed|confirmed|approved|signed|received|deferred)\b", text[end:], re.I)
                ):
                    continue
                if possessive:
                    end -= 2
                key = tuple(re.findall(r"\w+", canonical_org(text[start:end])))
                entries = anchors.get(key, [])
                lo = bisect_left(entries, (max(0, start - 2000), ""))
                hi = bisect_right(entries, (start, "\uffff"))
                eligible = {identity for _, identity in entries[lo:hi]}
                if (
                    eligible
                    and i + width < len(tokens)
                    and re.fullmatch(r"\s+", text[a + run[-1].end() : a + tokens[i + width].start()])
                ):
                    ambiguous[frame].append((start, a + tokens[i + width].end()))
                    occupied.update(range(i, i + width + 1))
                    break
                if len(eligible) == 1:
                    span = (start, end)
                    orgs[frame].append(span)
                    identities[span] = next(iter(eligible))
                    occupied.update(range(i, i + width))
                    break
                if eligible:
                    ambiguous[frame].append((start, end))
                    occupied.update(range(i, i + width))
                    break
        orgs[frame] = sorted(set(orgs[frame]))
    return orgs, identities, ambiguous


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
    index = bisect_right(sentences, (position, len(text) + 1)) - 1
    if index >= 0:
        a, b = sentences[index]
        if a <= position < b:
            return max(a, position - 1600), min(b, position + 1600)
    return position, position


def _item(text: str, a: int, b: int, kind: str) -> dict:
    return {"kind": kind, "start_char": a, "end_char": b, "matched_text": text[a:b]}


def contextual_mnpi(text: str, findings: list[Any]) -> dict:
    units = [(u.start_char, u.end_char) for u in parse_document_structure(text).units if u.kind != "document"]
    if not units:
        return {"state": "not_detected", "evidence": [], "public_status_verified": False, "reason": "no event evidence"}
    starts = [a for a, _ in units]
    sentences = [_sentences(text, a, b) for a, b in units]
    orgs, identities, ambiguous = _org_references(text, units)
    private_matches = list(NONPUBLIC.finditer(text))
    private_starts = [p.start() for p in private_matches]
    public_matches = []
    for match in PUBLIC.finditer(text):
        preceding = bisect_right(private_starts, match.start()) - 1
        if preceding < 0 or match.start() >= private_matches[preceding].end():
            public_matches.append(match)
    public_starts = [m.start() for m in public_matches]

    def local_orgs(frame: int, lower: int, upper: int) -> list[tuple[int, int]]:
        spans = orgs[frame]
        return spans[bisect_left(spans, (lower, -1)) : bisect_left(spans, (upper, -1))]

    hypotheses = []
    diagnostics = []

    def diagnostic(code: str, start: int, end: int) -> None:
        diagnostics.append({"code": code, **_item(text, start, end, "unresolved_link")})

    unresolved = False
    for private in private_matches:
        index = bisect_right(starts, private.start()) - 1
        if index < 0:
            continue
        a, b = units[index]
        window_start, window_end = max(0, private.start() - 1600), min(len(text), private.end() + 1600)
        if any(
            window_start <= x < private.start() and not non_subject(text[max(a, x - 30) : x])
            for x, _ in ambiguous[index]
        ):
            unresolved = True
            diagnostic("ambiguous_issuer", *private.span())
            continue
        sa, sb = _sentence(text, sentences[index], private.start())
        statement = text[sa:sb]
        if (
            UNRELATED.search(statement)
            or hypothetical_statement(statement)
            or IMMATERIAL.search(statement)
            or NEGATED_EVENT.search(statement)
        ):
            diagnostic("excluded_disclosure_context", sa, sb)
            continue
        topics = _topics(statement)
        previous = []
        if (
            topics
            or EVENT_REFERENCE.search(statement)
            or re.search(r"\b(?:it|this|(?:the|that) notice|both|neither)\b", statement, re.I)
        ):
            for prev in range(max(0, index - 2), index):
                x, y = units[prev]
                x, y = max(x, window_start), min(y, window_end)
                value = text[x:y]
                if (
                    a - y <= 1600
                    and EVENT.search(value)
                    and (_topics(value) & topics or not topics and EVENT_REFERENCE.search(statement))
                    and not UNRELATED.search(value)
                ):
                    previous.append(prev)
        indices = previous + [index]
        witness_indices = indices[:]
        if index + 1 < len(units):
            x, y = units[index + 1]
            following = text[x : min(y, window_end)]
            if (
                x - b <= 1600
                and not orgs[index + 1]
                and EVENT_REFERENCE.search(following)
                and (MATERIAL.search(following) or FINANCIAL_CONSEQUENCE.search(following))
                and not UNRELATED.search(following)
            ):
                witness_indices.append(index + 1)
        events = []
        material = []
        for frame in witness_indices:
            x, y = units[frame]
            x, y = max(x, window_start), min(y, window_end)
            for event in EVENT.finditer(text, x, y) if frame in indices else []:
                ea, eb = _sentence(text, sentences[frame], event.start())
                sentence = text[ea:eb]
                reference_only = (
                    any(m.start() <= event.start() < m.end() for m in EVENT_REFERENCE.finditer(text, ea, eb))
                    and not local_orgs(frame, ea, eb)
                    and not ISSUER.search(sentence)
                    and not BOARD_EVENT.search(sentence)
                )
                consequence_only = event.group().casefold() in {
                    "profit",
                    "forecast",
                    "guidance",
                    "earnings",
                    "revenue",
                } and any(m.start() <= event.start() < m.end() for m in FINANCIAL_CONSEQUENCE.finditer(text, ea, eb))
                if (
                    non_event_statement(sentence)
                    or reference_only
                    or consequence_only
                    or NEGATED_EVENT.search(sentence)
                    or IMMATERIAL.search(sentence)
                    or NO_LIVE_EVENT.search(text[max(ea, event.start() - 200) : event.end()])
                ):
                    continue
                events.append((event.start(), event.end()))
            for match in sorted(
                [*MATERIAL.finditer(text, x, y), *FINANCIAL_CONSEQUENCE.finditer(text, x, y)],
                key=lambda match: match.start(),
            ):
                ma, mb = _sentence(text, sentences[frame], match.start())
                if not (
                    IMMATERIAL.search(text[ma:mb])
                    or NEGATED_EVENT.search(text[ma:mb])
                    or non_event_statement(text[ma:mb])
                ):
                    material.append((match.start(), match.end()))
            material.extend(
                (m.start(), m.end())
                for m in QUANT_MATERIAL.finditer(text, x, y)
                if 10 <= float(m.group("pct")) <= 100 and m.end() <= _sentence(text, sentences[frame], m.start())[1]
            )
            material.extend(m.span() for m in COMPARATIVE_COST.finditer(text, x, y) if comparative_material(m))
        if (
            not topics
            and not EVENT_REFERENCE.search(statement)
            and not re.search(r"\b(?:it|this|(?:the|that) notice|both|neither)\b", statement, re.I)
        ):
            unresolved = True
            diagnostic("unlinked_disclosure", sa, sb)
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
            if not events:
                diagnostic("missing_event", sa, sb)
            if not material:
                diagnostic("missing_materiality", sa, sb)
            continue
        private_orgs = local_orgs(index, sa, sb)
        local_events = [e for e in events if sa <= e[0] < sb]
        private_subjects = [
            (x, y)
            for x, y in private_orgs
            if local_events and x < local_events[0][0] and not non_subject(text[max(sa, x - 30) : x])
        ]
        # public statements about the same event conflict unless a later development is explicit.
        conflicting = False
        for pub in public_matches[bisect_left(public_starts, window_start) : bisect_right(public_starts, window_end)]:
            frame = bisect_right(starts, pub.start()) - 1
            if frame not in witness_indices:
                continue
            pa, pb = _sentence(text, sentences[frame], pub.start())
            public_statement = text[pa:pb]
            public_orgs = local_orgs(frame, pa, pb)
            if (
                private_subjects
                and public_orgs
                and not any(
                    identities[(x, y)] == identities[(u, v)] for x, y in private_subjects for u, v in public_orgs
                )
            ):
                continue
            same_topics = bool(_topics(public_statement) & topics) or (
                frame > index and bool(EVENT_REFERENCE.search(public_statement))
            )
            if (pa == sa or same_topics) and not (
                pub.end() < private.start() and TRANSITION.search(text[pub.end() : private.start()])
            ):
                conflicting = True
                break
        if conflicting:
            unresolved = True
            diagnostic("contradictory_public_claim", sa, sb)
            continue
        # an explicit subject in the disclosure sentence cannot borrow another issuer's event.
        event_sentence = _sentence(text, sentences[index], events[-1][0]) if events[-1][0] >= a else None
        if private_orgs and event_sentence != (sa, sb):
            event_orgs = [span for frame in indices for span in local_orgs(frame, window_start, sa)]
            if event_orgs and not any(
                identities[(x, y)] == identities[(u, v)] for x, y in private_orgs for u, v in event_orgs
            ):
                unresolved = True
                diagnostic("issuer_mismatch", sa, sb)
                continue
        issuer: tuple[int, int] | None = None
        named_subjects = [
            (x, y)
            for x, y in private_orgs
            if local_events and x < local_events[0][0] and not non_subject(text[max(sa, x - 30) : x])
        ]
        if named_subjects:
            issuer = named_subjects[0]
        if issuer is None:
            for frame in indices:
                for x, y in local_orgs(frame, window_start, window_end):
                    if non_subject(text[max(units[frame][0], x - 30) : x]):
                        continue
                    issuer = (x, y)
                    break
                if issuer is not None:
                    break
        # an issuer/company reference may inherit a preceding named subject, never a new event.
        if issuer is None and ISSUER.search(
            text[max(window_start, min(units[i][0] for i in indices)) : min(b, window_end)]
        ):
            for prev in range(index - 1, max(-1, index - 5), -1):
                if orgs[prev] and a - units[prev][1] <= 2000:
                    candidates = [
                        (x, y) for x, y in orgs[prev] if not non_subject(text[max(units[prev][0], x - 30) : x])
                    ]
                    if not candidates:
                        continue
                    if len(candidates) == 1:
                        issuer = candidates[0]
                    break
        if issuer is None and BOARD_EVENT.search(text[max(a, window_start) : min(b, window_end)]):
            preceding_orgs = [
                span
                for prev in range(max(0, index - 4), index)
                if a - units[prev][1] <= 2000
                for span in orgs[prev]
                if not non_subject(text[max(units[prev][0], span[0] - 30) : span[0]])
            ]
            if len({identities[span] for span in preceding_orgs}) == 1:
                issuer = preceding_orgs[-1]
        if issuer is None:
            for frame in indices:
                issuer_match = ISSUER.search(text, max(units[frame][0], window_start), min(units[frame][1], window_end))
                if issuer_match:
                    issuer = issuer_match.span()
                    break
        if issuer is None:
            unresolved = True
            diagnostic("missing_issuer", sa, sb)
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
    partial_event = False
    if not resolved_negative:
        for frame, (x, y) in enumerate(units):
            if not (orgs[frame] or ISSUER.search(text, x, y)):
                continue
            for event_match in EVENT.finditer(text, x, y):
                ea, eb = _sentence(text, sentences[frame], event_match.start())
                value = text[ea:eb]
                if non_event_statement(value):
                    continue
                normative = re.search(
                    r"\b(?:should|must|generally|in principle|for example|may need|could|might)\b", value, re.I
                )
                actual = re.search(
                    r"\b(?:signed|received|served|terminated|accepted|confirmed|approved|decided|forecast|expects)\b",
                    value,
                    re.I,
                )
                if EXPANDED_EVENT_WORDS.match(event_match.group()) and not actual:
                    continue
                if not (
                    hypothetical_statement(value)
                    or NEGATED_EVENT.search(value)
                    or IMMATERIAL.search(value)
                    or NO_LIVE_EVENT.search(text[max(ea, event_match.start() - 200) : event_match.end()])
                ) and (not normative or actual):
                    partial_event = True
                    break
        partial_event |= bool(
            re.search(
                r"\b(?:confidential|nonpublic|non-public)\b[^.\n]{0,80}"
                r"(?:financial|SGD|S\$|USD|\$|earnings|revenue)",
                text,
                re.I,
            )
        )
    return {
        "state": "present" if hypotheses else "unknown" if unresolved or partial_event else "not_detected",
        "evidence": hypotheses,
        "diagnostics": diagnostics,
        "public_status_verified": False,
        "reason": "text-claimed event hypotheses; unresolved links and contradictory claims abstain",
    }
