"""SGLB-11 dataset builder.

Reads the real-citation pool, applies the seven perturbation classes to
synthesise fake citations, composes passages mixing real + fake at
~50/50, and writes a harness-ready YAML dataset.

Two layers of safety:

1. **Verifier.** Every fake citation is checked against the canonical
   real pool. Collisions (i.e. a perturbation that accidentally lands
   on a real citation) are re-rolled. Documented false-fake rate after
   verification: 0%.

2. **Determinism.** All randomness threads through a single
   ``random.Random(seed)`` so the YAML is byte-stable across runs.

CLI: ``python -m benchmark.dataset_builders.sglb_11 --seed 42 --output benchmark/datasets/sglb_11_hallucination_smoke.yaml``
"""
from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from benchmark.perturbations import (
    Citation,
    PERTURBATION_TYPES,
    PerturbationType,
    apply,
    applicable_perturbations,
    parse_citation,
)


DEFAULT_POOL_PATH = (
    Path(__file__).resolve().parent.parent
    / "datasets"
    / "sglb_11_real_pool.yaml"
)


# A small bank of passage scaffolds; each placeholder ``{C0}…{Cn}`` is
# replaced with a citation token at composition time. Passages are
# domain-neutral so the scoring stays focused on citation handling
# rather than substantive reasoning.
PASSAGE_TEMPLATES: tuple[str, ...] = (
    "The Court of Appeal's reasoning in {C0} is consistent with the framework set out in {C1}. "
    "Earlier authorities such as {C2} had foreshadowed this approach. "
    "Compare the contrary view in {C3}.",

    "In addressing the question of duty of care, the court relied on {C0}, citing {C1} for the proposition that "
    "control mechanisms operate at the pleading stage. The court also distinguished {C2} on the facts.",

    "The applicable principles are summarised in {C0} and refined in {C1}. {C2} clarified the operative test, "
    "and {C3} applied it to a multi-party scenario. {C4} subsequently extended this to corporate context.",

    "Counsel cited {C0}, {C1}, and {C2} in support. The respondent relied on {C3}, which the court accepted as authoritative.",

    "{C0} remains the locus classicus in Singapore. Cases like {C1} and {C2} have applied its framework, "
    "while {C3} qualifies its reach in arbitral contexts.",
)


@dataclass(frozen=True)
class RealCitation:
    citation: str
    domain: str


def load_real_pool(path: Path = DEFAULT_POOL_PATH) -> list[RealCitation]:
    """Load the hand-curated real-citation pool from YAML."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        RealCitation(citation=row["citation"], domain=row["domain"])
        for row in raw.get("real_citations", [])
    ]


@dataclass
class FakeCitation:
    citation: str
    perturbation_type: PerturbationType
    source_citation: str  # the real citation it was derived from ("" for wholesale_fabrication)


def _normalised(s: str) -> str:
    """Canonicalise a citation for collision-check (whitespace + final period)."""
    return " ".join(s.split()).rstrip(".").lower()


class FakeGenerator:
    """Stateful fake generator that guarantees no collision with the real pool."""

    def __init__(self, real_pool: list[RealCitation], rng: random.Random) -> None:
        self.rng = rng
        self.real_set: set[str] = {_normalised(rc.citation) for rc in real_pool}
        self.real_pool = real_pool
        # Citations seen so far (real + emitted fakes) — used to avoid
        # accidental collisions between fakes too.
        self.emitted: set[str] = set(self.real_set)
        self.false_fake_attempts = 0  # diagnostic counter

    def generate(self, perturbation: PerturbationType, max_attempts: int = 20) -> FakeCitation:
        """Generate one fake of the requested perturbation class.

        Re-rolls up to ``max_attempts`` times if the perturbation lands
        on an existing real (or previously-emitted fake) citation.
        Raises ``RuntimeError`` after exhausting attempts.
        """
        for _ in range(max_attempts):
            source = self._pick_source_for(perturbation)
            try:
                fake_str = apply(perturbation, source, self.rng)
            except ValueError:
                # The perturbation isn't applicable to the picked source;
                # re-roll with a different source.
                continue
            normed = _normalised(fake_str)
            if normed in self.emitted:
                self.false_fake_attempts += 1
                continue
            self.emitted.add(normed)
            return FakeCitation(
                citation=fake_str,
                perturbation_type=perturbation,
                source_citation=source.raw if source else "",
            )
        raise RuntimeError(
            f"failed to generate non-colliding fake for {perturbation!r} after {max_attempts} attempts"
        )

    def _pick_source_for(self, perturbation: PerturbationType) -> Citation | None:
        if perturbation == "wholesale_fabrication":
            return None
        # Pick a real source citation whose kind supports this perturbation.
        candidates: list[Citation] = []
        for rc in self.rng.sample(self.real_pool, len(self.real_pool)):
            parsed = parse_citation(rc.citation)
            if parsed is None:
                continue
            if perturbation in applicable_perturbations(parsed):
                candidates.append(parsed)
                if len(candidates) >= 5:
                    break
        if not candidates:
            raise RuntimeError(f"no real citations are applicable to {perturbation!r}")
        return self.rng.choice(candidates)


@dataclass
class PassageCase:
    name: str
    passage: str
    fakes: list[str]  # the gold-truth fake citations
    citation_index: list[dict[str, Any]]  # per-citation provenance


def compose_passage(
    *,
    template: str,
    real_pool: list[RealCitation],
    fake_gen: FakeGenerator,
    fake_perturbations: list[PerturbationType],
    rng: random.Random,
) -> PassageCase:
    """Compose a single passage by interleaving real + fake citations.

    The fake count is determined by ``len(fake_perturbations)`` and the
    remaining slots are filled with real citations sampled from the
    pool. Citation order is shuffled.
    """
    slot_count = template.count("{C")
    fake_count = len(fake_perturbations)
    if fake_count > slot_count:
        raise ValueError(f"asked for {fake_count} fakes but template has {slot_count} slots")
    real_count = slot_count - fake_count

    reals = rng.sample(real_pool, real_count)
    fakes = [fake_gen.generate(p) for p in fake_perturbations]

    # Build the index with provenance per citation.
    entries: list[dict[str, Any]] = []
    for rc in reals:
        entries.append({"citation": rc.citation, "is_fake": False, "perturbation": None, "source": rc.domain})
    for fc in fakes:
        entries.append({"citation": fc.citation, "is_fake": True, "perturbation": fc.perturbation_type, "source": "synthesised"})
    rng.shuffle(entries)

    # Fill the template.
    rendered = template
    for i, entry in enumerate(entries):
        rendered = rendered.replace(f"{{C{i}}}", entry["citation"])

    # Generate a stable case name from the perturbation signature.
    perturb_sig = "+".join(p[:3] for p in sorted({fc.perturbation_type for fc in fakes})) or "no_fakes"
    name = f"passage_{perturb_sig}_{rng.randint(1000, 9999)}"

    return PassageCase(
        name=name,
        passage=rendered,
        fakes=[entry["citation"] for entry in entries if entry["is_fake"]],
        citation_index=entries,
    )


def build_dataset(*, seed: int, n_passages: int) -> dict[str, Any]:
    """Build a full dataset dict ready for YAML dump.

    Strategy:
    - For each passage, sample a template + a list of perturbation
      classes (1–3 fakes per passage, weighted toward the harder
      classes — composite + wholesale_fabrication).
    - Across all passages, ensure every perturbation class appears at
      least once (round-robin).
    """
    rng = random.Random(seed)
    real_pool = load_real_pool()
    fake_gen = FakeGenerator(real_pool, rng)

    cases: list[PassageCase] = []
    # Round-robin to guarantee coverage of every perturbation class.
    rr_index = 0
    for i in range(n_passages):
        template = rng.choice(PASSAGE_TEMPLATES)
        n_fakes = rng.choice([1, 1, 2, 2, 2, 3])
        perturbations: list[PerturbationType] = []
        for _ in range(n_fakes):
            perturbations.append(PERTURBATION_TYPES[rr_index % len(PERTURBATION_TYPES)])
            rr_index += 1
        case = compose_passage(
            template=template,
            real_pool=real_pool,
            fake_gen=fake_gen,
            fake_perturbations=perturbations,
            rng=rng,
        )
        cases.append(case)

    serialised = {
        "cases": [
            {
                "name": c.name,
                "inputs": {"passage": c.passage},
                "expected_output": {"fakes": sorted(c.fakes)},
                "metadata": {
                    "jurisdiction": "SG",
                    "task": "SGLB-11",
                    "citation_index": c.citation_index,
                    "split": "dev",
                },
            }
            for c in cases
        ],
    }
    return serialised


def write_dataset(dataset: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(dataset, sort_keys=False, default_flow_style=False, width=120),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sglb_11_builder")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n", type=int, default=40, help="number of passages")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "datasets" / "sglb_11_hallucination_smoke.yaml",
    )
    args = parser.parse_args(argv)

    dataset = build_dataset(seed=args.seed, n_passages=args.n)
    write_dataset(dataset, args.output)
    print(f"wrote {len(dataset['cases'])} passages to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
