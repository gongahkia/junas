"""SGLB-16 Review-Redflag-Recall smoke dataset builder.

Builds deterministic SG contract-review cases by starting from local SG
templates and appending a clean review-clause bundle. Each case plants 3-5
closed-taxonomy defects mechanically and records the injected spans.
"""
from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yaml

from api.services.template_service import LegalTemplate, TEMPLATES, render_template

DATASET_VERSION = "sglb-16-v0.1-smoke"
EXTRACTION_RULE_NAME = "sg_contract_template_defect_injection"
DEFECT_TYPES: tuple[str, ...] = (
    "missing_limitation_of_liability",
    "governing_law_non_singapore",
    "missing_pdpa_data_protection_clause",
    "missing_notice_period",
    "missing_dispute_resolution_clause",
    "missing_termination_clause",
)

REVIEW_CLAUSE_BUNDLE = """

## LIMITATION OF LIABILITY
Each Party's total aggregate liability under this Agreement shall not exceed
the total fees paid or payable in the 12 months before the claim. Neither
Party excludes liability where exclusion is not permitted under Singapore law.

## PERSONAL DATA PROTECTION
Each Party shall comply with the Personal Data Protection Act 2012 when
collecting, using, disclosing, storing, or processing personal data. Where a
Party processes personal data on behalf of the other, it acts as a data
intermediary and shall implement reasonable security arrangements.

## NOTICE PERIOD
Either Party may terminate this Agreement by giving 30 days' written notice,
unless a longer minimum notice period is required by applicable Singapore law.

## DISPUTE RESOLUTION
The Parties shall first attempt to resolve disputes by good-faith negotiation.
If unresolved after 14 days, the dispute shall be referred to mediation in
Singapore, and then to the courts of Singapore unless the Parties agree to
SIAC arbitration.

## TERMINATION
Either Party may terminate this Agreement for material breach if the breach is
not remedied within 14 days after written notice. Termination does not affect
accrued rights or surviving confidentiality, payment, and data-protection
obligations.

## GOVERNING LAW
This Agreement is governed by and construed in accordance with the laws of the
Republic of Singapore. The Parties submit to the non-exclusive jurisdiction of
the Singapore courts.
""".strip()


@dataclass(frozen=True)
class Defect:
    defect_type: str
    span_start: int
    span_end: int

    def as_dict(self) -> dict:
        return {
            "defect_type": self.defect_type,
            "span_start": self.span_start,
            "span_end": self.span_end,
        }


@dataclass(frozen=True)
class Injection:
    defect_type: str
    action: str
    span_start: int
    span_end: int
    source_heading: str

    def as_dict(self) -> dict:
        return {
            "defect_type": self.defect_type,
            "action": self.action,
            "span_start": self.span_start,
            "span_end": self.span_end,
            "source_heading": self.source_heading,
        }


@dataclass(frozen=True)
class Sglb16Case:
    case_id: str
    contract_text: str
    defects: tuple[Defect, ...]
    template_id: str
    template_title: str
    injections: tuple[Injection, ...]
    clean_contract_sha: str
    extraction_rule_sha: str
    split: str

    def as_dict(self) -> dict:
        return {
            "name": self.case_id,
            "extraction_rule_sha": self.extraction_rule_sha,
            "inputs": {"contract_text": self.contract_text},
            "expected_output": {"defects": [defect.as_dict() for defect in self.defects]},
            "metadata": {
                "task": "SGLB-16",
                "split": self.split,
                "jurisdiction": "SG",
                "data_tier": "synthetic",
                "dataset_version": DATASET_VERSION,
                "template_id": self.template_id,
                "template_title": self.template_title,
                "clean_contract_sha": self.clean_contract_sha,
                "defect_taxonomy": list(DEFECT_TYPES),
                "injections": [injection.as_dict() for injection in self.injections],
                "label_provenance": "deterministic-mechanical-defect-injection",
            },
        }


@dataclass
class BuildStats:
    emitted: int = 0
    by_defect: dict[str, int] = field(default_factory=dict)
    by_template: dict[str, int] = field(default_factory=dict)


def rule_sha() -> str:
    payload = Path(__file__).read_bytes()
    return hashlib.sha256(payload).hexdigest()[:12]


def _default_values(template: LegalTemplate) -> dict[str, str]:
    return {variable.name: variable.placeholder for variable in template.variables}


def clean_contract(template: LegalTemplate) -> str:
    rendered = render_template(template, _default_values(template)).strip()
    return f"{rendered}\n\n# SG REVIEW CLAUSES\n\n{REVIEW_CLAUSE_BUNDLE}\n"


def _heading_span(text: str, heading: str) -> tuple[int, int]:
    marker = f"## {heading}\n"
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"heading not found: {heading}")
    next_heading = text.find("\n## ", start + len(marker))
    end = len(text) if next_heading < 0 else next_heading
    return start, end


def _remove_heading(text: str, heading: str, defect_type: str) -> tuple[str, Defect, Injection]:
    start, end = _heading_span(text, heading)
    replacement = text[:start].rstrip() + "\n\n" + text[end:].lstrip()
    defect = Defect(defect_type=defect_type, span_start=start, span_end=start)
    injection = Injection(
        defect_type=defect_type,
        action=f"removed ## {heading} block",
        span_start=start,
        span_end=start,
        source_heading=heading,
    )
    return replacement, defect, injection


def _swap_governing_law(text: str) -> tuple[str, Defect, Injection]:
    heading_start, heading_end = _heading_span(text, "GOVERNING LAW")
    segment = text[heading_start:heading_end]
    match = re.search(r"Republic of Singapore", segment)
    if match is None:
        raise ValueError("Singapore governing-law phrase not found")
    start = heading_start + match.start()
    end = heading_start + match.end()
    planted = "State of New York"
    replacement = text[:start] + planted + text[end:]
    defect = Defect(
        defect_type="governing_law_non_singapore",
        span_start=start,
        span_end=start + len(planted),
    )
    injection = Injection(
        defect_type="governing_law_non_singapore",
        action="replaced Republic of Singapore with State of New York",
        span_start=defect.span_start,
        span_end=defect.span_end,
        source_heading="GOVERNING LAW",
    )
    return replacement, defect, injection


Injector = Callable[[str], tuple[str, Defect, Injection]]


INJECTORS: dict[str, Injector] = {
    "missing_limitation_of_liability": lambda text: _remove_heading(
        text,
        "LIMITATION OF LIABILITY",
        "missing_limitation_of_liability",
    ),
    "governing_law_non_singapore": _swap_governing_law,
    "missing_pdpa_data_protection_clause": lambda text: _remove_heading(
        text,
        "PERSONAL DATA PROTECTION",
        "missing_pdpa_data_protection_clause",
    ),
    "missing_notice_period": lambda text: _remove_heading(
        text,
        "NOTICE PERIOD",
        "missing_notice_period",
    ),
    "missing_dispute_resolution_clause": lambda text: _remove_heading(
        text,
        "DISPUTE RESOLUTION",
        "missing_dispute_resolution_clause",
    ),
    "missing_termination_clause": lambda text: _remove_heading(
        text,
        "TERMINATION",
        "missing_termination_clause",
    ),
}


def _case_id(template_id: str, index: int, defects: list[str]) -> str:
    raw = f"{template_id}:{index}:{','.join(defects)}".encode("utf-8")
    return f"sglb_16_{hashlib.sha256(raw).hexdigest()[:12]}"


def _split(index: int) -> str:
    bucket = index % 10
    if bucket < 8:
        return "train"
    if bucket == 8:
        return "dev"
    return "test"


def _defect_plan(index: int) -> list[str]:
    count = 3 + (index % 3)
    return [DEFECT_TYPES[(index + offset) % len(DEFECT_TYPES)] for offset in range(count)]


def build(n: int = 30, sha: str | None = None) -> tuple[list[Sglb16Case], BuildStats]:
    if n <= 0:
        raise ValueError("n must be positive")
    extraction_sha = sha or rule_sha()
    stats = BuildStats()
    cases: list[Sglb16Case] = []
    for index in range(n):
        template = TEMPLATES[index % len(TEMPLATES)]
        base = clean_contract(template)
        planted = base
        defects: list[Defect] = []
        injections: list[Injection] = []
        defect_types = _defect_plan(index)
        for defect_type in defect_types:
            planted, defect, injection = INJECTORS[defect_type](planted)
            defects.append(defect)
            injections.append(injection)
            stats.by_defect[defect_type] = stats.by_defect.get(defect_type, 0) + 1
        stats.by_template[template.id] = stats.by_template.get(template.id, 0) + 1
        cases.append(
            Sglb16Case(
                case_id=_case_id(template.id, index, defect_types),
                contract_text=planted,
                defects=tuple(defects),
                template_id=template.id,
                template_title=template.title,
                injections=tuple(injections),
                clean_contract_sha=hashlib.sha256(base.encode("utf-8")).hexdigest()[:16],
                extraction_rule_sha=extraction_sha,
                split=_split(index),
            )
        )
    stats.emitted = len(cases)
    return cases, stats


def write_dataset(cases: list[Sglb16Case], output_path: str | Path) -> None:
    if not cases:
        raise ValueError("no cases to write")
    extraction_sha = cases[0].extraction_rule_sha
    payload = {
        "extraction_rules": {EXTRACTION_RULE_NAME: extraction_sha},
        "cases": [case.as_dict() for case in cases],
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build SGLB-16 smoke dataset")
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[1] / "datasets" / "sglb_16_review_redflag.yaml"),
    )
    parser.add_argument("--n", type=int, default=30)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    cases, stats = build(n=args.n)
    write_dataset(cases, args.output)
    print(
        f"wrote {stats.emitted} SGLB-16 cases to {args.output}; "
        f"defects={stats.by_defect}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
