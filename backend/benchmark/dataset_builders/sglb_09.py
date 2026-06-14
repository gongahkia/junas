"""SGLB-09 Summary-Faithfulness smoke dataset builder.

Builds a deterministic local scaffold from SGLB-01 PDPC fact summaries.
This is not the paid Azure judge run from PROMPTS-TO-RUN.md; it exists so
the task contract, scorer, prompt builder, and harness wiring are testable
without API keys.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import yaml

DATASET_VERSION = "sglb-09-v0.1-local-scaffold"
EXTRACTION_MODULE = Path(__file__)
EXTRACTION_RULE_NAME = "pdpc_summary_faithfulness_scaffold"
DEFAULT_N_CASES = 20

UNSUPPORTED_FACTS: tuple[str, ...] = (
    "The PDPC awarded damages to affected individuals.",
    "The organisation received a criminal sentence of imprisonment.",
    "The matter was resolved by the Singapore International Arbitration Centre.",
    "The regulator found that no personal data was involved.",
    "The organisation's directors were personally fined by the court.",
)


@dataclass(frozen=True)
class AtomicFact:
    fact: str
    supported: bool

    def as_dict(self) -> dict:
        return {"fact": self.fact, "supported": self.supported}


@dataclass(frozen=True)
class Sglb09Case:
    case_id: str
    source_case_id: str
    source_text: str
    summary: str
    atomic_facts: tuple[AtomicFact, ...]
    variant: str
    split: str
    source_split: str
    source_case_name: str
    source_citation: str
    source_url: str
    extraction_rule_sha: str

    def as_dict(self) -> dict:
        return {
            "name": self.case_id,
            "extraction_rule_sha": self.extraction_rule_sha,
            "inputs": {
                "source_text": self.source_text,
                "summary": self.summary,
            },
            "expected_output": {
                "atomic_facts": [fact.as_dict() for fact in self.atomic_facts],
            },
            "metadata": {
                "task": "SGLB-09",
                "split": self.split,
                "jurisdiction": "SG",
                "data_tier": "synthetic",
                "dataset_version": DATASET_VERSION,
                "source_task": "SGLB-01",
                "source_case_id": self.source_case_id,
                "source_split": self.source_split,
                "source_case_name": self.source_case_name,
                "source_citation": self.source_citation,
                "source_url": self.source_url,
                "variant": self.variant,
                "benchmark_eligible": False,
                "label_provenance": "deterministic-smoke-from-sglb-01-pdpc-fact-summary",
                "quality_note": "local scaffold only; Azure single-judge labels and kappa are pending",
            },
        }


@dataclass
class BuildStats:
    sources_seen: int = 0
    emitted: int = 0
    by_split: dict[str, int] = field(default_factory=dict)
    by_variant: dict[str, int] = field(default_factory=dict)
    excluded: list[tuple[str, str]] = field(default_factory=list)


def _stable_case_id(source_case_id: str, index: int, variant: str) -> str:
    raw = f"{source_case_id}:{index}:{variant}".encode("utf-8")
    return f"sglb_09_{hashlib.sha256(raw).hexdigest()[:12]}"


def _split(index: int) -> str:
    bucket = index % 10
    if bucket < 8:
        return "train"
    if bucket == 8:
        return "dev"
    return "test"


def _variant(index: int) -> str:
    return ("faithful", "mild_hallucination", "wholesale_fabrication")[index % 3]


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _supported_fact(source_text: str) -> str:
    text = _clean_text(source_text)
    first_sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    if first_sentence and len(first_sentence) <= 500:
        return first_sentence
    if len(text) <= 500:
        return text
    boundary = text.rfind(" ", 0, 500)
    return text[: boundary if boundary >= 120 else 500].rstrip(" ,;")


def _unsupported_fact(index: int) -> str:
    return UNSUPPORTED_FACTS[index % len(UNSUPPORTED_FACTS)]


def file_rule_sha() -> str:
    return hashlib.sha256(EXTRACTION_MODULE.read_bytes()).hexdigest()[:12]


def _iter_source_rows(jsonl_dir: Path) -> Iterator[tuple[dict, str]]:
    for split in ("train", "dev", "test"):
        path = jsonl_dir / f"{split}.jsonl"
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line), split
                except json.JSONDecodeError:
                    continue


def _build_case(row: dict, source_split: str, index: int, rule_sha: str) -> tuple[Sglb09Case | None, str]:
    source_text = _clean_text(str(row.get("inputs", {}).get("fact_summary") or ""))
    if not source_text:
        return None, "missing fact_summary"
    source_case_id = str(row.get("id") or "")
    if not source_case_id:
        return None, "missing source id"
    meta = row.get("metadata") or {}
    variant = _variant(index)
    true_fact = _supported_fact(source_text)
    false_fact = _unsupported_fact(index)
    if variant == "faithful":
        summary = true_fact
        atomic_facts = (AtomicFact(true_fact, True),)
    elif variant == "mild_hallucination":
        summary = f"{true_fact} {false_fact}"
        atomic_facts = (AtomicFact(true_fact, True), AtomicFact(false_fact, False))
    else:
        fabricated = (
            f"{meta.get('case_name') or 'The organisation'} was prosecuted in the "
            "criminal courts and its directors were imprisoned."
        )
        summary = fabricated
        atomic_facts = (
            AtomicFact(fabricated, False),
            AtomicFact(_unsupported_fact(index + 1), False),
        )
    split = _split(index)
    return (
        Sglb09Case(
            case_id=_stable_case_id(source_case_id, index, variant),
            source_case_id=source_case_id,
            source_text=source_text,
            summary=summary,
            atomic_facts=atomic_facts,
            variant=variant,
            split=split,
            source_split=source_split,
            source_case_name=str(meta.get("case_name") or ""),
            source_citation=str(meta.get("citation") or ""),
            source_url=str(meta.get("source_url") or ""),
            extraction_rule_sha=rule_sha,
        ),
        "",
    )


def build(jsonl_dir: Path, rule_sha: str, n: int = DEFAULT_N_CASES) -> tuple[list[Sglb09Case], BuildStats]:
    if n <= 0:
        raise ValueError("n must be positive")
    cases: list[Sglb09Case] = []
    stats = BuildStats()
    seen_ids: set[str] = set()
    for row, source_split in _iter_source_rows(jsonl_dir):
        stats.sources_seen += 1
        case, reason = _build_case(row, source_split, len(cases), rule_sha)
        if case is None:
            stats.excluded.append((str(row.get("id") or "?"), reason))
            continue
        if case.case_id in seen_ids:
            stats.excluded.append((case.case_id, "duplicate"))
            continue
        seen_ids.add(case.case_id)
        cases.append(case)
        stats.emitted += 1
        stats.by_split[case.split] = stats.by_split.get(case.split, 0) + 1
        stats.by_variant[case.variant] = stats.by_variant.get(case.variant, 0) + 1
        if len(cases) == n:
            return cases, stats
    raise ValueError(f"only built {len(cases)} SGLB-09 cases from {jsonl_dir}; need {n}")


def write_outputs(cases: list[Sglb09Case], rule_sha: str, yaml_path: Path, jsonl_dir: Path) -> dict[str, int]:
    if not cases:
        raise ValueError("no cases to write")
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "extraction_rules": {EXTRACTION_RULE_NAME: rule_sha},
        "cases": [case.as_dict() for case in cases],
    }
    yaml_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False, width=120, allow_unicode=False),
        encoding="utf-8",
    )
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {"train": 0, "dev": 0, "test": 0}
    for split in counts:
        path = jsonl_dir / f"{split}.jsonl"
        with path.open("w", encoding="utf-8") as fp:
            for case in cases:
                if case.split != split:
                    continue
                obj = case.as_dict()
                obj["id"] = case.case_id
                fp.write(json.dumps(obj, sort_keys=True) + "\n")
                counts[split] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(prog="benchmark.dataset_builders.sglb_09")
    parser.add_argument(
        "--input-dir",
        default=str(root / "backend" / "data" / "benchmarks" / "sglb_01_pdpa"),
        help="dir holding SGLB-01 {train,dev,test}.jsonl",
    )
    parser.add_argument(
        "--yaml",
        default=str(root / "backend" / "benchmark" / "datasets" / "sglb_09_summary_faithfulness.yaml"),
    )
    parser.add_argument(
        "--output",
        default=str(root / "backend" / "data" / "benchmarks" / "sglb_09_summary_faithfulness"),
    )
    parser.add_argument("--n", type=int, default=DEFAULT_N_CASES)
    parser.add_argument("--rule-sha", default="", help="override extraction rule sha")
    args = parser.parse_args(argv)

    rule_sha = args.rule_sha.strip()
    if not rule_sha:
        try:
            from data.ingestion._provenance import extraction_rule_sha
            rule_sha = extraction_rule_sha(EXTRACTION_MODULE)
        except Exception:  # noqa: BLE001
            rule_sha = file_rule_sha()

    jsonl_dir = Path(args.input_dir)
    if not jsonl_dir.exists():
        print(f"error: input dir not found: {jsonl_dir}", file=sys.stderr)
        return 2
    cases, stats = build(jsonl_dir, rule_sha, n=args.n)
    counts = write_outputs(cases, rule_sha, Path(args.yaml), Path(args.output))
    print(
        json.dumps(
            {
                "sources_seen": stats.sources_seen,
                "emitted": stats.emitted,
                "by_split": counts,
                "by_variant": stats.by_variant,
                "excluded": len(stats.excluded),
                "dataset_version": DATASET_VERSION,
                "extraction_rule_sha": rule_sha,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
