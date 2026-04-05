# Layer Trigger Strings

Use these sample `text` values with `POST /classify` to exercise each pipeline layer.

To verify a layer actually ran, check `observability.executed_layers` in the response.

## Lexicon (deterministic short-circuit via restricted list)

```text
Acme Corp is preparing an unannounced supplier agreement update for next quarter.
```

Expected behavior: `lexicon.high_risk_short_circuit=true`, which skips non-regression downstream layers.

## Embedding (non-short-circuit baseline)

```text
The company published a routine product roadmap recap after investor day.
```

Expected behavior: `embedding` should appear in `observability.executed_layers` when configured.

## Clustering (anomaly candidate)

```text
Whispered mezzanine covenant unwind with synthetic carry offsets in tranche-zeta.
```

Expected behavior: `clustering` executes if both `embedding` and clustering checkpoint are available.

## Model-1 (risk candidate)

```text
Confidential draft notes next quarter revenue will miss consensus before earnings are announced.
```

Expected behavior: `model1` executes and often returns `label="risk"` on trained checkpoints.

## Model-2 (high-risk candidate; gated by Model-1)

```text
Strictly confidential board memo confirms an unannounced 18% workforce reduction effective next month.
```

Expected behavior: `model2` only executes if `model1.label="risk"`.

## Mosaic (requires `entity_id`)

```text
Preliminary channel checks suggest softer enterprise demand in EMEA next quarter.
```

Send with a stable entity ID (example):

```json
{"text":"Preliminary channel checks suggest softer enterprise demand in EMEA next quarter.","entity_id":"mosaic-demo-entity"}
```

Expected behavior: `mosaic` executes only when the layer is configured and `entity_id` is provided (or inferred from restricted entities).

## Regression (final synthesis)

```text
Internal planning draft indicates delayed launches and lower renewal rates in the upcoming quarter.
```

Expected behavior: `regression` executes when regression artifacts are present, regardless of upstream class.

## Mosaic Escalation String Set (10 unique fragments)

Use the same `entity_id` for each request below; default threshold is 10 unique low-risk fragments in 24h.

```text
Preliminary channel check points to mild EMEA softness in enterprise demand.
Desk notes indicate procurement cycles are stretching modestly in DACH accounts.
Partner feedback suggests slower pilot-to-production conversion this month.
Internal sales pulse shows smaller average seat expansions in large accounts.
Regional update indicates cautious budget pacing in financial services clients.
Early quarter check-in shows deferred upsell conversations in key territories.
Customer success notes highlight longer legal review cycles in renewals.
Field report suggests pipeline quality is stable but deal velocity is lower.
Team summary indicates enterprise win rates are holding with longer sales cycles.
Planning memo flags moderate demand softness without immediate guidance changes.
```

Important: model checkpoints and thresholds can change final labels. Use `observability.executed_layers` and `observability.skipped_layers` as the source of truth for whether a layer was triggered.
