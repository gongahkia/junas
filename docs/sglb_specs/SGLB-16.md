# SGLB-16 Review-Redflag-Recall

Version: 0.1-draft. Tracking issue: [#57](https://github.com/gongahkia/junas/issues/57).

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

The model is prompted: *"Review this contract for issues. For each
issue, identify the clause and the type of issue. Output a JSON list of
`{clause_excerpt, issue_type, severity}`."*

## Output contract

Model output is a JSON list:

```json
[
  {"clause_excerpt": "...", "issue_type": "unlimited-liability", "severity": "high"},
  {"clause_excerpt": "...", "issue_type": "non-sg-governing-law", "severity": "medium"}
]
```

## Scoring

- **Per-defect-class recall:** of N planted defects of class X, how
  many caught.
- **Precision:** of all flagged issues, how many correspond to planted
  defects.
- **Localisation IoU:** the flagged `clause_excerpt` should overlap the
  planted clause's text span (token IoU ≥ 0.5 with rapidfuzz threshold).
- Leaderboard reports per-defect-class F1.

## Source provenance

- Base contracts from `backend/api/services/template_service.py`
  (SG-applicable types). Reviewed pre-planting to be defect-free for
  the 12 planted classes.
- Defect taxonomy (`taxonomy.yaml`): 12 classes covering missing
  governing law, non-SG governing law, unenforceable non-compete,
  unlimited liability, unilateral termination, missing PDPA clause,
  forum-non-conveniens trap, auto-renewal without notice, IP
  assignment overreach, perpetual confidentiality overbroad,
  payment-no-late-interest, arbitration bad seat.
- Each defect class includes a deterministic *trigger* (a regex/AST
  check) that confirms planting succeeded.

## Limitations

- Planted defects are by definition unrealistic in distribution. Real
  contracts have natural defects; we filter base contracts to be
  defect-free for the 12 planted classes, but other natural defects
  may exist and may be flagged as false positives.
- Token-IoU localisation may unfairly punish paraphrased excerpts;
  rapidfuzz threshold disclosed.
- The defect taxonomy reflects benchmark-author opinion on "what is a
  defect"; documented and open to PR contributions.

## v0.1 / v0.2 stratification

- v0.1: ~60 contracts, ~240 planted defect instances.
- v0.2 held-out: ~20 contracts built from new template variations.
- Per-class F1 and per-template-type breakdown.
