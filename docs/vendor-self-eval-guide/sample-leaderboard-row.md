# Sample leaderboard row

This shows how a receipt is rendered for a vendor-facing leaderboard row. The
numbers below come from the two-case walkthrough fixture in
[sample-receipt.json](sample-receipt.json), not from a real vendor benchmark
submission.

## Markdown row

| Task | Metric | Sample Provider |
|---|---|---|
| SGLB-01 | obligation F1 | 0.50 [0.00, 1.00] |

## Receipt listing

- SGLB-01 obligation F1 / sample-provider: `docs/vendor-self-eval-guide/sample-receipt.json` (`sglb-01-v0.1`)

## Leaderboard JSON cell

```json
{
  "task": "SGLB-01",
  "metric": "obligation F1",
  "evaluator": "sglb_01_obligations_f1",
  "cells": {
    "sample-provider": {
      "mean": 0.5,
      "ci_low": 0.0,
      "ci_high": 1.0,
      "n": 2,
      "receipt": "docs/vendor-self-eval-guide/sample-receipt.json",
      "dataset_version": "sglb-01-v0.1",
      "run_date": "2026-06-06T01:15:04+00:00",
      "model": "sample-provider:sample-model-v1",
      "lower_is_better": false
    }
  }
}
```

For a full submission, each eligible task/metric gets its own row cell, and the
receipt path points at the vendor's full strict-mode receipt under
`runs/baselines/<vendor-or-provider>/<task>/`.
