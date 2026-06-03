# SGLB-02 Statute-QA

Version: 0.1-draft. Tracking issue: [#28](https://github.com/gongahkia/junas/issues/28), [#32](https://github.com/gongahkia/junas/issues/32).

## Capability

**C1 — Statute QA.** Given a question grounded in a specific SG statute
section, return the answer and the correct citation.

## Literature anchor

- Guha et al., **LegalBench** (NeurIPS 2023), `rule_qa` and
  `definition_extraction` task families.
- Holzenberger et al., **SARA: A Dataset for Statutory Reasoning in Tax
  Law** (2020, [arXiv:2005.05257](https://arxiv.org/abs/2005.05257)).

## Input contract

```python
case.inputs = {
  "question": str,           # natural-language question
  "act_short_name": str,     # e.g. "PDPA"
  "act_full_name": str,      # e.g. "Personal Data Protection Act 2012"
}
```

## Output contract

Model output is a JSON object:

```json
{
  "answer": "free-form answer, ≤ 200 words",
  "citation": "s 13 of the Personal Data Protection Act 2012"
}
```

## Scoring

- **Citation:** `exact_match` over the canonical section reference,
  after `sal_citation.validate_citation` normalisation. Citation is the
  primary metric.
- **Answer:** ROUGE-L against the gold span extracted from the statute.

## Source provenance

- Adapter: `api.adapters.public.sso.SsoAdapter`.
- Required `extra_schema` fields: `unique_id`, `doc_no`,
  `valid_start_date`, `legis_title`, `fragments_content` (decoded), the
  `data_json` blob.
- Dataset builder selects sections, drafts a question from the section
  heading + content, with the section reference as the citation
  ground truth and the section text as the answer span.

## Limitations

- Question authoring is benchmark-author work; disclose the prompt
  template and audit a 10% sample by hand.
- Statute revisions are versioned (SSO `valid_start_date`); the
  benchmark pins each item to a specific version.
- "Answer" is necessarily abstractive; ROUGE-L is a coarse proxy.
- Excluded statutes: those with extensive subsidiary legislation that
  changes the answer (cross-statute is a separate task).

## v0.1 / v0.2 stratification

- v0.1: ~500 sections from PDPA, Employment Act, ROC 2021, Penal Code.
- v0.2 held-out: ~80 sections from post-2026-Q1 statute amendments.
- Leaderboard reports per-statute breakdowns to surface domain skew.
