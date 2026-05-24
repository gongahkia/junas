# Running Kaypoh

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

For reproducible local installs:

```sh
python -m pip install -r requirements.lock.txt -r requirements-dev.lock.txt
```

`backend.main:app` remains the supported FastAPI entrypoint. The canonical package lives under `src/kaypoh/`.

## Running The API

```sh
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Or use the repository launchers:

```sh
./scripts/launch/run_backend_only.sh
./scripts/launch/run_dev.sh
./scripts/launch/run_prod.sh
```

The launchers start the backend, run preflight checks, and wait for readiness. They do not serve legacy UI assets.

Useful env vars:

- `KAYPOH_PORT` (default `8000`)
- `KAYPOH_HOST` (default `0.0.0.0`)
- `KAYPOH_LOG_LEVEL` (default `info`)
- `KAYPOH_PRETTY_LOGS` (`1` by default)
- `PIPELINE_LAYERS=lexicon,embedding,...`
- `KAYPOH_API_KEY` for `X-API-Key` auth on protected POST endpoints
- `KAYPOH_FAIL_ON_LAYER_LOAD_ERROR=1` to fail fast when required layers cannot load
- `KAYPOH_LAUNCH_TELEMETRY_FILE=reports/launch_telemetry.json`

Runtime docs:

- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health: `GET /health`
- Readiness: `GET /ready`
- Diagnostics: `GET /diagnostics`
- Metrics: `GET /metrics`

## Primary Workflows

Anonymize a document before sending it to another system:

```sh
curl -X POST http://localhost:8000/anonymize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Send Dr Jane Tan S1234567D the confidential draft. Acme Corp expects a $2.5 billion acquisition before announcement.",
    "source_jurisdiction": "SG",
    "destination_jurisdiction": "US",
    "document_type": "email",
    "include_suggestions": true
  }'
```

Review without rewriting:

```sh
curl -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Please send to Tan S1234567D. Confidential: Acme Corp will acquire GlobalTech before announcement for $2.5 billion.",
    "source_jurisdiction": "SG",
    "destination_jurisdiction": "US",
    "document_type": "research_note",
    "entity_id": "Acme Corp",
    "include_suggestions": true
  }'
```

Legacy classifier path:

```sh
curl -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{"text": "Acme Corp is acquiring GlobalTech for $2.5 billion", "include_offending_spans": true}'
```

Batch classification:

```sh
curl -X POST http://localhost:8000/classify/batch \
  -H "Content-Type: application/json" \
  -d '{"items":[{"text":"Company A earnings leak"},{"text":"Public press release"}]}'
```

For file uploads through an integration, send base64 text, DOCX, or PDF content with `document_base64`, `document_filename`, and optionally `document_mime_type`.

## Python Client

```python
from kaypoh import KaypohClient

with KaypohClient("http://localhost:8000") as client:
    result = client.anonymize(
        text="Send Dr Jane Tan S1234567D the confidential draft.",
        source_jurisdiction="SG",
        destination_jurisdiction="US",
    )

    print(result.anonymized_text)
    print(result.mapping)
```

`KaypohClient` is synchronous and `AsyncKaypohClient` is asynchronous. Both support `anonymize(...)`, `review(...)`, `classify(...)`, and batch classification. Full usage is documented in `docs/api/python_client.md`.

## Optional Public Evidence And Local LLM

Kaypoh can add sanitized public-source verification and local-only LLM adjudication:

```sh
PIPELINE_LAYERS=lexicon,model1,model2,public_evidence,llm_adjudicator \
KAYPOH_PUBLIC_EVIDENCE_ENABLED=1 \
EXA_API_KEY="..." \
KAYPOH_LLM_ENABLED=1 \
KAYPOH_LLM_BASE_URL="http://10.0.0.25:8001/v1" \
KAYPOH_LLM_MODEL="gpt-oss-20b" \
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

The public evidence layer sends only sanitized entity/ticker/event/date queries to external retrieval providers. The local LLM layer may receive original document text only when the configured base URL is loopback/private, unless remote use is explicitly allowed by config. API responses expose structured evidence and privacy-ledger decisions, not raw chain-of-thought.

## Verification

```sh
python3 scripts/preflight.py
python3 scripts/preflight.py --strict
./scripts/verify_runtime.sh
python -m unittest discover -s test -p 'test*.py'
```

`./scripts/verify_runtime.sh` expects `redis-server` on `PATH` so it can start an isolated Redis instance for mosaic checks.

## Artifacts And Training

Verify or hydrate runtime artifacts:

```sh
python3 scripts/bootstrap_artifacts.py
python3 scripts/bootstrap_artifacts.py --sync-from-legacy
```

Regenerate model artifacts:

```sh
python3 training/train_validate_pipeline.py
```

Minimal lexicon-only local server:

```sh
PIPELINE_LAYERS=lexicon uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## Benchmarking

Place benchmark `.txt` inputs in `test/fixtures/latency-corpus/`, then run:

```sh
./scripts/benchmark_latency_corpus.sh
python3 scripts/benchmark_latency.py path/to/1000.txt path/to/2000.txt
```

Reports are written to `reports/`.
