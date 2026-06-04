# SGLB-05 Employment-Issue

Version: 0.1-code-shipped (data pending live MOM scraper, [#59](https://github.com/gongahkia/junas/issues/59)). Tracking issues: [#33](https://github.com/gongahkia/junas/issues/33), [#59](https://github.com/gongahkia/junas/issues/59).

## Capability

**C5 — Issue spotting.** Multi-label identification of which Employment
Act / MOM-regulated issues a scenario triggers.

## Literature anchor

- Guha et al., **LegalBench** (NeurIPS 2023), `learned_hands_*` family
  — multi-label legal issue classification.
- Chalkidis et al., **LexGLUE** (ACL 2022), ECtHR Task A multi-label
  scoring protocol.

## Input contract

```python
case.inputs = {
  "scenario": str,   # 100–300-token fact pattern about an employer/employee dispute
}
```

## Output contract

Model output is a JSON list of lowercase snake_case issue labels:

```json
["notice_period_breach", "cpf_non_contribution"]
```

## Scoring

- `multi_label_f1` — reuses the existing strong-tier evaluator;
  leaderboard reports macro-F1, micro-F1, per-class P/R.

## Source provenance

- Adapter: `api.adapters.public.mom.MomAdapter` (issue [#59](https://github.com/gongahkia/junas/issues/59)).
- Required JSONL row schema: `doc_id`, `source_url`, `subsource`
  (`press_release`/`faq`/`advisory`), `title`, `body_plain`,
  `stated_breaches` (list[str], MOM's own labels), `act_references`,
  `subject_organisation`, `pub_date`.
- Dataset builder: `benchmark.dataset_builders.sglb_05`.
  - Filters: drop rows without `doc_id` or `stated_breaches`; drop
    scenarios shorter than 150 chars after redaction.
  - Gold labels = `stated_breaches` normalised to lowercase snake_case
    (deduplicated, order-preserving).
  - Scenario redaction: mask SGD amounts and outcome verbs
    ("MOM imposed", "court fined") so the model can't read the answer
    back. Documented patterns in `backend/benchmark/dataset_builders/sglb_05.py::_REDACTORS`.

## Limitations

- **Data pending live ingest.** v0.1 ships builder + scorer + runner +
  prompt; the case data lands once #59 produces
  `backend/vendor-data/mom/enforcement.jsonl`.
- **Label set constrained to MOM-published categories.** Issues outside
  that taxonomy (e.g. industry-specific obligations) are not in scope.
- **Press-release narratives are summarised** by MOM; the publicly
  available text may not capture every issue that arose.
- **Confidence calibration is not measured;** only label presence.

## v0.1 / v0.2 stratification

- v0.1 (data pending): ~120 scenarios from pre-2026-Q1 MOM press
  releases + FAQs.
- v0.2 held-out: ~30 scenarios from post-2026-Q1.
- Splits assigned deterministically by case-index modulo 10 (80/10/10).
- Per-issue precision/recall reported to surface rare-class performance.

## CHANGELOG

- 0.1-code-shipped (2026-06-04): builder, oracle runner, LLM prompt
  builder, spec. Reuses `multi_label_f1` evaluator. Data lands on
  `make ingest-mom && make build-sglb-05` once #59 ships.
