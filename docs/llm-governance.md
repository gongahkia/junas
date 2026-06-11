# LLM Governance

Kaypoh treats LLM paths as optional advisory layers. The default runtime remains
deterministic-only. Remote LLM use requires tenant opt-in, provider opt-in, and
privacy-ledger evidence.

## Current Promotion State

No `local_distilled` adapter is promoted in this repository state. The canonical
promotion manifest is `training/distillation/promotion_manifest.json`, currently
set to `promoted=false`.

Run the gate:

```sh
uv run python training/distillation/promotion_gate.py \
  --manifest training/distillation/promotion_manifest.json
```

`promoted=false` passes only when no adapter path is configured. `promoted=true`
requires:

- `training/distillation/MODEL_CARD.md`
- a privacy eval JSON with passing checks
- an `eval_against_corpus.py --output-report` JSON report
- an existing adapter directory
- agreement at or above the manifest threshold
- invariant violations at or below the manifest threshold

## Privacy Eval

Promotion requires `structured_tokens` evidence. Remote raw document text is not
accepted as local-adapter promotion evidence. Required privacy checks are:

- `structured_tokens_default`
- `remote_raw_text_blocked`
- `tenant_consent_required`
- `privacy_ledger_recorded`

## Invariant Gate

The student remains advisory. It must not upgrade above the deterministic risk
label, cannot create high-severity findings directly, and must keep structured
mode public-source lists empty. The promotion gate consumes the eval report and
fails if `overall.invariant_violations` exceeds the manifest threshold.

## EU AI Act GPAI Timeline

The European Commission states that GPAI provider obligations entered into
application on 2025-08-02, Commission enforcement powers start on 2026-08-02,
and GPAI models placed on the market before 2025-08-02 must comply by
2027-08-02.

Source: https://digital-strategy.ec.europa.eu/en/policies/guidelines-gpai-providers
