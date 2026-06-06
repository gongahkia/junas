# Contributor Observability (Pydantic Logfire)

Opt-in tracing for benchmark contributors who want to inspect their
own runs. **Off by default. No data leaves your machine unless you set
`LOGFIRE_TOKEN`.**

If you don't care about traces, do nothing — the codebase is unchanged
for you.

## What you get

When enabled, you see spans for:

- `benchmark.run` — workflow, dataset, total_cases, evaluators, strict
- `benchmark.case` — workflow, case_name, evaluators
- `benchmark.task` — per-case task invocation
- `benchmark.evaluator` — evaluator, score, duration_ms, task_duration_ms
- `benchmark.task.error` / `benchmark.evaluator.error` — error_class, duration_ms
- HTTP spans on the FastAPI app (auto-instrumented)

## What we do NOT send

Privacy is enforced at the instrumentation site, not at the SDK. We
deliberately never emit:

- API keys, model names, provider URLs
- Case inputs (raw user-provided text)
- Model outputs (verbatim completions)
- Expected outputs (gold labels)
- Evaluator detail payloads

Only structural metadata (names, scores, durations, error classes).
The harness already writes outputs to receipt JSON (`runs/<task>/`);
that file is the canonical record. Telemetry is for shape and timing,
not content.

## 2-minute setup

```sh
# 1. install the optional extra (your venv, not the repo's runtime deps)
.venv/bin/pip install -e "backend[observability]"

# 2. get a write token from https://pydantic.dev/logfire
#    (free tier; project-scoped)
export LOGFIRE_TOKEN=pylf_v1_us_xxxxxxxxxxxxxxxxxxxx

# 3. run anything — benchmark CLI or the API
cd backend && ../.venv/bin/python -m benchmark.cli run \
  --workflow sglb_01_pdpa_outcome \
  --dataset benchmark/datasets/sglb_01_pdpa.yaml \
  --evaluator exact_match --strict

# 4. open https://logfire.pydantic.dev → your project → live tail
```

## Disabling

`unset LOGFIRE_TOKEN`. The next process starts with telemetry off, no
network calls, no overhead beyond a single env-var lookup.

## CI safety

CI never sets `LOGFIRE_TOKEN`. The `logfire` package is in the
optional `observability` extra, not the runtime deps, so CI doesn't
even install it. If someone leaks a token into a fork's secrets, the
package import still fails closed (logged warning, no traces).

## What this surfaces that the receipt JSON does not

- Wall-clock breakdown task-vs-evaluator (helps identify slow scorers)
- Per-case duration distribution (tail-latency outliers)
- Live progress on long runs (waiting on synth gen? watch the span tree)
- Error class frequencies across runs (regression spotting)

The receipt JSON already records: scores, bootstrap CIs, provenance,
contamination summary, full outputs. Don't duplicate those into
telemetry — read the receipt.

## Verifying it's off

```sh
unset LOGFIRE_TOKEN
.venv/bin/python -c "from api.telemetry import is_enabled, configure; \
  print('enabled:', is_enabled()); print('module:', configure())"
# expected: enabled: False / module: None
```
