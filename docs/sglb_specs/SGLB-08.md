# SGLB-08 Clause-Tone

Version: 0.1-synthesis-ready. Tracking issue: [#33](https://github.com/gongahkia/junas/issues/33).

## Capability

**C6 (weak proxy) — Drafting under constraints.** Given a contract
clause, classify its negotiation tone.

## Literature anchor

- No strong literature anchor; this is the weakest task in v0.1.
- The label methodology adapts LLM-judge protocols from
  Min et al., **FActScore** (EMNLP 2023) — multi-judge ensemble with
  disclosed agreement metric.

## Input contract

```python
case.inputs = {
  "clause_text": str,   # contract clause body
  "clause_type": str,   # e.g. "force-majeure" — context for the judges
}
```

## Output contract

Model output is a single-element JSON list with one of:

```json
["standard"]
["aggressive"]
["balanced"]
["protective"]
```

## Scoring

- `multi_label_f1` (single-element).
- Leaderboard reports inter-judge Cohen's κ on the labelling stage;
  task is dropped if sustained κ < 0.4 (coverage matrix §8).

## Source provenance

- Adapter: none external. Dataset bootstraps from the SG clause library
  at `backend/api/services/clause_service.py`.
- Labelling: ensemble of ≥3 frontier LLM judges with a fixed prompt;
  label is majority vote; disagreements held out and hand-spot-checked.

## Limitations

- **Subjective by construction.** Clause tone is not in any regulator's
  taxonomy. We disclose this explicitly: SGLB-08 is the only task in
  v0.1 where labels are not mechanically extracted.
- The clause library is benchmark-author drafted; representativeness
  of real-world SG contracts is not asserted.
- Models that themselves use clause-tone reasoning in training may be
  favoured.

## v0.1 / v0.2 stratification

- v0.1: ~300 clauses across 8 clause types.
- v0.2 held-out: 100 clauses authored after the v0.1 release date.
- κ reported per release; task retired if it falls below 0.4 sustained.

## Synthesis pipeline

SGLB-08 may use `benchmark.synthetic` because the target tone is fixed by the
generation instruction. Candidates must be human-reviewed before promotion to
the reviewed dataset, and receipts must be reported under the `synthetic` tier.
