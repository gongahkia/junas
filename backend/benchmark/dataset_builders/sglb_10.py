"""SGLB-10 Citation-Generation smoke dataset builder.

CommonLII headnotes are not present in the local repo, so v0.1 uses the
existing hand-curated real SG citation pool from SGLB-11 and builds a
deterministic synthetic lookup smoke. This is intentionally marked
synthetic and benchmark-ineligible until a CommonLII-derived dataset lands.
"""
from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from benchmark.dataset_builders.sglb_11 import DEFAULT_POOL_PATH, RealCitation, load_real_pool

DATASET_VERSION = "sglb-10-v0.1-smoke"
EXTRACTION_RULE_NAME = "curated_sg_case_citation_generation"
DEFAULT_N_CASES = 40
SOURCE_POOL_LABEL = "backend/benchmark/datasets/sglb_11_real_pool.yaml"

DOMAIN_FACT_PATTERNS: dict[str, str] = {
    "tort": "A Singapore negligence brief asks for the authority on duty of care, proximity, and policy limits in a civil claim involving the parties named in {case_name}.",
    "contract": "A commercial contract dispute asks for the Singapore authority on interpretation, breach, mistake, or remedies involving the parties named in {case_name}.",
    "equity": "An equitable relief problem asks for the Singapore authority on trusts, fiduciary obligations, or proprietary remedies involving the parties named in {case_name}.",
    "public": "A public-law or statutory-interpretation memorandum asks for the Singapore authority involving the parties named in {case_name}.",
    "criminal": "A criminal-law memorandum asks for the Singapore authority on liability, sentencing, or procedure involving the parties named in {case_name}.",
    "family": "A matrimonial dispute asks for the Singapore authority on ancillary matters, maintenance, or asset division involving the anonymised parties named in {case_name}.",
    "ip": "An intellectual-property dispute asks for the Singapore authority on copyright, patents, or passing off involving the parties named in {case_name}.",
    "company": "A company-law dispute asks for the Singapore authority on shareholder remedies, directors, or insolvency involving the parties named in {case_name}.",
    "procedure": "A civil-procedure or arbitration dispute asks for the Singapore authority on stay, jurisdiction, or enforcement involving the parties named in {case_name}.",
}


@dataclass(frozen=True)
class Sglb10Case:
    case_id: str
    fact_pattern: str
    citation: str
    case_name: str
    domain: str
    source_pool_sha: str
    extraction_rule_sha: str
    split: str
    citation_rank: int = 1

    def as_dict(self) -> dict:
        return {
            "name": self.case_id,
            "extraction_rule_sha": self.extraction_rule_sha,
            "inputs": {"fact_pattern": self.fact_pattern},
            "expected_output": {"citations": [self.citation]},
            "metadata": {
                "task": "SGLB-10",
                "split": self.split,
                "jurisdiction": "SG",
                "data_tier": "synthetic",
                "dataset_version": DATASET_VERSION,
                "case_name": self.case_name,
                "domain": self.domain,
                "source_pool": SOURCE_POOL_LABEL,
                "source_pool_sha": self.source_pool_sha,
                "citation_rank": self.citation_rank,
                "label_provenance": "mechanical-copy-from-curated-real-citation-pool",
                "quality_note": "synthetic lookup smoke; replace with CommonLII headnote-derived fact patterns before publication",
            },
        }


@dataclass
class BuildStats:
    emitted: int = 0
    by_domain: dict[str, int] = field(default_factory=dict)


def rule_sha() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]


def source_pool_sha(pool_path: Path = DEFAULT_POOL_PATH) -> str:
    return hashlib.sha256(pool_path.read_bytes()).hexdigest()[:12]


def _case_name(citation: str) -> str:
    name = citation.split("[", 1)[0].strip()
    return name if name else citation.strip()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _split(index: int) -> str:
    bucket = index % 10
    if bucket < 8:
        return "train"
    if bucket == 8:
        return "dev"
    return "test"


def _fact_pattern(row: RealCitation) -> str:
    case_name = _case_name(row.citation)
    template = DOMAIN_FACT_PATTERNS.get(
        row.domain,
        "A Singapore legal research task asks for the authority involving the parties named in {case_name}.",
    )
    return (
        template.format(case_name=case_name)
        + " Return the most relevant Singapore case citation."
    )


def _eligible_pool(pool: list[RealCitation]) -> list[RealCitation]:
    return [row for row in pool if _case_name(row.citation) != row.citation]


def _select_pool(pool: list[RealCitation], n: int) -> list[RealCitation]:
    by_domain: dict[str, list[RealCitation]] = {}
    for row in pool:
        by_domain.setdefault(row.domain, []).append(row)
    domains = list(by_domain)
    selected: list[RealCitation] = []
    offset = 0
    while len(selected) < n:
        progressed = False
        for domain in domains:
            rows = by_domain[domain]
            if offset >= len(rows):
                continue
            selected.append(rows[offset])
            progressed = True
            if len(selected) == n:
                return selected
        if not progressed:
            break
        offset += 1
    return selected


def build(n: int = DEFAULT_N_CASES, sha: str | None = None) -> tuple[list[Sglb10Case], BuildStats]:
    if n <= 0:
        raise ValueError("n must be positive")
    pool = _eligible_pool(load_real_pool())
    if n > len(pool):
        raise ValueError(f"n={n} exceeds eligible curated pool size {len(pool)}")
    extraction_sha = sha or rule_sha()
    pool_sha = source_pool_sha()
    stats = BuildStats()
    cases: list[Sglb10Case] = []
    for index, row in enumerate(_select_pool(pool, n)):
        case_name = _case_name(row.citation)
        case_id = f"sglb_10_{index:03d}_{_slug(case_name)[:48]}"
        stats.by_domain[row.domain] = stats.by_domain.get(row.domain, 0) + 1
        cases.append(
            Sglb10Case(
                case_id=case_id,
                fact_pattern=_fact_pattern(row),
                citation=row.citation,
                case_name=case_name,
                domain=row.domain,
                source_pool_sha=pool_sha,
                extraction_rule_sha=extraction_sha,
                split=_split(index),
            )
        )
    stats.emitted = len(cases)
    return cases, stats


def write_dataset(cases: list[Sglb10Case], output_path: str | Path) -> None:
    if not cases:
        raise ValueError("no cases to write")
    extraction_sha = cases[0].extraction_rule_sha
    payload = {
        "extraction_rules": {EXTRACTION_RULE_NAME: extraction_sha},
        "cases": [case.as_dict() for case in cases],
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False, width=120),
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build SGLB-10 smoke dataset")
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[1] / "datasets" / "sglb_10_citation_generation_smoke.yaml"),
    )
    parser.add_argument("--n", type=int, default=DEFAULT_N_CASES)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    cases, stats = build(n=args.n)
    write_dataset(cases, args.output)
    print(
        f"wrote {stats.emitted} SGLB-10 cases to {args.output}; "
        f"domains={stats.by_domain}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
