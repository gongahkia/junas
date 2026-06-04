# SGLB-07 Jurisdiction-Routing

Version: 0.1-code-shipped (data pending live CommonLII SG case ingest, [#34](https://github.com/gongahkia/junas/issues/34)). Tracking issues: [#33](https://github.com/gongahkia/junas/issues/33), [#34](https://github.com/gongahkia/junas/issues/34).

## Capability

**C2 — Case-law retrieval / jurisdiction reasoning.** Given a SG legal
question, classify the source-jurisdiction of the controlling authority
an SG court would apply.

## Literature anchor

- Guha et al., **LegalBench** (NeurIPS 2023), `function_of_decision`
  family.
- Common-law commentary on SG courts' use of persuasive UK / AU / HK
  authority is the substantive background; we test the model's ability
  to predict the published court statement, not to opine on it.

## Input contract

```python
case.inputs = {
  "question": str,   # 50–200-token legal question
}
```

## Output contract

Model output is a single-element JSON array drawn from:

```json
["sg_binding"]
["uk_persuasive"]
["au_persuasive"]
["hk_persuasive"]
["not_applicable"]
```

## Scoring

- `multi_label_f1` over the single-element labels list (overall accuracy
  in practice).
- Leaderboard reports per-class P/R.

## Source provenance

- Adapter: `api.adapters.public.commonlii_sg.CommonliiSgAdapter`
  (TOS-clean; supersedes the eLitigation path which is deferred to v0.2
  per #34).
- Required JSONL row schema:
  - `case_id`, `citation`, `court_code` (SGCA/SGHC/SGDC/SGMC/SGSAC),
    `decision_date`, `source_url`, `body_plain`, `question` or
    `catchwords` (used as the question framing).
  - `jurisdiction_statements`: list of dicts pre-extracted by ingestion,
    each `{"label": "uk_persuasive", "quote": "...", "paragraph": int}`.
    The ingestion step uses regex over the judgment body to locate the
    published court statement; this builder never makes the legal
    judgment itself.
- Mechanical extraction rule:
  - Gold label = first statement's `label` when the judgment has
    exactly one source-jurisdiction statement (multi-source cases are
    excluded from v0.1 per spec).
  - Question = trimmed `question` field or `catchwords` fallback.

## Limitations

- **Data pending live ingest.** v0.1 ships builder + scorer + runner +
  prompt; the case data lands once #34 produces
  `backend/vendor-data/sg_cases/judgments.jsonl`.
- **Excludes cases without an explicit source-jurisdiction statement.**
  Where the court applies a principle without naming its provenance,
  the case is out of scope.
- **Persuasive-vs-binding is sometimes contested in the literature;** we
  test the published-court framing, not the academic one.
- **Multi-source cases excluded from v0.1.** UK + AU cited together →
  out of scope. Future work: multi-label variant in v0.2.

## v0.1 / v0.2 stratification

- v0.1 (data pending): ~200 cases.
- v0.2 held-out: ~50 cases from post-2026-Q1 judgments.
- Splits assigned deterministically by case-index modulo 10 (80/10/10).
- Per-source-jurisdiction leaderboard breakdown.

## CHANGELOG

- 0.1-code-shipped (2026-06-04): builder, oracle runner, LLM prompt
  builder, spec. Reuses `multi_label_f1` evaluator. Data lands on
  `make build-sglb-07` once a CommonLII SG case ingester populates
  `vendor-data/sg_cases/judgments.jsonl` (tracked in #34).
