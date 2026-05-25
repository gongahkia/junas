# Running Kaypoh

## Prerequisites

- Python 3.10+
- pip
- macOS/Linux

## Setup

Pick the SKU that matches your deployment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

# Desktop / offline runtime (no torch/transformers/redis/xgboost/sklearn/pandas)
python -m pip install -e ".[local,dev]"

# Full server runtime (model layers, mosaic, retrieval, LLM)
python -m pip install -e ".[server,dev]"

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
- `KAYPOH_REVIEW_PERSIST=1` to enable `/review/{id}/decision` and `GET /review/{id}` (writes to the HMAC-chained journal)
- `KAYPOH_JOURNAL_DIR` (default `./kaypoh-journal`) — directory holding `journal.jsonl`
- `KAYPOH_JOURNAL_KEY` — HMAC key for the journal chain. **Must be set in production.** A dev fallback is used otherwise.
- `KAYPOH_PUBLIC_EVIDENCE_PROVIDER=exa|tinyfish` + `EXA_API_KEY` / `TINYFISH_API_KEY` — provider auto-resolves to the right endpoint per provider.
- `KAYPOH_LLM_BASE_URL`, `KAYPOH_LLM_MODEL`, `KAYPOH_LLM_ENABLED=1` — local LLM adjudicator. Remote URLs require `KAYPOH_LLM_ALLOW_REMOTE_BASE_URL=1`.

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

Round-trip an anonymised document after external LLM analysis:

```sh
curl -X POST http://localhost:8000/reidentify \
  -H "Content-Type: application/json" \
  -d '{
    "anonymized_text": "Send [PERSON_1] [NRIC_FIN_1] the draft.",
    "mapping": [
      {"placeholder": "[PERSON_1]", "original_text": "Dr Jane Tan"},
      {"placeholder": "[NRIC_FIN_1]", "original_text": "S1234567D"}
    ]
  }'
```

Record a per-finding decision in the audit journal:

```sh
KAYPOH_REVIEW_PERSIST=1 KAYPOH_JOURNAL_KEY=$(openssl rand -hex 32) \
  uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# REVIEW_ID is the request_id returned from POST /review
curl -X POST http://localhost:8000/review/$REVIEW_ID/decision \
  -H "Content-Type: application/json" \
  -d '{"finding_id":"pii:named_person:5:16:0","action":"reject","rationale":"defined-term false positive"}'

curl http://localhost:8000/review/$REVIEW_ID
```

Export and verify a tamper-evident audit pack:

```sh
python3 scripts/export_audit_pack.py $REVIEW_ID --output ./out/audit.zip
python3 scripts/verify_audit_pack.py ./out/audit.zip
python3 scripts/verify_journal.py
```

Legacy classifier path (server SKU only):

```sh
curl -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{"text": "Acme Corp is acquiring GlobalTech for $2.5 billion", "include_offending_spans": true}'
```

Batch classification (server SKU only):

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

`KaypohClient` is synchronous and `AsyncKaypohClient` is asynchronous. Both support `anonymize(...)`, `review(...)`, `reidentify(...)`, `classify(...)`, and batch classification. Full usage is documented in `docs/api/python_client.md`.

Two end-to-end example scripts ship under `scripts/examples/`:

- `round_trip_example.py` — `anonymise → simulated external LLM → reidentify`, with `--use-document-hash` to demo the persistent-mapping path.
- `decision_flow_example.py` — `/review → POST /review/{id}/decision (with X-Reviewer-ID) → GET /review/{id}` and a follow-on audit-pack export command.

## Optional Public Evidence And Local LLM

Kaypoh can add sanitized public-source verification (Exa or Tinyfish) and local LLM adjudication:

```sh
PIPELINE_LAYERS=lexicon,model1,model2,public_evidence,llm_adjudicator \
KAYPOH_PUBLIC_EVIDENCE_ENABLED=1 \
KAYPOH_PUBLIC_EVIDENCE_PROVIDER=tinyfish \
TINYFISH_API_KEY="..." \
KAYPOH_LLM_ENABLED=1 \
KAYPOH_LLM_BASE_URL="http://10.0.0.25:8001/v1" \
KAYPOH_LLM_MODEL="gpt-oss-20b" \
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

The public-evidence layer sends only sanitized entity/ticker/event/date queries to external retrieval providers; both Exa and Tinyfish go through the same `PrivacyGuard.check_external_query` gate and every decision is recorded in the response's `privacy_ledger`. The LLM layer may receive original document text only when the configured base URL is loopback/private (`127.0.0.1`, `::1`, RFC1918, `*.local`). Remote LLM URLs require `KAYPOH_LLM_ALLOW_REMOTE_BASE_URL=1`; remote endpoints default to `structured_tokens` unless `KAYPOH_LLM_INPUT_MODE=raw_text` and `KAYPOH_LLM_ALLOW_REMOTE_RAW_TEXT=1` are both explicitly set. API responses expose structured evidence and privacy-ledger decisions, not raw chain-of-thought.

## Persistent Mapping Store

When `KAYPOH_REVIEW_PERSIST=1`, `/anonymize` can persist placeholder mappings under `${KAYPOH_JOURNAL_DIR}/mappings/` so `/reidentify` can restore text later from a `document_hash`. Set `KAYPOH_MAPPING_STORE_KEY` to encrypt newly written mapping files; see `docs/mapping-store-hardening.md`.

## Legal-Corpus Recall Gate

A hand-labelled SG legal-contract corpus lives under `test/fixtures/legal-corpus/`. The recall gate runs every fixture through the engine and fails on per-rule regression:

```sh
PYTHONPATH=src python3 scripts/recall_gate.py            # gate against the locked baseline
PYTHONPATH=src python3 scripts/recall_gate.py --update   # rewrite the baseline after an accuracy improvement
PYTHONPATH=src python3 scripts/recall_gate.py --verbose  # per-doc breakdown
```

The gate is invoked from the tracked pre-push hook (`.githooks/pre-push` → `scripts/check_python_clients.sh`). PRs that drop per-rule recall fail before push.

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
