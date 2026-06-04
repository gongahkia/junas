# SGLB-01 PDPA-Outcome

Version: 0.1-shipped. Tracking issue: [#27](https://github.com/gongahkia/junas/issues/27), [#32](https://github.com/gongahkia/junas/issues/32).

## Capability

**C4 — Outcome prediction from facts.** Given a redacted fact summary from
a PDPC enforcement decision, predict the obligation breached and the
log-band of the penalty.

## Literature anchor

- Chalkidis et al., **LexGLUE** (ACL 2022), ECtHR Tasks A and B — paired
  multi-label-classification + outcome-prediction protocol on a public
  regulator corpus.
- Aletras et al., **Predicting Judicial Decisions of the European Court
  of Human Rights** (PeerJ CS 2016) — the foundational outcome-prediction
  format we adapt to a domestic SG regulator.

## Input contract

```python
case.inputs = {
  "fact_summary": str,   # redacted PDPC fact pattern, ~30–600 chars after redaction
}
```

## Output contract

Model output is a JSON object:

```json
{
  "obligations": ["protection", "purpose_limitation"],
  "penalty_band": "low"
}
```

`obligations` is a list drawn from the closed PDPC taxonomy:
`consent`, `notification`, `purpose_limitation`, `protection`,
`retention_limitation`, `data_portability`, `dpo`, `dnc`,
`data_intermediary`, `transfer_limitation`, `accountability`, `openness`,
`accuracy`, `access_correction`. Taxonomy in
`backend/data/ingestion/pdpc.py::OBLIGATION_TAXONOMY`.

`penalty_band` is one of `none`, `low`, `mid`, `high` (log-bucketed SGD).
Boundaries (also in `backend/data/ingestion/pdpc.py`):

- `none`: no financial penalty (warning, directions, or no breach).
- `low`: `0 < SGD < 5_000`.
- `mid`: `5_000 <= SGD < 50_000`.
- `high`: `SGD >= 50_000`.

## Scoring

- **Obligations:** `sglb_01_obligations_f1` — multi-label F1 over the
  obligation label set extracted from the model's JSON object output.
- **Penalty band:** `penalty_band_mae` — ordinal MAE on the band index;
  score reported as `1 - mae/3` (so 1.0 is perfect, 0.0 is max-distance
  miss). Raw MAE in evaluator `detail`.
- Leaderboard reports both metrics separately; no composite score.

## Source provenance

- Adapter: `api.adapters.public.pdpc.PdpcAdapter` (scaffold).
- Canonical ingest entry: `backend/data/ingestion/pdpc.py` reads
  `backend/data/raw/pdpc_decisions.xlsx` (vendored from
  `kevanwee/pdpcscraper`, MIT-licensed) and emits:
  - `backend/data/benchmarks/sglb_01_pdpa/{train,dev,test}.jsonl`
  - `backend/benchmark/datasets/sglb_01_pdpa.yaml` (harness-compatible)
- Mechanical extraction:
  - `obligations` → canonicalised from the `Obligations` column of the
    xlsx (PDPC's own published tags).
  - `penalty_band` → derived from the `Financial Penalty` column SGD figure
    using the documented boundaries above.
  - `fact_summary` → PDPC-published `Case Description` with mechanical
    redaction of outcome-leakage (`$X` amounts, "financial penalty",
    "directions were issued", "Click here for more information") to make
    the task non-trivial.

## Limitations

- **Protection-filter bias.** The upstream scraper filters to PDPC's
  "Protection" obligation, so 100% of cases triggered Protection. ~13%
  also tag Accountability; remaining obligations (Consent, Retention,
  Transfer, Purpose Limitation) appear single-digit times. Future
  versions should ingest all-obligation filters.
- **Penalty bands collapse a continuous variable** to four buckets. The
  boundaries are documented and reproducible but the choice is
  benchmark-author. Sensitivity analysis pending.
- **Taxonomy reflects PDPC's own categorisation**, not a normative ground
  truth.
- **Description-as-facts approximation.** The PDPC "Case Description" is
  a summary that historically leaked the outcome; we redact outcome verbs
  and amounts but the model still sees the regulator's framing of what
  the breach was. Pure-fact extraction would require the underlying PDF
  body, which the upstream scraper does not pull.
- **Citation coverage is partial** (~75% have machine-readable PDFs); we
  do not exclude cases lacking citations because the task does not score
  citations.

## v0.1 / v0.2 stratification

Splits assigned mechanically by publication date:

- `train`: `pub_date < 2024-01-01` — 192 cases.
- `dev`: `2024-01-01 <= pub_date < 2026-01-01` — 14 cases.
- `test`: `pub_date >= 2026-01-01` — 5 cases (post-cutoff per coverage
  matrix §4.3; small for v0.1, grows as PDPC publishes new decisions).
- Leaderboard reports both `train`+`dev` and `test` splits separately.
- Models with cutoff dates after 2026-Q1 still report both, with a
  contamination flag.

## CHANGELOG

- 0.1-shipped (2026-06-04): registered as `sglb_01` workflow with oracle
  runner + LLM prompt builder; obligations + penalty band scorers added;
  dataset materialised at 211 cases (192/14/5 train/dev/test).
