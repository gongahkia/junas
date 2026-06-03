# SGLB-01 PDPA-Outcome

Version: 0.1-draft. Tracking issue: [#27](https://github.com/gongahkia/junas/issues/27), [#32](https://github.com/gongahkia/junas/issues/32).

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
  "fact_summary": str,   # redacted PDPC fact pattern, 100–400 tokens
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

`obligations` is a list drawn from the PDPC obligation taxonomy
(Consent, Notification, Purpose Limitation, Protection, Retention,
Data Portability, DPO, DNC, Data Intermediary, Transfer Limitation).
`penalty_band` is one of `none`, `low`, `mid`, `high` (log-bucketed SGD).

## Scoring

- **Obligations:** `multi_label_f1` with `expected_output["labels"]`
  populated from the PDPC published finding.
- **Penalty band:** `exact_match` over the band string.
- Leaderboard reports both metrics separately; no composite score.

## Source provenance

- Adapter: `api.adapters.public.pdpc.PdpcAdapter`.
- Required `extra_schema` fields: `resource_type` ("decision"),
  `dp_obligations` (list[str], directly from PDPC), `decision` (text
  including the penalty), `pub_date`, `file_urls` (for SHA pinning).
- Dataset builder filters to `resource_type == "decision"` and extracts:
  - `obligations` from `dp_obligations`.
  - `penalty_band` by parsing the decision text for SGD figures and
    bucketing on log10.

## Limitations

- Penalty bands collapse a continuous variable to four buckets. The
  bucket boundaries are documented and reproducible but the choice is
  benchmark-author. Disclose explicitly.
- The taxonomy reflects PDPC's published categorisation, not a
  normative ground truth.
- Pre-2020 decisions may use a narrower obligation taxonomy; filter
  documented.

## v0.1 / v0.2 stratification

- v0.1: ~180 decisions, all pre-2026-Q1.
- v0.2 held-out: ~30 decisions, post-2026-Q1.
- Leaderboard reports both splits.
- Models with cutoff dates after 2026-Q1 still report both, with a
  contamination flag.
