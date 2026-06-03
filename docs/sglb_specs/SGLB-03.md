# SGLB-03 Case-Holding

Version: 0.1-draft. Tracking issue: [#34](https://github.com/gongahkia/junas/issues/34), [#32](https://github.com/gongahkia/junas/issues/32).

## Capability

**C2 — Case-law retrieval / reading.** Given a fact pattern and a
question presented, select the correct holding from a multiple-choice
set of distractors drawn from real SG judgments.

## Literature anchor

- Zheng et al., **CaseHOLD: When Does Pretraining Help?** (ICAIL 2021)
  — multiple-choice case-holding methodology.
- Guha et al., **LegalBench** (NeurIPS 2023), `case_holding` task.

## Input contract

```python
case.inputs = {
  "facts": str,
  "question_presented": str,
  "choices": list[str],     # exactly 4 candidate holdings
}
```

## Output contract

Model output is the index of the selected choice as a JSON list:

```json
[2]
```

## Scoring

- **Choice index:** `exact_match` over `expected_output["span"]` set to
  the gold choice index as a string.
- Leaderboard reports accuracy.

## Source provenance

- Adapter: `api.adapters.public.elitigation.ElitigationAdapter` —
  **TOS-gated, currently `benchmark_eligible=False`** until #34 closes.
- Required `extra_schema` fields: `citation`, `body`, `coram`,
  `categories`, `decision_date`.
- Dataset builder extracts holdings from judgment text ("holdings" or
  catchwords sections); distractors drawn from other judgments in the
  same category.
- Fallback if eLitigation TOS does not clear: `CommonliiSgAdapter` for
  the case corpus with reduced N. Document the substitution in the
  release notes.

## Limitations

- Distractor quality matters. Random distractors are too easy; we use
  same-category same-court distractors to keep the task discriminating.
- Holdings are author-extracted from judgment text; a 10% sample is
  hand-audited.
- Multi-issue cases produce multiple holdings; we filter to single-issue
  rulings for v0.1.

## v0.1 / v0.2 stratification

- v0.1: ~250 cases pre-2026-Q1.
- v0.2 held-out: ~50 cases post-2026-Q1.
- Per-court breakdown (SGCA, SGHC, SGDC) in the leaderboard.
