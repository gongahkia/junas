"""SGLB-02 Statute-QA dataset builder.

Reads an SSO JSONL (one section per row, schema per ``data.ingestion.sso``)
and emits SGLB-02 cases. Each case asks a natural-language question about
the section heading + content and expects the model to return the
canonical SAL-style citation plus a short answer span.

Inputs (per row): ``section_id``, ``number``, ``name``, ``chapter_number``,
``act_title``, ``text_plain``, ``source_url``, ``version_id``,
``valid_start_date``, ``kind``.

Outputs (per case):
- ``inputs.question`` — natural-language question grounded in the heading
- ``inputs.act_short_name`` — short alias derived from chapter_number
- ``inputs.act_full_name`` — ``act_title``
- ``expected_output.citation`` — canonical SAL-style section reference,
  e.g. ``s 13 of the Personal Data Protection Act 2012``
- ``expected_output.answer_span`` — first sentence/paragraph of the
  section text (gold answer; ROUGE-L target)

Filtering policy:
- Drop ``[Repealed]`` sections.
- Drop sections with ``len(text_plain) < 120`` chars (boilerplate or
  citation-only).
- Drop ``Interpretation`` / ``Definitions`` sections — too long, multiple
  answers, low ROUGE signal.
- Drop sections without an ``act_title`` (unrecoverable citation).

Question template is deliberately mechanical so the methodology section
of the paper can disclose it verbatim.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import yaml

DATASET_VERSION = "sglb-02-v0.1"

# Mapping chapter_number (SSO short code) → short alias surfaced to the model.
# Conservative seed; unknown codes fall back to the code itself.
SHORT_NAMES: dict[str, str] = {
    "PDPA2012": "PDPA",
    "EmA1968": "Employment Act",
    "PC1871": "Penal Code",
    "ROC2021": "Rules of Court 2021",
}

# Section headings to drop (definitions / interpretation / catalogue).
_HEADING_DROP_PATTERNS = (
    re.compile(r"^interpretation\b", re.IGNORECASE),
    re.compile(r"^definitions?\b", re.IGNORECASE),
    re.compile(r"^short title\b", re.IGNORECASE),
    re.compile(r"^citation\b", re.IGNORECASE),
    re.compile(r"^commencement\b", re.IGNORECASE),
    re.compile(r"^application\b", re.IGNORECASE),
)

_MIN_TEXT_LEN = 120
_MAX_ANSWER_CHARS = 600


@dataclass
class Sglb02Case:
    case_id: str
    question: str
    act_short_name: str
    act_full_name: str
    citation: str
    answer_span: str
    chapter_number: str
    section_number: str
    section_heading: str
    source_url: str
    version_id: str
    valid_start_date: str
    split: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.case_id,
            "inputs": {
                "question": self.question,
                "act_short_name": self.act_short_name,
                "act_full_name": self.act_full_name,
            },
            "expected_output": {
                "citation": self.citation,
                "answer_span": self.answer_span,
            },
            "metadata": {
                "task": "SGLB-02",
                "split": self.split,
                "jurisdiction": "SG",
                "chapter_number": self.chapter_number,
                "section_number": self.section_number,
                "section_heading": self.section_heading,
                "source_url": self.source_url,
                "version_id": self.version_id,
                "valid_start_date": self.valid_start_date,
                "dataset_version": DATASET_VERSION,
                "source_adapter": "api.adapters.public.sso.SsoAdapter",
                "label_provenance": "mechanical-extraction-from-sso-section",
            },
        }


def _short_name(chapter_number: str) -> str:
    return SHORT_NAMES.get(chapter_number, chapter_number)


def _is_substantive(section_text: str, section_heading: str) -> bool:
    if not section_text or len(section_text) < _MIN_TEXT_LEN:
        return False
    lowered = section_heading.lower()
    if "[repealed]" in lowered:
        return False
    if any(pat.search(section_heading) for pat in _HEADING_DROP_PATTERNS):
        return False
    return True


def _strip_section_number_prefix(text: str, section_number: str) -> str:
    # SSO bodies open with "13. —(1) ..." or "13. The Commission shall...";
    # strip the leading "N." so the answer reads naturally.
    pattern = re.compile(rf"^{re.escape(section_number)}\.\s*(?:—\s*)?")
    return pattern.sub("", text).strip()


def _first_paragraph(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= _MAX_ANSWER_CHARS:
        return cleaned
    # Cut at the last sentence boundary ≤ max chars.
    cut = cleaned[: _MAX_ANSWER_CHARS + 1]
    last_period = cut.rfind(". ")
    if last_period >= int(_MAX_ANSWER_CHARS * 0.5):
        return cut[: last_period + 1].strip()
    return cleaned[:_MAX_ANSWER_CHARS].rstrip() + "…"


def _question_for(section_heading: str, short_name: str) -> str:
    return f'Under the {short_name}, what does the section on "{section_heading}" provide?'


def _citation_for(short_name: str, full_name: str, section_number: str) -> str:
    if full_name:
        return f"s {section_number} of the {full_name}"
    return f"s {section_number} of the {short_name}"


def _stable_case_id(version_id: str, section_number: str) -> str:
    sid = re.sub(r"[^A-Za-z0-9]+", "_", f"{version_id}:{section_number}").strip("_")
    return f"sglb_02_{sid}"


def _assign_split(idx: int) -> str:
    # Deterministic 80/10/10 split by hash of case_id index — keeps
    # PDPA-only v0.1 reproducible until live SSO ingestion materialises
    # post-cutoff sections.
    bucket = idx % 10
    if bucket < 8:
        return "train"
    if bucket == 8:
        return "dev"
    return "test"


def iter_cases(jsonl_path: Path) -> Iterator[Sglb02Case]:
    if not jsonl_path.exists():
        raise FileNotFoundError(f"SSO JSONL not found: {jsonl_path}")
    idx = 0
    with jsonl_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            heading = str(row.get("name") or "").strip()
            text = str(row.get("text_plain") or "")
            if not _is_substantive(text, heading):
                continue
            chapter = str(row.get("chapter_number") or "").strip()
            number = str(row.get("number") or "").strip()
            full_name = str(row.get("act_title") or "").strip()
            if not chapter or not number or not full_name:
                continue
            short = _short_name(chapter)
            answer = _first_paragraph(_strip_section_number_prefix(text, number))
            if len(answer) < _MIN_TEXT_LEN:
                continue
            version_id = str(row.get("version_id") or "").strip()
            case = Sglb02Case(
                case_id=_stable_case_id(version_id or chapter, number),
                question=_question_for(heading, short),
                act_short_name=short,
                act_full_name=full_name,
                citation=_citation_for(short, full_name, number),
                answer_span=answer,
                chapter_number=chapter,
                section_number=number,
                section_heading=heading,
                source_url=str(row.get("source_url") or ""),
                version_id=version_id,
                valid_start_date=str(row.get("valid_start_date") or ""),
            )
            case.split = _assign_split(idx)
            idx += 1
            yield case


def build(jsonl_path: Path) -> list[Sglb02Case]:
    cases = list(iter_cases(jsonl_path))
    seen: set[str] = set()
    deduped: list[Sglb02Case] = []
    for case in cases:
        if case.case_id in seen:
            continue
        seen.add(case.case_id)
        deduped.append(case)
    deduped.sort(key=lambda c: (c.chapter_number, c.section_number, c.case_id))
    return deduped


def write_yaml(cases: Iterable[Sglb02Case], yaml_path: Path) -> int:
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    case_list = list(cases)
    payload = {"cases": [c.as_dict() for c in case_list]}
    yaml_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False, width=120, allow_unicode=True),
        encoding="utf-8",
    )
    return len(case_list)


def write_jsonl_splits(cases: Iterable[Sglb02Case], output_dir: Path) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    bucket: dict[str, list[Sglb02Case]] = {"train": [], "dev": [], "test": []}
    for case in cases:
        bucket.setdefault(case.split, []).append(case)
    counts: dict[str, int] = {}
    for split, items in bucket.items():
        path = output_dir / f"{split}.jsonl"
        with path.open("w", encoding="utf-8") as fp:
            for case in items:
                # Reuse the same shape as the YAML cases for round-trip.
                payload = case.as_dict()
                payload["id"] = case.case_id
                fp.write(json.dumps(payload, sort_keys=True) + "\n")
        counts[split] = len(items)
    return counts


def main(argv: list[str] | None = None) -> int:
    # __file__ = backend/benchmark/dataset_builders/sglb_02.py → parents[3] = repo root
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(prog="benchmark.dataset_builders.sglb_02")
    parser.add_argument(
        "--input",
        default=str(root / "backend" / "vendor-data" / "sso" / "statutes.jsonl"),
        help="SSO JSONL produced by data.ingestion.sso",
    )
    parser.add_argument(
        "--yaml",
        default=str(root / "backend" / "benchmark" / "datasets" / "sglb_02_statute_qa.yaml"),
        help="harness YAML output path",
    )
    parser.add_argument(
        "--output",
        default=str(root / "backend" / "data" / "benchmarks" / "sglb_02_statute_qa"),
        help="output dir for {train,dev,test}.jsonl",
    )
    args = parser.parse_args(argv)

    cases = build(Path(args.input))
    write_yaml(cases, Path(args.yaml))
    counts = write_jsonl_splits(cases, Path(args.output))
    print(
        json.dumps(
            {
                "total": len(cases),
                "by_split": counts,
                "dataset_version": DATASET_VERSION,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not cases:
        print("warning: no cases emitted; check the input JSONL", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
