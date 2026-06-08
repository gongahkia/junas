# SGLB-14 Statutory-Entailment

Version: 0.1-code-shipped (fixture smoke). Tracking issue:
[#55](https://github.com/gongahkia/junas/issues/55),
[#60](https://github.com/gongahkia/junas/issues/60).

## Capability

**C1 — Statute QA (entailment).** Given a scenario and a named SG
statute clause, classify the entailment relation.

## Literature anchor

- Holzenberger et al., **SARA** (2020,
  [arXiv:2005.05257](https://arxiv.org/abs/2005.05257)) —
  entailment-prompt format for statutory reasoning.
- Bowman et al., **SNLI** (EMNLP 2015) — 3-class entailment baseline.
- Guha et al., **LegalBench** (NeurIPS 2023), `hearsay` and
  `contract_nli` task families.

## Input contract

```python
case.inputs = {
  "statute_section": str,   # e.g. "s 43 of the PDPA"
  "conduct": str,           # worked-example scenario text
}
```

## Output contract

Model output is a JSON object:

```json
{"entailment": "contravenes"}
{"entailment": "complies"}
{"entailment": "indeterminate"}
```

## Scoring

- `sglb_14_entailment_accuracy`: exact match over the 3-label space after
  parsing the JSON object.
- Confusion matrix is a leaderboard/reporting follow-up once a production
  dataset is materialised.

## Source provenance

- Adapter: `PdpcGuidanceAdapter` (PDPC Advisory Guidelines, #60),
  `MomAdapter` (MOM Employment Act FAQs).
- Required `extra_schema` fields:
  `extracted_worked_examples`/`stated_breaches`.
- **The credibility move:** entailment labels are extracted *mechanically*
  from regulator-published worked examples ("In this scenario, the
  organisation would be in breach of section X"). The regulator states
  the entailment; we just reformat.
- The current builder (`benchmark.dataset_builders.sglb_14`) only emits rows
  where PDPC guideline text explicitly says one of:
  `would be in breach of section X`, `would contravene section X`,
  `would not be in breach of section X`, `would comply with section X`, or
  an explicit `would depend` / `cannot be determined` formulation near a
  section reference.
- The source JSONL (`backend/vendor-data/pdpc/guidelines.jsonl`) is generated
  by `make ingest-pdpc-guidelines` and is gitignored. The committed test suite
  uses fixture rows to prove extraction behavior without committing live
  vendor data.

## Limitations

- Regulator worked examples carry implicit normative judgments. We
  document this and let users discount the task if they reject the
  regulator's framing.
- `indeterminate` examples are only emitted when the regulator text itself
  uses dependency/indeterminacy language. We do not infer uncertainty from
  missing facts.
- We run a statute-placeholder ablation (replace section numbers with
  generic tokens) to surface whether models pattern-match on numbers.

## v0.1 / v0.2 stratification

- v0.1 code-shipped: builder, oracle task, prompt builder, evaluator, and
  fixture-backed smoke tests.
- v0.1 data materialisation target: 50-100 PDPC worked examples after live
  `make ingest-pdpc-guidelines` output is available locally.
- v0.2 held-out: ~50 items from post-2026-Q1 PDPC Advisory Guideline
  revisions.
- Statute-placeholder ablation delta reported in the leaderboard.

## CHANGELOG

- 2026-06-08: Code-shipped fixture smoke. Added deterministic PDPC worked
  example extraction, oracle task, prompt builder, strong evaluator, Makefile
  target, and tests. Production dataset remains gated on materialising the
  gitignored PDPC Advisory Guidelines JSONL.
