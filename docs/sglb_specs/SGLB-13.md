# SGLB-13 Counterfactual-Outcome

Version: 0.1-draft. Tracking issue: [#54](https://github.com/gongahkia/junas/issues/54).

## Capability

**C4 — Outcome prediction (counterfactual).** Given two near-identical
PDPC fact patterns differing in one legally-relevant atomic fact,
predict whether the outcome changes.

## Literature anchor

- Guha et al., **LegalBench** (NeurIPS 2023), `mpc` (minimal-pair
  changes) methodology.
- Kaushik et al., **Learning the Difference that Makes a Difference**
  (ICLR 2020, [arXiv:1909.12434](https://arxiv.org/abs/1909.12434)).

## Input contract

```python
case.inputs = {
  "fact_pattern_a": str,
  "fact_pattern_b": str,   # differs from A in one documented fact
}
```

## Output contract

Model output is a JSON object with the prediction and a justification:

```json
{
  "verdict": "different_outcome",
  "justification": "Encryption status was the determinative fact..."
}
```

`verdict` ∈ {`same_outcome`, `different_outcome`}.

## Scoring

- **Paired accuracy:** both members of a pair must be classified
  correctly. This is the headline metric.
- **Single-side accuracy:** each fact pattern scored independently
  (lenient).
- **Justification grounding:** a secondary LLM-judge checks whether the
  justification cites the perturbed fact (anti-shortcut metric).

## Source provenance

- Adapter: `PdpcAdapter`.
- Required: PDPC decisions where the regulator's own published reasoning
  states the counterfactual ("had the company encrypted the data, no
  breach would have occurred").
- Filter: only decisions with explicit counterfactual reasoning enter
  the dataset.

## Limitations

- Perturbations restricted to single-issue changes; multi-fact
  perturbations deferred to v0.3.
- "Same outcome" perturbations may be uninformative if the perturbed
  fact is legally trivial; the designer is drawn from a curated list
  of legally-relevant-but-not-determinative facts (company size,
  industry sector).
- PDPC's counterfactual reasoning may itself be a regulatory tendency
  rather than a legal rule; we disclose this in the spec.

## v0.1 / v0.2 stratification

- v0.1: ~120 pairs (240 items).
- v0.2 held-out: ~30 pairs from post-2026-Q1 decisions.
- ≥30% of pairs hand-audited by an SG-law-trained reviewer pre-launch.
