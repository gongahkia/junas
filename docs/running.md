# Running Noupe

## Prerequisites

- Python 3.10+
- pip
- macOS/Linux

## Setup

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python3 -m spacy download en_core_web_sm
```

For reproducible local installs, the repo also ships pinned lockfiles:

```sh
python -m pip install -r requirements.lock.txt -r requirements-dev.lock.txt
```

`pyproject.toml` is the canonical dependency and tooling definition. `backend.main:app` remains the supported FastAPI entrypoint, but the canonical Python package now lives under `src/noupe/`.

## Bootstrapping Artifacts

Verify or hydrate runtime artifacts from the committed manifest with:

```sh
python3 scripts/bootstrap_artifacts.py
python3 scripts/bootstrap_artifacts.py --sync-from-legacy
```

If you need to regenerate artifacts from the training pipeline:

```sh
python3 scripts/bootstrap_artifacts.py --regenerate
```

The artifact manifest path defaults to `artifacts/manifest.json` and can be overridden with `NOUPE_ARTIFACT_MANIFEST`.

## Preflight

```sh
python3 scripts/preflight.py
```

Use strict mode to fail on warnings:

```sh
python3 scripts/preflight.py --strict
```

For a one-command verification run that executes linting, type checks, the unit suite, and live smoke tests across lexicon, embedding, clustering, model1, model2, regression, and a temporary Redis-backed mosaic flow:

```sh
./scripts/verify_runtime.sh
```

`./scripts/verify_runtime.sh` expects `redis-server` to be available on your `PATH` so it can start an isolated local Redis instance for the mosaic checks.

## Benchmarking Latency

Place benchmark `.txt` inputs in:

```sh
test/fixtures/latency-corpus/
```

Benchmark every `.txt` file in that folder with:

```sh
./scripts/benchmark_latency_corpus.sh
```

Useful variants:

```sh
./scripts/benchmark_latency_corpus.sh --repetitions 10 --warmups 2
./scripts/benchmark_latency_corpus.sh --no-server --url http://127.0.0.1:8000
LATENCY_CORPUS_DIR=/path/to/other/texts ./scripts/benchmark_latency_corpus.sh
```

Outputs are written to `reports/` as:

- `latency_<timestamp>.json`
- `latency_<timestamp>.csv`
- `latency_<timestamp>.txt`

The `.txt` report now includes both the summary table and the per-file detailed run breakdown, including `timings_ms` values for each workflow step returned by the backend.

## Running the API

```sh
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

`backend.main:app` is a compatibility shim that re-exports the canonical app from `noupe.backend.main`.

## Dev Launcher

Run the combined dev launcher with:

```sh
./scripts/launch/run_dev.sh
```

`scripts/launch/run_dev.sh` now:

- asks which frontend(s) to open
- asks which pipeline layers to run with
- starts the backend first
- waits for `GET /ready` to report `ready: true`
- starts a static server rooted at `archive/frontend-demos/` when any demo is selected
- opens the selected frontend URLs only after backend readiness

Frontend choices:

- legacy analyzer only: `http://localhost:8081/legacy/?api=http://localhost:8000`
- chat demo only: `http://localhost:8081/chat/?api=http://localhost:8000`
- all frontends
- backend only

Useful launcher env vars:

- `NOUPE_FRONTENDS=legacy|chat|all|none`
- `PIPELINE_LAYERS=lexicon,embedding,...` to skip the layer prompt and force a specific pipeline
- `NOUPE_PORT` (default `8000`)
- `NOUPE_FRONTEND_DEMO_PORT` (default `8081`)
- `NOUPE_READY_TIMEOUT_SECONDS` (default `180`)
- `NOUPE_LAUNCH_TELEMETRY_FILE` (optional; write startup telemetry JSON after readiness)
- `NOUPE_ALLOW_PARTIAL_START=1` if you intentionally want degraded startup
- `NOUPE_PREFLIGHT_STRICT=0` to relax preflight warnings

Example minimal launcher path:

```sh
PIPELINE_LAYERS=lexicon ./scripts/launch/run_dev.sh
```

When `PIPELINE_LAYERS` is set, `scripts/launch/run_dev.sh` skips the layer-selection prompt and only validates checkpoints for the layers in that active pipeline.

## Backend-Only Launcher

Run the backend without any demo UI:

```sh
./scripts/launch/run_backend_only.sh
```

Useful env vars:

- `NOUPE_PORT` (default `8000`)
- `NOUPE_HOST` (default `0.0.0.0`)
- `NOUPE_LOG_LEVEL` (default `info`)
- `NOUPE_PRETTY_LOGS` (`1` by default; set `NOUPE_PRETTY_LOGS=0` for compact single-line backend JSON logs)
- `NOUPE_BATCH_MAX_CONCURRENCY` (default `min(4, os.cpu_count() or 1)`)
- `NOUPE_ARTIFACT_MANIFEST` (default `artifacts/manifest.json`)
- `NOUPE_RELOAD=1` to enable autoreload
- `NOUPE_LAUNCH_TELEMETRY_FILE` (optional; write startup telemetry JSON after readiness)

Bare `uvicorn backend.main:app` startup allows degraded mode by default when configured required layers are missing, and exposes that state through `GET /ready` and `GET /diagnostics`. When lazy loading is enabled, `GET /ready` remains degraded until required lazy layers finish warming.

The Redis-backed Mosaic layer is optional for client handoff. When Redis is unavailable, the backend remains usable and surfaces that dependency state through `GET /ready` and `GET /diagnostics`.

The Mosaic layer now tracks rolling-window event history rather than a blind counter. The HTTP response exposes:

- `entity_id`
- `escalated`
- `recent_event_count`
- `unique_fragment_count`
- `window_hours`
- `threshold`
- `escalation_reason`
- `matched_event_ids`

Downstream consumers should migrate from the removed `mosaic.count` field to `mosaic.unique_fragment_count` when they need the escalation-driving signal, and to `mosaic.recent_event_count` when they need total event volume.

The launcher scripts are stricter by default:

- `scripts/launch/run_dev.sh` defaults `NOUPE_FAIL_ON_LAYER_LOAD_ERROR=1`
- `scripts/launch/run_backend_only.sh` defaults `NOUPE_FAIL_ON_LAYER_LOAD_ERROR=1`
- `scripts/launch/run_prod.sh` forces strict startup and strict preflight checks

Use strict startup locally when you want missing required layers to fail fast:

```sh
NOUPE_FAIL_ON_LAYER_LOAD_ERROR=1 uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Healthcheck: `curl http://localhost:8000/health`

Readiness: `curl http://localhost:8000/ready`
Diagnostics: `curl http://localhost:8000/diagnostics`
Metrics: `curl http://localhost:8000/metrics`

JSON API endpoints return indented responses by default for terminal readability. The Prometheus `/metrics` endpoint remains plain text.

Classify:

```sh
curl -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{"text": "Acme Corp is acquiring GlobalTech for $2.5 billion", "debug": false}'
```

Include exact lexicon spans and approximate classifier windows with:

```sh
curl -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{"text": "Acme Corp is acquiring GlobalTech for $2.5 billion", "include_offending_spans": true}'
```

API docs auto-served at `http://localhost:8000/docs` (Swagger) and `http://localhost:8000/redoc`.

## Optional Public Evidence + Local LLM

Noupe can add sanitized public-source verification and local-only LLM adjudication to the normal pipeline:

```sh
PIPELINE_LAYERS=lexicon,model1,model2,public_evidence,llm_adjudicator \
NOUPE_PUBLIC_EVIDENCE_ENABLED=1 \
EXA_API_KEY="..." \
NOUPE_LLM_ENABLED=1 \
NOUPE_LLM_BASE_URL="http://10.0.0.25:8001/v1" \
NOUPE_LLM_MODEL="gpt-oss-20b" \
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

The public evidence layer sends only sanitized entity/ticker/event/date queries to external retrieval providers. The local LLM layer may receive the original document text only when the configured base URL is loopback/private, unless `NOUPE_LLM_ALLOW_REMOTE_BASE_URL=1` is explicitly set.

Optional launch telemetry report:

```sh
NOUPE_LAUNCH_TELEMETRY_FILE=reports/launch_telemetry.json ./scripts/launch/run_backend_only.sh
cat reports/launch_telemetry.json
```

Watch-style terminal status view:

```sh
python3 scripts/watch_backend_status.py
python3 scripts/watch_backend_status.py --once
python3 scripts/watch_backend_status.py --base-url http://127.0.0.1:8010 --interval-seconds 1.5
```

## Request Tracing By `X-Request-ID`

When you need to debug one request end-to-end, run the backend through `tee` so logs are persisted:

```sh
./scripts/launch/run_backend_only.sh | tee reports/backend.log
```

Send a classify request and capture response headers:

```sh
curl -sS -D /tmp/noupe-headers.txt -o /tmp/noupe-body.json \
  -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{"text":"Acme Corp is acquiring GlobalTech for $2.5 billion"}'
```

Extract the request id and follow only matching log lines:

```sh
REQUEST_ID="$(grep -i '^x-request-id:' /tmp/noupe-headers.txt | awk '{print $2}' | tr -d '\r')"
./scripts/trace_request_logs.sh --log-file reports/backend.log --request-id "${REQUEST_ID}"
```

One-shot view (no follow):

```sh
./scripts/trace_request_logs.sh --log-file reports/backend.log --request-id "${REQUEST_ID}" --no-follow
```

Swagger/OpenAPI now documents:

- the backend-only runtime and archived-demo split
- route summaries for health, readiness, diagnostics, metrics, classify, and batch classify
- the richer `offending_spans` payload, including exact lexicon spans and approximate classifier-window spans
- request and response examples for the main classification path

Chat demo UI:

- `http://localhost:8081/chat/?api=http://localhost:8000`
- Screens typed messages and DOCX uploads through the same `POST /classify` backend before they are allowed into the chat transcript
- Requests `include_offending_spans=true` and surfaces localization, timing, cache, and request-id details inside the guard modal
- `LOW_RISK` triggers a warning with override, `HIGH_RISK` is blocked

Legacy analyzer UI:

- `http://localhost:8081/legacy/?api=http://localhost:8000`
- Sends `include_offending_spans=true` by default
- Renders request telemetry, per-layer timings, localized findings, the archived architecture trace view, and the raw JSON response side by side

Batch classify:

```sh
curl -X POST http://localhost:8000/classify/batch \
  -H "Content-Type: application/json" \
  -d '{"items":[{"text":"Company A earnings leak"},{"text":"Public press release", "debug": false}]}'
```

Python client:

```python
from noupe import NoupeClient

with NoupeClient("http://localhost:8000") as client:
    result = client.classify(
        text="Acme Corp is acquiring GlobalTech for $2.5 billion next quarter.",
        entity_id="acme-corp",
        include_offending_spans=True,
    )

    print(result.classification)
    print(result.timings_ms)
    print(result.model_dump())
```

The clients are implemented at `src/noupe/client.py`. `NoupeClient` is synchronous, `AsyncNoupeClient` is asynchronous, and both call the same backend endpoints. Full usage is documented in `docs/api/python_client.md`.

Run the included example scripts:

```sh
python scripts/examples/sync_client_example.py \
  "Acme Corp is acquiring GlobalTech for $2.5 billion next quarter." \
  --include-offending-spans

python scripts/examples/async_client_example.py \
  "Acme Corp is acquiring GlobalTech for $2.5 billion next quarter." \
  --include-offending-spans
```

Use the sync client when the caller is ordinary blocking Python. Use the async client when the caller already runs under `asyncio` and should avoid blocking the event loop.

## Production Profile

Use the production launcher (no autoreload, multi-worker):

```sh
./scripts/launch/run_prod.sh
```

`scripts/launch/run_prod.sh` now:

- always runs strict preflight checks
- does not prompt for pipeline layers
- still asks which surface(s) to open: legacy analyzer, chat demo, all, or backend only
- starts the backend in multi-worker mode
- waits for `GET /ready` before opening any selected frontend
- provisions `PROMETHEUS_MULTIPROC_DIR` automatically so `/metrics` aggregates across workers

Useful production launcher env vars:

- `NOUPE_FRONTENDS=legacy|chat|all|none`
- `NOUPE_HOST` (default `0.0.0.0`)
- `NOUPE_PORT` (default `8000`)
- `NOUPE_UVICORN_WORKERS` (default `2`)
- `NOUPE_LOG_LEVEL` (default `info`)
- `NOUPE_PRETTY_LOGS` (`1` by default; set `NOUPE_PRETTY_LOGS=0` for compact single-line backend JSON logs)
- `NOUPE_FRONTEND_DEMO_PORT` (default `8081`)
- `NOUPE_READY_TIMEOUT_SECONDS` (default `180`)
- `NOUPE_RESPONSE_CACHE_SIZE` (default `0` in the production launcher because the built-in cache is per-worker memory)

`scripts/launch/run_prod.sh` still forces strict startup and will fail if required configured layers cannot load.

## Bootstrapping Artifacts

If model and clustering checkpoints are missing, regenerate repo-local runtime artifacts with:

```sh
python3 training/train_validate_pipeline.py
```

Interactive training launcher:

```sh
./scripts/train_dev.sh
```

If you only need a minimal local server without trained artifacts, you can run lexicon-only mode:

```sh
PIPELINE_LAYERS=lexicon uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The legacy analyzer and the chat demo now live under `archive/frontend-demos/` and are served by the launch scripts from a separate static file server.

Useful env vars:

- `NOUPE_UVICORN_WORKERS` (default `2`)
- `NOUPE_HOST` (default `0.0.0.0`)
- `NOUPE_PORT` (default `8000`)
- `NOUPE_LOG_LEVEL` (default `info`)
- `NOUPE_PRETTY_LOGS` (`1` by default; set `NOUPE_PRETTY_LOGS=0` for compact single-line backend JSON logs)
- `PROMETHEUS_MULTIPROC_DIR` (optional in dev; automatically set by `scripts/launch/run_prod.sh` for multi-worker metrics aggregation)

## Latency Benchmarking

Benchmark one or more text files against real `POST /classify` requests with:

```sh
python3 scripts/benchmark_latency.py path/to/1000.txt path/to/2000.txt path/to/5000.txt path/to/10000.txt
```

The script can also:

- read `.txt` files from directories
- accept a repo-relative glob with `--glob`
- spawn the backend automatically or target an existing backend with `--no-server --url`
- write JSON and CSV reports to `reports/`

## Pipeline Behavior

The `/classify` endpoint runs configured layers sequentially:

1. **Lexicon filter** — regex, spaCy NER, Presidio PII, restricted list cross-ref. Deterministic short-circuit to `HIGH_RISK` when a restricted entity or a money threshold breach is detected.
2. **Embedding generation** — sentence embedding with `all-mpnet-base-v2`.
3. **Clustering** — Isolation Forest anomaly score (if checkpoint exists).
4. **Model-1 (FinBERT)** — binary classifier: safe vs risk, executed over overlapping sliding windows so the response can expose approximate top-risk classifier windows (if checkpoint exists).
5. **Model-2 (BERT)** — binary classifier: low_risk vs high_risk, also executed over overlapping sliding windows when Model-1 predicts risk (if checkpoint exists).
6. **Mosaic aggregation** — Redis rolling-window event tracking with unique-fragment escalation and explainable evidence fields.
7. **Regression** — optional final risk synthesis only when a trained regression checkpoint exists.

Each classification response now includes an additive `observability` object with:

- `degraded` to signal best-effort output when a configured layer that should have run was unavailable or failed.
- `cache_status` to distinguish `hit`, `miss`, and `disabled`.
- `active_pipeline`, `executed_layers`, and `skipped_layers` for request drilldown.
- `layer_errors` for startup, lazy-load, or runtime failures associated with the response.

When `include_offending_spans=true`, responses can also include:

- exact lexicon-derived spans
- approximate `model1` and `model2` spans derived from sliding-window classifier inference
- per-span localization metrics such as exact-vs-approximate status, local context, span length, score type, score, and classifier window index/count/token sizing

## Training Models

Both classification training scripts expect CSVs with columns `text,label`.

### Model-1 (FinBERT — public vs non-public)

Labels: `0` = public/safe, `1` = non-public/risk.

```sh
python3 src/noupe/workflow/layer4_classification/model1/classifier.py data/train.csv data/val.csv
```

Checkpoint directory: `artifacts/layer4_classification/model1/best/`.

### Model-2 (BERT — high risk vs low risk)

Labels: `0` = low_risk, `1` = high_risk. Train on violation corpus only (no safe/public rows).

```sh
python3 src/noupe/workflow/layer4_classification/model2/classifier.py data/train_violations.csv data/val_violations.csv
```

Checkpoint directory: `artifacts/layer4_classification/model2/best/`.

## Generating Embeddings

```sh
python3 src/noupe/workflow/layer2_embeddings/generate_embeddings.py
```

Outputs `public_embeddings.npy`, `violation_embeddings.npy`, and `all_embeddings.npy`.

## Training the Anomaly Detector (Isolation Forest)

```sh
python3 src/noupe/workflow/layer3_clustering/isolation_forest.py all_embeddings.npy
```

Checkpoint saved to `artifacts/layer3_clustering/anomaly_detector.joblib`.

Optional custom output path:

```sh
python3 src/noupe/workflow/layer3_clustering/isolation_forest.py all_embeddings.npy path/to/output.joblib
```

## Configuration

Primary runtime config is `config.toml`. Environment variables override config values.

Notable keys:

- `MNPI_ABS_THRESHOLD`
- `MNPI_PCT_THRESHOLD`
- `MODEL1_THRESHOLD`
- `MODEL2_THRESHOLD`
- `IF_CONTAMINATION`
- `IF_MAX_FEATURES`
- `IF_N_ESTIMATORS`
- `MOSAIC_TTL_HOURS`
- `MOSAIC_THRESHOLD`
- `REDIS_HOST`
- `REDIS_PORT`
- `MOSAIC_CONNECT_TIMEOUT_SECONDS`
- `MOSAIC_SOCKET_TIMEOUT_SECONDS`
- `MOSAIC_RETRY_ATTEMPTS`
- `MOSAIC_RETRY_BACKOFF_MS`
- `NOUPE_ALLOWED_ORIGINS` (comma-separated CORS origins)
- `NOUPE_API_KEY` (optional; when set, both `POST /classify` and `POST /classify/batch` require `X-API-Key`)
- `NOUPE_FAIL_ON_LAYER_LOAD_ERROR` (`1`/`0`, default `0` for bare app startup; `scripts/launch/run_prod.sh` overrides to `1`)
- `NOUPE_FRONTEND_DEMO_PORT` (default `8081` for the archived demo server)
- `NOUPE_LAZY_LOAD_HEAVY` (`1`/`0`, default `1`)
- `NOUPE_PRETTY_LOGS` (`1`/`0`, default `1`)
- `NOUPE_PREWARM_REQUIRED_LAYERS` (`1`/`0`, default `1` when lazy loading is enabled)
- `NOUPE_RESPONSE_CACHE_SIZE` (default `256`)
- `NOUPE_RESPONSE_CACHE_TTL_SECONDS` (default `60`)
- `NOUPE_BATCH_MAX_CONCURRENCY` (default `min(4, os.cpu_count() or 1)`)
- `NOUPE_ARTIFACT_MANIFEST` (default `artifacts/manifest.json`)
- `NOUPE_HF_OFFLINE` (optional offline mode hint for preflight)

## Restricted List

Edit `src/noupe/workflow/layer1_lexicon/restricted_list.json`:

```json
{"entities": [{"name": "...", "ticker": "...", "isin": "..."}]}
```

Matches are case-insensitive on name and exact on ticker/ISIN.
