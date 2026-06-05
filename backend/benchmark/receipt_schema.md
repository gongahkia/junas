# Benchmark Receipt Schema

This documents the JSON persisted by `python -m benchmark.cli run --output ...`.

## Top-level fields

| Field | Type | Notes |
|---|---|---|
| `workflow` | string | Registered benchmark task. |
| `dataset` | string | Dataset path used for the run. |
| `evaluators` | array[string] | Requested evaluators. |
| `total_cases` | integer | Number of dataset cases. |
| `started_at` / `finished_at` | string | UTC ISO timestamps. |
| `strict` | boolean | Whether weak evaluators were rejected. |
| `weak_evaluators_used` | array[string] | Weak evaluators used when not strict. |
| `data_tier` | string | `regulator`, `synthetic`, or `mixed`. |
| `provenance` | object | LLM provenance when registered, else `{}`. |
| `per_evaluator_mean` | object | Existing scalar mean map, unchanged. |
| `per_evaluator_bootstrap` | object | New per-evaluator bootstrap confidence interval map. |
| `results` | array[object] | Per-case evaluator results. |

## `per_evaluator_bootstrap`

Each key is an evaluator name. Each value has:

| Field | Type | Notes |
|---|---|---|
| `mean` | number | Mean over successful per-case scores; duplicates `per_evaluator_mean[evaluator]`. |
| `ci_low` | number | Lower 2.5th percentile of bootstrap sample means. |
| `ci_high` | number | Upper 97.5th percentile of bootstrap sample means. |
| `n_bootstrap` | integer | Bootstrap resamples used; `0` only when no successful case scores exist. |
| `seed` | integer | Deterministic seed derived from the evaluator name. |

Bootstrap CIs use 1,000 resamples by default and exclude per-case results
with an `error`, matching `per_evaluator_mean`.

## Schema diff

Before GAP-02:

```json
{
  "per_evaluator_mean": {
    "multi_label_f1": 0.9
  }
}
```

After GAP-02:

```json
{
  "per_evaluator_mean": {
    "multi_label_f1": 0.9
  },
  "per_evaluator_bootstrap": {
    "multi_label_f1": {
      "mean": 0.9,
      "ci_low": 0.8,
      "ci_high": 1.0,
      "n_bootstrap": 1000,
      "seed": 1291020342
    }
  }
}
```

Existing consumers that only read `per_evaluator_mean` do not need a
schema migration. Consumers that display uncertainty should add optional
reads from `per_evaluator_bootstrap`.
