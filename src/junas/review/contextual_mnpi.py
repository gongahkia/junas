"""Conservative text-claimed MNPI hypotheses with local, auditable component evidence."""

from __future__ import annotations

import re
from typing import Any

from junas.review.conjunctive_mnpi import ORG_NAME_RE

ISSUER = re.compile(r"\b(?:listed\s+(?:issuer|company)|the\s+issuer|issuer\s+[A-Z][\w-]*)\b", re.I)
EVENT = re.compile(
    r"\b(?:acqui(?:re|red|res|sition)|merger|scheme of arrangement|takeover|binding agreement|"
    r"earnings|profit|revenue|insolvency|default|trial halt|cyber(?:attack| incident)|"
    r"contract (?:termination|loss)|terminat\w*[^.\n]{0,70}contract|largest[^.\n]{0,50}contract)\b",
    re.I,
)
MATERIAL = re.compile(
    r"\b(?:price[- ]sensitive|material(?:ly)?|largest|controlling stake|all (?:outstanding )?shares|"
    r"(?:4[0-9]|[5-9][0-9]|100)%[^.\n]{0,30}premium)\b",
    re.I,
)
NONPUBLIC = re.compile(
    r"\b(?:not\s+(?:yet\s+)?(?:(?:been|made)\s+)?publicly\s+(?:disclosed|announced|released)|"
    r"(?:has|have|had)\s+not\s+(?:yet\s+)?been\s+(?:publicly\s+)?(?:disclosed|announced)|"
    r"neither[^.\n]{0,100}(?:publicly\s+disclosed|publicly\s+announced)|"
    r"unpublished|not\s+in\s+the\s+public\s+domain|"
    r"announcement\s+(?:is|remains)\s+(?:still\s+)?(?:in\s+)?draft)\b",
    re.I,
)
PUBLIC = re.compile(
    r"\b(?:publicly\s+(?:disclosed|announced|released)|already\s+published|published\s+on\s+SGXNet)\b", re.I
)
HYPOTHETICAL = re.compile(
    r"\b(?:hypothetical|training example|for illustration|suppose|if\s+.{0,60}(?:were|would))\b", re.I
)
NEGATED_EVENT = re.compile(
    r"\b(?:no\s+(?:material\s+)?(?:acquisition|merger|takeover|default|contract termination)|"
    r"(?:did|will|has|have)\s+not\s+(?:sign|acquire|merge)|no\s+price[- ]sensitive\s+(?:event|information))\b",
    re.I,
)
IMMATERIAL = re.compile(r"\b(?:immaterial|not\s+(?:financially\s+)?material|not\s+price[- ]sensitive)\b", re.I)


def _component(match: re.Match, offset: int, kind: str) -> dict:
    return {
        "kind": kind,
        "start_char": offset + match.start(),
        "end_char": offset + match.end(),
        "matched_text": match.group(),
    }


def contextual_mnpi(text: str, findings: list[Any]) -> dict:
    hypotheses = []
    unresolved = False
    resolved_negative = False
    for block in re.finditer(r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*", text):
        value = block.group()
        # a blank line bounds linkage; event and disclosure in different paragraphs abstain.
        issuer = ORG_NAME_RE.search(value) or ISSUER.search(value)
        event, material, private = EVENT.search(value), MATERIAL.search(value), NONPUBLIC.search(value)
        if not event:
            continue
        public = [
            m
            for m in PUBLIC.finditer(value)
            if not any(n.start() <= m.start() and m.end() <= n.end() for n in NONPUBLIC.finditer(value))
        ]
        hypothetical, negated, immaterial = (
            HYPOTHETICAL.search(value),
            NEGATED_EVENT.search(value),
            IMMATERIAL.search(value),
        )
        components = [
            _component(m, block.start(), kind)
            for m, kind in (
                (issuer, "issuer"),
                (event, "event"),
                (material, "materiality"),
                (private, "claimed_nonpublic"),
            )
            if m
        ]
        if hypothetical or negated or immaterial:
            # mixed actual/hypothetical assertions require further context.
            if re.search(r"\b(?:but|however|actually|in fact)\b", value, re.I):
                unresolved = True
            else:
                resolved_negative = True
            continue
        if private and event:
            sentence_start = max(value.rfind(". ", 0, private.start()), value.rfind(";", 0, private.start())) + 1
            prefix = value[sentence_start : private.start()]
            other_issuers = [m for m in ORG_NAME_RE.finditer(prefix) if issuer and m.group() != issuer.group()]
            same_sentence = event.start() >= sentence_start
            reference = re.search(
                r"\b(?:it|this|agreement|deal|event|transaction|information|offer price|"
                r"termination|results|announcement)\b",
                prefix,
                re.I,
            )
            unrelated = re.search(r"\b(?:unrelated|separate|different|another)\b", prefix, re.I)
            if other_issuers or unrelated or not (same_sentence or reference):
                unresolved = True
                continue
        if issuer and event and material and private and not public:
            hypotheses.append(
                {
                    "start_char": block.start(),
                    "end_char": block.end(),
                    "matched_text": value,
                    "label": "CONTEXTUAL_MNPI",
                    "rule": "contextual_mnpi",
                    "reason": "locally linked issuer event with explicit materiality and nonpublic claim",
                    "components": components,
                    "public_status_verified": False,
                }
            )
        elif public and not private:
            resolved_negative = True
            continue
        else:
            unresolved = True
    return {
        "state": "present"
        if hypotheses
        else "unknown"
        if unresolved or (not resolved_negative and any(f.category == "MNPI" for f in findings))
        else "not_detected",
        "evidence": hypotheses,
        "public_status_verified": False,
        "reason": "text-claimed hypotheses; unresolved linkage, materiality or disclosure remains unknown",
    }
