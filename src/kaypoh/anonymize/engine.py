from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from kaypoh.review.entity_linker import canonical_org, canonical_person


PII_RULE_ENTITY_TYPES = {
    "sg_nric_fin": "NRIC_FIN",
    "sg_uen": "UEN",
    "sg_postal_address": "ADDRESS",
    "email_address": "EMAIL",
    "phone_number": "PHONE",
    "passport_number": "PASSPORT",
    "bank_account": "BANK_ACCOUNT",
    "named_person": "PERSON",
}

MNPI_SCALAR_ENTITY_TYPES = {
    "financial_amount": "MONETARY",
    "financial_percentage": "PERCENTAGE",
    "large_number": "NUMBER",
}

NON_REPLACEABLE_RULES = {
    "quasi_identifier_combination",
    "conjunctive_mnpi",
}

SEVERITY_PRIORITY = {"high": 30, "medium": 20, "low": 10}


@dataclass(frozen=True)
class AnonymizationMappingEntry:
    placeholder: str
    entity_type: str
    original_text: str
    occurrence_count: int


@dataclass(frozen=True)
class AnonymizationReplacement:
    finding_id: str
    placeholder: str
    entity_type: str
    original_text: str
    start_char: int
    end_char: int


@dataclass(frozen=True)
class AnonymizationResult:
    anonymized_text: str
    mapping: list[AnonymizationMappingEntry]
    replacements: list[AnonymizationReplacement]


@dataclass(frozen=True)
class _Candidate:
    finding_id: str
    entity_type: str
    original_text: str
    start_char: int
    end_char: int
    priority: int


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _canonicalize(entity_type: str, text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if entity_type in {"EMAIL", "NRIC_FIN", "PASSPORT", "BANK_ACCOUNT", "UEN"}:
        return re.sub(r"[\s-]+", "", cleaned).upper()
    if entity_type == "PHONE":
        digits = re.sub(r"\D+", "", cleaned)
        return digits or cleaned
    if entity_type == "PERSON":
        return canonical_person(cleaned) or cleaned.casefold()
    if entity_type == "ORG":
        return canonical_org(cleaned) or cleaned.casefold()
    if entity_type == "ADDRESS":
        return cleaned.casefold()
    return cleaned


class DeterministicAnonymizer:
    """Build deterministic placeholders from accepted Kaypoh review findings."""

    def __init__(self, *, include_mnpi_scalars: bool = True) -> None:
        self.include_mnpi_scalars = include_mnpi_scalars

    def anonymize(self, *, text: str, findings: list[Any]) -> AnonymizationResult:
        candidates = self._build_candidates(text=text, findings=findings)
        accepted = self._resolve_overlaps(candidates)

        counters: dict[str, int] = {}
        mapping: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()
        replacements: list[AnonymizationReplacement] = []

        for candidate in accepted:
            key = (candidate.entity_type, _canonicalize(candidate.entity_type, candidate.original_text))
            entry = mapping.get(key)
            if entry is None:
                counters[candidate.entity_type] = counters.get(candidate.entity_type, 0) + 1
                entry = {
                    "placeholder": f"[{candidate.entity_type}_{counters[candidate.entity_type]}]",
                    "entity_type": candidate.entity_type,
                    "original_text": candidate.original_text,
                    "occurrence_count": 0,
                }
                mapping[key] = entry

            entry["occurrence_count"] += 1
            replacements.append(
                AnonymizationReplacement(
                    finding_id=candidate.finding_id,
                    placeholder=str(entry["placeholder"]),
                    entity_type=candidate.entity_type,
                    original_text=candidate.original_text,
                    start_char=candidate.start_char,
                    end_char=candidate.end_char,
                )
            )

        anonymized_text = text
        for replacement in sorted(replacements, key=lambda item: item.start_char, reverse=True):
            anonymized_text = (
                anonymized_text[: replacement.start_char]
                + replacement.placeholder
                + anonymized_text[replacement.end_char :]
            )

        return AnonymizationResult(
            anonymized_text=anonymized_text,
            mapping=[
                AnonymizationMappingEntry(
                    placeholder=str(entry["placeholder"]),
                    entity_type=str(entry["entity_type"]),
                    original_text=str(entry["original_text"]),
                    occurrence_count=int(entry["occurrence_count"]),
                )
                for entry in mapping.values()
            ],
            replacements=replacements,
        )

    def _entity_type_for_finding(self, finding: Any) -> str | None:
        category = str(_attr(finding, "category", "")).upper()
        rule = str(_attr(finding, "rule", "")).lower()
        if rule in NON_REPLACEABLE_RULES:
            return None
        if category == "PII":
            return PII_RULE_ENTITY_TYPES.get(rule, rule.upper() if rule else None)
        if self.include_mnpi_scalars and category == "MNPI":
            return MNPI_SCALAR_ENTITY_TYPES.get(rule)
        return None

    def _build_candidates(self, *, text: str, findings: list[Any]) -> list[_Candidate]:
        candidates: list[_Candidate] = []
        for finding in findings:
            entity_type = self._entity_type_for_finding(finding)
            if entity_type is None:
                continue

            start = int(_attr(finding, "start_char", -1))
            end = int(_attr(finding, "end_char", -1))
            if start < 0 or end <= start or end > len(text):
                continue

            original_text = text[start:end]
            if not original_text.strip():
                continue

            category = str(_attr(finding, "category", "")).upper()
            severity = str(_attr(finding, "severity", "")).lower()
            category_priority = 100 if category == "PII" else 50
            priority = category_priority + SEVERITY_PRIORITY.get(severity, 0)

            candidates.append(
                _Candidate(
                    finding_id=str(_attr(finding, "id", "")),
                    entity_type=entity_type,
                    original_text=original_text,
                    start_char=start,
                    end_char=end,
                    priority=priority,
                )
            )
        return candidates

    def _resolve_overlaps(self, candidates: list[_Candidate]) -> list[_Candidate]:
        ordered = sorted(
            candidates,
            key=lambda item: (
                item.start_char,
                -item.priority,
                -(item.end_char - item.start_char),
                item.end_char,
            ),
        )
        accepted: list[_Candidate] = []
        for candidate in ordered:
            if any(
                candidate.start_char < existing.end_char and existing.start_char < candidate.end_char
                for existing in accepted
            ):
                continue
            accepted.append(candidate)
        return sorted(accepted, key=lambda item: (item.start_char, item.end_char))


def reidentify(*, anonymized_text: str, mapping: list[Any]) -> tuple[str, int]:
    """Restore original text in place of placeholders. Sort by placeholder length desc so
    `[PERSON_1]` does not partially match inside `[PERSON_10]`."""
    entries: list[tuple[str, str]] = []
    for entry in mapping:
        placeholder = str(_attr(entry, "placeholder", "") or "")
        original = str(_attr(entry, "original_text", "") or "")
        if placeholder:
            entries.append((placeholder, original))
    entries.sort(key=lambda pair: len(pair[0]), reverse=True)

    text = anonymized_text
    total = 0
    for placeholder, original in entries:
        count = text.count(placeholder)
        if count:
            text = text.replace(placeholder, original)
            total += count
    return text, total
