"""SGLB-14 Statutory-Entailment dataset builder.

Reads PDPC Advisory Guidelines JSONL rows emitted by
``data.ingestion.pdpc_guidelines`` and extracts only worked examples where the
regulator text explicitly states the entailment relation:

- ``would be in breach of section X`` / ``would contravene section X`` →
  ``contravenes``
- ``would not be in breach of section X`` / ``would comply with section X`` →
  ``complies``
- ``would depend on`` / ``cannot be determined`` near section X →
  ``indeterminate``

Rows that do not contain explicit worked-example language are dropped. No legal
judgement is used to infer labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

import yaml

from data.ingestion._provenance import extraction_rule_sha

DATASET_VERSION = "sglb-14-v0.1-code-shipped"
EXTRACTION_MODULE = Path(__file__)
EXTRACTION_RULE_NAME = "pdpc_guidance_worked_examples"

_EXAMPLE_MARKER_RE = re.compile(
    r"(?=(?:^|\n|\s)(?:\d{1,2}(?:\.\d{1,2})?\s+)?(?:Example|Illustration)"
    r"(?:(?:\s+\d+[A-Za-z]?)?\s*[:.\-]|\s+\d+[A-Za-z]?\s+|\s+Treatment\b))",
)
_SECTION_RE = re.compile(
    r"(?:section|s\.?)\s+(\d+[A-Z]?(?:\(\d+[A-Z]?\))*)\s+of\s+the\s+PDPA",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_WS_RE = re.compile(r"\s+")

_LABEL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "indeterminate",
        re.compile(
            r"\b(?:whether|if)\b.{0,220}?\b(?:would|will)\s+(?:be\s+)?(?:in\s+)?breach\s+of\s+"
            r"(?P<section>(?:section|s\.?)\s+\d+[A-Z]?(?:\(\d+[A-Z]?\))*\s+of\s+the\s+PDPA)"
            r".{0,220}?\b(?:would\s+depend|depends\s+on|cannot\s+be\s+determined)"
            r"|"
            r"\b(?:would\s+depend|depends\s+on|cannot\s+be\s+determined)\b.{0,220}?"
            r"(?P<section2>(?:section|s\.?)\s+\d+[A-Z]?(?:\(\d+[A-Z]?\))*\s+of\s+the\s+PDPA)",
            re.IGNORECASE,
        ),
    ),
    (
        "complies",
        re.compile(
            r"\b(?:would|will)\s+not\s+(?:be\s+)?(?:(?:in|i\s+n)\s+)?breach\s+of\s+"
            r"(?P<section>(?:section|s\.?)\s+\d+[A-Z]?(?:\(\d+[A-Z]?\))*\s+of\s+the\s+PDPA)"
            r"|"
            r"\b(?:would|will)\s+comply\s+with\s+"
            r"(?P<section2>(?:section|s\.?)\s+\d+[A-Z]?(?:\(\d+[A-Z]?\))*\s+of\s+the\s+PDPA)",
            re.IGNORECASE,
        ),
    ),
    (
        "contravenes",
        re.compile(
            r"\b(?:would|will)\s+(?:be\s+)?(?:(?:in|i\s+n)\s+)?breach\s+of\s+"
            r"(?P<section>(?:section|s\.?)\s+\d+[A-Z]?(?:\(\d+[A-Z]?\))*\s+of\s+the\s+PDPA)"
            r"|"
            r"\b(?:would|will)\s+contravene\s+"
            r"(?P<section2>(?:section|s\.?)\s+\d+[A-Z]?(?:\(\d+[A-Z]?\))*\s+of\s+the\s+PDPA)",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True)
class Sglb14Case:
    case_id: str
    conduct: str
    statute_section: str
    entailment: str
    source_doc_id: str
    source_title: str
    source_url: str
    pdf_url: str
    example_text: str
    matched_sentence: str
    split: str
    pub_date: str
    extraction_rule_sha: str

    def as_dict(self) -> dict:
        return {
            "name": self.case_id,
            "extraction_rule_sha": self.extraction_rule_sha,
            "inputs": {
                "statute_section": self.statute_section,
                "conduct": self.conduct,
            },
            "expected_output": {"entailment": self.entailment},
            "metadata": {
                "task": "SGLB-14",
                "split": self.split,
                "jurisdiction": "SG",
                "source_doc_id": self.source_doc_id,
                "source_title": self.source_title,
                "source_url": self.source_url,
                "pdf_url": self.pdf_url,
                "pub_date": self.pub_date,
                "example_text": self.example_text,
                "matched_sentence": self.matched_sentence,
                "dataset_version": DATASET_VERSION,
                "source_adapter": "api.adapters.public.pdpc_guidance.PdpcGuidanceAdapter",
                "label_provenance": "mechanical-extraction-from-pdpc-guideline-worked-example",
            },
        }


@dataclass
class BuildStats:
    source_rows: int = 0
    examples_seen: int = 0
    emitted: int = 0
    by_split: dict[str, int] = field(default_factory=dict)
    by_label: dict[str, int] = field(default_factory=dict)
    excluded: list[tuple[str, str]] = field(default_factory=list)


def _clean(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").strip())


def _canonical_section(raw: str) -> str:
    match = _SECTION_RE.search(raw or "")
    if not match:
        return ""
    return f"s {match.group(1)} of the PDPA"


def _split_examples(body_plain: str) -> list[str]:
    text = (body_plain or "").replace("\r", "\n")
    parts = [part.strip() for part in _EXAMPLE_MARKER_RE.split(text) if part.strip()]
    return [
        part
        for part in parts
        if re.match(
            r"^(?:\d{1,2}(?:\.\d{1,2})?\s+)?(?:Example|Illustration)"
            r"(?:(?:\s+\d+[A-Za-z]?)?\s*[:.\-]|\s+\d+[A-Za-z]?\s+|\s+Treatment\b)",
            part,
        )
    ]


def _strip_example_prefix(text: str) -> str:
    return re.sub(
        r"^(?:\d{1,2}(?:\.\d{1,2})?\s+)?(?:Example|Illustration)"
        r"(?:(?:\s+\d+[A-Za-z]?)?\s*[:.\-]|\s+\d+[A-Za-z]?\s+|\s+Treatment\b)\s*",
        "",
        text,
    ).strip()


def _sentences(text: str) -> list[str]:
    cleaned = _clean(text)
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(cleaned) if s.strip()]


def _label_match(example: str) -> tuple[str, str, re.Match[str] | None]:
    for label, pattern in _LABEL_PATTERNS:
        match = pattern.search(example)
        if not match:
            continue
        section = _canonical_section(
            match.groupdict().get("section")
            or match.groupdict().get("section2")
            or match.group(0)
        )
        if section:
            return label, section, match
    return "", "", None


def _matched_sentence(example: str, match: re.Match[str]) -> str:
    start, end = match.span()
    for sentence in _sentences(example):
        offset = example.lower().find(sentence.lower())
        if offset <= start and offset + len(sentence) >= end:
            return sentence
    return _clean(match.group(0))


def _conduct_text(example: str, match: re.Match[str]) -> str:
    before = _strip_example_prefix(example[: match.start()])
    if len(_clean(before)) >= 30:
        return _clean(before)
    sentences = [s for s in _sentences(_strip_example_prefix(example)) if match.group(0) not in s]
    if sentences:
        return _clean(sentences[0])
    return _clean(_strip_example_prefix(example))


def extract_cases_from_row(row: dict, rule_sha: str) -> tuple[list[Sglb14Case], list[tuple[str, str]]]:
    doc_id = str(row.get("doc_id") or "").strip()
    title = str(row.get("title") or "").strip()
    body = str(row.get("body_plain") or "")
    examples = _split_examples(body)
    cases: list[Sglb14Case] = []
    excluded: list[tuple[str, str]] = []
    for index, raw_example in enumerate(examples):
        example = _clean(raw_example)
        label, section, match = _label_match(example)
        example_id = f"{doc_id or 'pdpc_guideline'}:{index}"
        if not match:
            excluded.append((example_id, "no explicit entailment phrase"))
            continue
        conduct = _conduct_text(example, match)
        if len(conduct) < 30:
            excluded.append((example_id, "conduct text too short"))
            continue
        case = Sglb14Case(
            case_id=_stable_case_id(doc_id or title, index, section, label),
            conduct=conduct,
            statute_section=section,
            entailment=label,
            source_doc_id=doc_id,
            source_title=title,
            source_url=str(row.get("source_url") or ""),
            pdf_url=str(row.get("pdf_url") or ""),
            example_text=_clean(example),
            matched_sentence=_matched_sentence(example, match),
            split=_assign_split(index),
            pub_date=str(row.get("pub_date") or ""),
            extraction_rule_sha=rule_sha,
        )
        cases.append(case)
    return cases, excluded


def _stable_case_id(doc_id: str, example_index: int, section: str, label: str) -> str:
    raw = f"{doc_id}::{example_index}::{section}::{label}".encode("utf-8")
    return f"sglb_14_{hashlib.sha256(raw).hexdigest()[:12]}"


def _assign_split(idx: int) -> str:
    bucket = idx % 10
    if bucket < 8:
        return "train"
    if bucket == 8:
        return "dev"
    return "test"


def _iter_rows(jsonl_path: Path) -> Iterator[dict]:
    if not jsonl_path.exists():
        raise FileNotFoundError(f"PDPC guidelines JSONL not found: {jsonl_path}")
    with jsonl_path.open(encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def build(jsonl_path: Path, rule_sha: str) -> tuple[list[Sglb14Case], BuildStats]:
    cases: list[Sglb14Case] = []
    stats = BuildStats()
    seen: set[str] = set()
    for row in _iter_rows(jsonl_path):
        stats.source_rows += 1
        row_cases, excluded = extract_cases_from_row(row, rule_sha)
        stats.examples_seen += len(row_cases) + len(excluded)
        stats.excluded.extend(excluded)
        for case in row_cases:
            if case.case_id in seen:
                stats.excluded.append((case.case_id, "duplicate"))
                continue
            seen.add(case.case_id)
            cases.append(case)
            stats.emitted += 1
            stats.by_split[case.split] = stats.by_split.get(case.split, 0) + 1
            stats.by_label[case.entailment] = stats.by_label.get(case.entailment, 0) + 1
    cases.sort(key=lambda c: c.case_id)
    return cases, stats


def write_outputs(cases: Iterable[Sglb14Case], rule_sha: str, yaml_path: Path, jsonl_dir: Path) -> dict[str, int]:
    case_list = list(cases)
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "extraction_rules": {EXTRACTION_RULE_NAME: rule_sha},
        "cases": [case.as_dict() for case in case_list],
    }
    yaml_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False, width=120, allow_unicode=True),
        encoding="utf-8",
    )
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {"train": 0, "dev": 0, "test": 0}
    for split in counts:
        with (jsonl_dir / f"{split}.jsonl").open("w", encoding="utf-8") as fp:
            for case in case_list:
                if case.split != split:
                    continue
                payload = case.as_dict()
                payload["id"] = case.case_id
                fp.write(json.dumps(payload, sort_keys=True) + "\n")
                counts[split] += 1
    return counts


def _default_rule_sha() -> str:
    try:
        return extraction_rule_sha(EXTRACTION_MODULE)
    except Exception:  # noqa: BLE001 — bootstrap before first commit
        return hashlib.sha256(EXTRACTION_MODULE.read_bytes()).hexdigest()[:7]


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(prog="benchmark.dataset_builders.sglb_14")
    parser.add_argument(
        "--input",
        default=str(root / "backend" / "vendor-data" / "pdpc" / "guidelines.jsonl"),
        help="PDPC Advisory Guidelines JSONL produced by data.ingestion.pdpc_guidelines",
    )
    parser.add_argument(
        "--yaml",
        default=str(root / "backend" / "benchmark" / "datasets" / "sglb_14_statutory_entailment.yaml"),
    )
    parser.add_argument(
        "--output",
        default=str(root / "backend" / "data" / "benchmarks" / "sglb_14_statutory_entailment"),
    )
    parser.add_argument("--rule-sha", default="", help="override extraction rule sha")
    args = parser.parse_args(argv)

    rule_sha = args.rule_sha.strip() or _default_rule_sha()
    try:
        cases, stats = build(Path(args.input), rule_sha)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    counts = write_outputs(cases, rule_sha, Path(args.yaml), Path(args.output))
    print(
        json.dumps(
            {
                "source_rows": stats.source_rows,
                "examples_seen": stats.examples_seen,
                "emitted": stats.emitted,
                "by_split": counts,
                "by_label": stats.by_label,
                "excluded": len(stats.excluded),
                "dataset_version": DATASET_VERSION,
                "extraction_rule_sha": rule_sha,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not cases:
        print("warning: no explicit worked examples emitted from input JSONL", file=sys.stderr)
    if stats.excluded:
        print("note: first 5 exclusions: " + json.dumps(stats.excluded[:5]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
