# SGLB-16 Review-Redflag-Recall

Version: 0.1-smoke. Tracking issue: [#57](https://github.com/gongahkia/junas/issues/57).

## Capability

**C7 — Document review.** Given an SG-context contract with
intentionally-planted defects, identify the defects.

## Literature anchor

- Hendrycks et al., **CUAD** (NeurIPS 2021,
  [arXiv:2103.06268](https://arxiv.org/abs/2103.06268)) — planted-issue
  extraction methodology.
- Koreeda & Manning, **ContractNLI** (EMNLP Findings 2021,
  [arXiv:2110.01799](https://arxiv.org/abs/2110.01799)).

## Input contract

```python
case.inputs = {
  "contract_text": str,   # 1500–5000-token SG-context contract
}
```

The model is prompted to review the contract for planted defects and
return span-localised findings from a closed taxonomy.

## Output contract

Model output is a JSON list:

```json
[
  {"defect_type": "governing_law_non_singapore", "span_start": 1542, "span_end": 1559},
  {"defect_type": "missing_notice_period", "span_start": 2140, "span_end": 2140}
]
```

Closed defect taxonomy:

- `missing_limitation_of_liability`
- `governing_law_non_singapore`
- `missing_pdpa_data_protection_clause`
- `missing_notice_period`
- `missing_dispute_resolution_clause`
- `missing_termination_clause`

Missing-clause defects use zero-width spans at the deterministic deletion
anchor. Non-missing defects use the span of the planted problematic text.

## Scoring

- `sglb_16_redflag_f1`: F1 over `(defect_type, span_start, span_end)`
  matches with a +/-10 character tolerance on both span endpoints.
- The evaluator accepts only the closed defect taxonomy and integer spans.

## Source provenance

- Base contracts from `backend/api/services/template_service.py`
  (SG-applicable types).
- A clean SG review-clause bundle is appended before planting so every
  case has deterministic source clauses.
- Defects are planted by deterministic block deletion or phrase
  replacement. Each injection is logged in case metadata.

## Limitations

- Planted defects are by definition unrealistic in distribution.
- The v0.1 smoke set uses appended clean clauses to keep labels
  deterministic, not naturally occurring defects in negotiated contracts.
- Zero-width anchors for missing clauses are easy to score but may be
  unnatural for models that prefer explanatory review comments.
- The defect taxonomy reflects benchmark-author opinion on what is a
  defect; it is documented and open to PR contributions.

## v0.1 / v0.2 stratification

- v0.1 smoke: 30 contracts with 3-5 planted defect instances each.
- v0.2 held-out: ~20 contracts built from new template variations.
- Per-class F1 and per-template-type breakdown.
