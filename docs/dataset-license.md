# Dataset licence

Benchmark datasets under SG-LegalBench (the eval-suite inside this project) are licensed under [Creative Commons Attribution 4.0 International (CC-BY-4.0)](https://creativecommons.org/licenses/by/4.0/).

The codebase (everything outside `backend/benchmark/datasets/` and `runs/baselines/`) is licensed separately under MIT — see `LICENSE` at repo root.

## Why CC-BY-4.0

Matches the dataset licence precedent of LegalBench (Stanford), CUAD (Atticus), and SG-LegalCite. Attribution-only — does not block commercial dataset reuse (the explicit goal: SG legal-tech vendors should be able to use SG-LegalBench in their own internal evaluations and external sales decks), does not force share-alike licence-compat headaches downstream.

Alternatives rejected per `docs/decisions/dr-001-name-and-license.md`:

- **CC-BY-SA-4.0** — share-alike adds friction for benchmark aggregation. A vendor cannot wrap SGLB scores in a closed-source eval dashboard without that dashboard being CC-BY-SA-4.0 too. Defeats the "use us for your evals" thesis.
- **CC-BY-NC-4.0** — non-commercial blocks the very vendor adoption this benchmark targets.
- **CC0** — removes attribution; loses academic citation tracking and credit.

## What "the datasets" covers

The CC-BY-4.0 declaration applies to:

- All YAML files under `backend/benchmark/datasets/sglb_*/`.
- All JSONL files under `backend/data/benchmarks/sglb_*/`.
- All extracted fixture corpora under `backend/tests/fixtures/normalisation/` and `backend/tests/fixtures/sal_style_guide/` (the extracted SAL Style Guide / SLR Style Guide worked examples; not the source PDFs themselves, which remain under their original SAL/SLR Press copyright and are not redistributed).
- The leaderboard JSON + CSV outputs under `runs/leaderboard.*` and `runs/baselines/**.json`.

The CC-BY-4.0 declaration does NOT apply to:

- The source documents we mechanically extract labels from (PDPC enforcement decisions, SSO statute text, MOM publications, court judgments). Those remain under their original government / regulator copyright. Our mechanical extractions are intermediate research artefacts cited back to source; the upstream copyright is unaffected.

## Attribution

When citing the benchmark or reusing the datasets, attribute as:

> SG-LegalBench (Junas), CC-BY-4.0, <repo URL>, accessed YYYY-MM-DD.

A `cite.bib` lands with the v0.1 arXiv preprint (SOLO-8 in Tier 4).

## Provenance

Each dataset row carries `source_url`, `dataset_version`, and (after `NEW-EXTRACT-VERSION` lands) `extraction_rule_sha` so any cited score is reproducible. Per-dataset YAML headers include the CC-BY-4.0 declaration inline:

```yaml
dataset_version: sglb-01-v0.1
license: CC-BY-4.0
license_url: https://creativecommons.org/licenses/by/4.0/
attribution: "SG-LegalBench (Junas)"
```

If a downstream user disagrees with a label, they file via `docs/dispute-process.md` (the dispute process landed via `NEW-DISPUTE-PROCESS`).
