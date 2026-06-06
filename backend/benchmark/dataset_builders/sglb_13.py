"""SGLB-13 Counterfactual-Outcome dataset builder.

Piggybacks on the SGLB-01 PDPC JSONL splits — no new ingest. For each
SGLB-01 case we attempt to generate one counterfactual perturbation by:

1. Locating a *cue clause* in ``fact_summary`` that PDPC's own published
   ``Obligations`` row pins to a specific obligation label (e.g. the
   phrase "appoint a data protection officer" → ``accountability``).
2. Excising that clause to produce a perturbed fact pattern in which
   the obligation X is no longer evidenced.
3. Deriving the gold label ``outcome_changes`` **purely mechanically**
   from PDPC's own obligation count:

       outcome_changes = (len(case.obligations) == 1)

   Rationale: PDPC's published label set is the regulator's stated
   basis for enforcement. If X is the ONLY listed obligation, removing
   the X-fact removes the sole basis → outcome would change. If the
   case has ≥2 listed obligations, the remaining obligations still
   independently ground the same outcome under PDPC's own labelling →
   outcome unchanged.

This satisfies coverage-matrix §4.1 (mechanical-extraction-only): the
gold label is derived from PDPC's own published label count, not from
any author judgement about regulatory tendency. Cases without an
unambiguous cue for *each* breached obligation are dropped (we cannot
guarantee a clean excision otherwise).

Task contract:
  inputs = {"fact_pattern": str, "perturbation": str}
  expected_output = {"outcome_changes": bool}
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

DATASET_VERSION = "sglb-13-v0.1"
EXTRACTION_MODULE = Path(__file__)
EXTRACTION_RULE_NAME = "pdpc_counterfactual"

# Obligation → ordered list of cue patterns. First match wins. Patterns
# are intentionally narrow (PDPC writes verbatim boilerplate across most
# decisions). When two patterns from different obligations match the same
# span we drop the case (ambiguity).
_OBLIGATION_CUES: dict[str, tuple[str, ...]] = {
    "protection": (
        r"failing to put in place reasonable security (?:arrangements|measures)(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"failing to make reasonable security arrangements(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"failing to implement proper and adequate protective measures(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"failing to put in place reasonable measures? to protect(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"did not make reasonable security arrangements(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"did not put in place reasonable security arrangements(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"did not put in place reasonable measures to protect(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
    ),
    "accountability": (
        r"failing to appoint a data protection officer(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"failed to appoint a data protection officer(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"did not appoint a data protection officer(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"failed to develop and implement (?:internal )?data protection policies(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"failing to develop and implement (?:internal )?data protection policies(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"(?:did not|failed to) (?:have|put in place) (?:written )?(?:data protection )?policies and practices(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"failed to put in place data protection policies(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"for not developing and implementing data protection policies(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"the absence of a Data Protection Officer",
        r"absence of a Data Protection Officer",
    ),
    "consent": (
        r"failing to obtain (?:the )?consent(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"did not obtain (?:the )?consent(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"disclosing (?:the )?personal data of [^.]*? without (?:their|the individuals?')? consent",
    ),
    "notification": (
        r"failing to notify[^.]{0,80}?purpose(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"did not notify[^.]{0,80}?purpose(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
    ),
    "retention_limitation": (
        r"did not cease retention(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"failed to cease retention(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"retain(?:ing|ed)? personal data which was no longer necessary(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"holding personal data which was no longer necessary(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"cease retaining data when the purpose of collection no longer exists",
    ),
    "transfer_limitation": (
        r"transferred (?:the )?personal data (?:out of Singapore|overseas)(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
    ),
    "purpose_limitation": (
        r"using personal data not for a purpose that a reasonable person would consider appropriate(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
    ),
    "dnc": (
        r"sen[dt][^.]{0,40}?specified message(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
        r"breach of the Do Not Call(?:[^.,]*?(?=(?:\s+and\b|,|\.|;)))?",
    ),
}


@dataclass
class Sglb13Case:
    case_id: str
    source_case_id: str
    fact_pattern: str
    perturbation: str
    outcome_changes: bool
    perturbed_obligation: str
    source_obligations: list[str]
    cue_span: str
    split: str
    source_citation: str
    source_url: str
    extraction_rule_sha: str

    def as_dict(self) -> dict:
        return {
            "name": self.case_id,
            "extraction_rule_sha": self.extraction_rule_sha,
            "inputs": {
                "fact_pattern": self.fact_pattern,
                "perturbation": self.perturbation,
            },
            "expected_output": {"outcome_changes": self.outcome_changes},
            "metadata": {
                "task": "SGLB-13",
                "split": self.split,
                "jurisdiction": "SG",
                "source_case_id": self.source_case_id,
                "source_citation": self.source_citation,
                "source_url": self.source_url,
                "perturbed_obligation": self.perturbed_obligation,
                "source_obligations": list(self.source_obligations),
                "cue_span": self.cue_span,
                "dataset_version": DATASET_VERSION,
                "label_provenance": "mechanical-derivation-from-pdpc-obligation-count",
            },
        }


@dataclass
class BuildStats:
    sources_seen: int = 0
    emitted: int = 0
    by_split: dict[str, int] = field(default_factory=dict)
    by_label: dict[str, int] = field(default_factory=dict)
    excluded: list[tuple[str, str]] = field(default_factory=list)


def _stable_case_id(source_case_id: str, obligation: str) -> str:
    raw = f"{source_case_id}::{obligation}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:12]
    return f"sglb_13_{digest}"


def _find_cue_span(text: str, obligation: str) -> tuple[str, re.Match[str] | None]:
    for pat in _OBLIGATION_CUES.get(obligation, ()):
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(0), m
    return "", None


_TRAILING_CONJUNCTION_RE = re.compile(
    r"[,;]?\s+(?:and(?:\s+for)?|but|while|however|also|further|additionally|for)\s*[,.]?\s*$",
    flags=re.IGNORECASE,
)
_INNER_DANGLING_AND_RE = re.compile(
    r",\s+and\s*[.,]",
    flags=re.IGNORECASE,
)
_RAGGED_TAIL_RE = re.compile(
    r"\s+for(?:\s+breaches\s+of\s+the\s+PDPA)?\.?\s*$",
    flags=re.IGNORECASE,
)
_LEADING_CONJUNCTION_RE = re.compile(
    r"(?<=[\s,])(?:and|but|or|also|further|additionally|and\s+for|and\s+also)\s+(?=did|failed|for|the\s|to\s)",
    flags=re.IGNORECASE,
)
_DOUBLE_FOR_RE = re.compile(r"\bfor\s+(?:and\s+for|and\s+also)\b", flags=re.IGNORECASE)
_ENUM_ARTIFACT_RE = re.compile(
    r"\b(?:First|Second|Third|Lastly|Finally)\s*,\s*(?=(?:First|Second|Third|Lastly|Finally)\b)",
    flags=re.IGNORECASE,
)


def _apply_perturbation(text: str, match: re.Match[str]) -> str:
    start, end = match.span()
    cleaned = text[:start] + text[end:]
    # collapse "First, Second" artifacts (where the cue between them was excised)
    cleaned = _ENUM_ARTIFACT_RE.sub("", cleaned)
    # collapse "X and for Y" → "X for Y" style joiners left by interior cuts
    cleaned = _DOUBLE_FOR_RE.sub("for", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,;])", r"\1", cleaned)
    # collapse a comma-then-dangling-conjunction-then-punctuation artifact
    cleaned = _INNER_DANGLING_AND_RE.sub(".", cleaned)
    # strip ragged trailing conjunctions left by an end-of-sentence excision
    while True:
        new = _TRAILING_CONJUNCTION_RE.sub(".", cleaned.rstrip()).rstrip()
        if new == cleaned:
            break
        cleaned = new
    cleaned = _RAGGED_TAIL_RE.sub(".", cleaned.rstrip()).rstrip()
    # strip terminal " and ." / " for ." that survived the first pass
    cleaned = re.sub(r"\s+(?:and|for|but)\s*\.\s*$", ".", cleaned, flags=re.IGNORECASE)
    # mid-string: "X and for. Y" / "X for, Y" → "X. Y"
    cleaned = re.sub(r"\s+(?:and\s+for|and|for)\s*\.\s+", ". ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bfor,\s+", "", cleaned, flags=re.IGNORECASE)
    # ensure terminal punctuation
    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned.strip()


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


def _build_for_row(row: dict, split: str, rule_sha: str) -> tuple[list[Sglb13Case], str]:
    """Generate one perturbation per listed obligation in a source case.

    Returns (cases, reason). On any per-row exclusion the cases list is
    empty and reason explains why. Each emitted case targets a distinct
    obligation X and has gold ``outcome_changes = (len(obligations)==1)``
    — i.e. True only when X is the sole basis for breach.
    """
    fact_pattern = str(row.get("inputs", {}).get("fact_summary") or "").strip()
    if not fact_pattern:
        return [], "no fact_summary"
    expected = row.get("expected_output") or {}
    obligations = [str(o).strip().lower() for o in expected.get("obligations") or [] if str(o).strip()]
    if not obligations:
        return [], "no obligations"

    # Verify a cue exists for every listed obligation so each perturbation
    # has visible textual grounding.
    cue_spans: dict[str, tuple[str, re.Match[str]]] = {}
    for o in obligations:
        span, match = _find_cue_span(fact_pattern, o)
        if not match:
            return [], f"no cue for obligation {o!r}"
        cue_spans[o] = (span, match)

    # Reject if any two obligations' cue spans overlap — that means a
    # single excision would remove more than one obligation's fact, and
    # the "outcome unchanged" gold would no longer be supported.
    if len(obligations) >= 2:
        spans_only = sorted((m.span(), o) for o, (_, m) in cue_spans.items())
        for i in range(len(spans_only) - 1):
            (_, e_a), _ = spans_only[i]
            (s_b, _), _ = spans_only[i + 1]
            if e_a > s_b:
                return [], "overlapping cue spans across obligations"

    source_case_id = str(row.get("id") or "")
    if not source_case_id:
        return [], "no source id"
    meta = row.get("metadata") or {}
    outcome_changes = len(obligations) == 1
    cases: list[Sglb13Case] = []
    for target in obligations:
        span, match = cue_spans[target]
        perturbation_text = _apply_perturbation(fact_pattern, match)
        if len(perturbation_text) < 40:
            continue  # too short to be a useful counterfactual
        cases.append(
            Sglb13Case(
                case_id=_stable_case_id(source_case_id, target),
                source_case_id=source_case_id,
                fact_pattern=fact_pattern,
                perturbation=perturbation_text,
                outcome_changes=outcome_changes,
                perturbed_obligation=target,
                source_obligations=list(obligations),
                cue_span=span,
                split=split,
                source_citation=str(meta.get("citation") or ""),
                source_url=str(meta.get("source_url") or ""),
                extraction_rule_sha=rule_sha,
            )
        )
    if not cases:
        return [], "all perturbations too short post-excision"
    return cases, ""


def build(jsonl_dir: Path, rule_sha: str) -> tuple[list[Sglb13Case], BuildStats]:
    cases: list[Sglb13Case] = []
    stats = BuildStats()
    seen_ids: set[str] = set()
    for row, split in _iter_source_rows(jsonl_dir):
        stats.sources_seen += 1
        emitted_cases, reason = _build_for_row(row, split, rule_sha)
        if not emitted_cases:
            stats.excluded.append((str(row.get("id") or "?"), reason))
            continue
        for case in emitted_cases:
            if case.case_id in seen_ids:
                stats.excluded.append((case.case_id, "duplicate"))
                continue
            seen_ids.add(case.case_id)
            cases.append(case)
            stats.emitted += 1
            stats.by_split[case.split] = stats.by_split.get(case.split, 0) + 1
            label_key = "outcome_changes" if case.outcome_changes else "outcome_unchanged"
            stats.by_label[label_key] = stats.by_label.get(label_key, 0) + 1
    cases.sort(key=lambda c: c.case_id)
    return cases, stats


def write_outputs(cases: list[Sglb13Case], rule_sha: str, yaml_path: Path, jsonl_dir: Path) -> dict[str, int]:
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "extraction_rules": {EXTRACTION_RULE_NAME: rule_sha},
        "cases": [c.as_dict() for c in cases],
    }
    yaml_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False, width=120, allow_unicode=True),
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
    parser = argparse.ArgumentParser(prog="benchmark.dataset_builders.sglb_13")
    parser.add_argument(
        "--input-dir",
        default=str(root / "backend" / "data" / "benchmarks" / "sglb_01_pdpa"),
        help="dir holding SGLB-01 {train,dev,test}.jsonl",
    )
    parser.add_argument(
        "--yaml",
        default=str(root / "backend" / "benchmark" / "datasets" / "sglb_13_counterfactual.yaml"),
    )
    parser.add_argument(
        "--output",
        default=str(root / "backend" / "data" / "benchmarks" / "sglb_13_counterfactual"),
    )
    parser.add_argument(
        "--rule-sha",
        default="",
        help="override extraction rule sha (default: derived from git history of this module)",
    )
    args = parser.parse_args(argv)

    rule_sha = args.rule_sha.strip()
    if not rule_sha:
        try:
            from data.ingestion._provenance import extraction_rule_sha
            rule_sha = extraction_rule_sha(EXTRACTION_MODULE)
        except Exception:  # noqa: BLE001 — bootstrap before first commit
            rule_sha = "pending"

    jsonl_dir = Path(args.input_dir)
    if not jsonl_dir.exists():
        print(f"error: input dir not found: {jsonl_dir}", file=sys.stderr)
        return 2

    cases, stats = build(jsonl_dir, rule_sha)
    counts = write_outputs(cases, rule_sha, Path(args.yaml), Path(args.output))
    print(
        json.dumps(
            {
                "sources_seen": stats.sources_seen,
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
    if stats.excluded:
        print(
            "note: first 5 exclusions: "
            + json.dumps(stats.excluded[:5]),
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
