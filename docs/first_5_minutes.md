# First 5 Minutes Runbook

This is a copy-paste quickstart for operators and integrators.

## 1) Setup (one-time)

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python3 -m spacy download en_core_web_sm
python3 scripts/bootstrap_artifacts.py
python3 scripts/preflight.py --strict
```

## 2) Backend-Only (fastest path)

Start server:

```sh
./scripts/launch/run_backend_only.sh
```

Smoke check:

```sh
curl http://localhost:8000/ready
curl http://localhost:8000/health
```

Sample classify:

```sh
curl -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{"text":"Acme Corp is acquiring GlobalTech for $2.5 billion"}'
```

Sample Python call:

```python
from kaypoh import KaypohClient

with KaypohClient("http://localhost:8000") as client:
    result = client.classify(
        text="Acme Corp is acquiring GlobalTech for $2.5 billion",
        include_offending_spans=True,
    )
    print(result.classification)
```

If you are integrating from an asyncio application, use `AsyncKaypohClient` from the same package. Both clients call the same backend routes.

Run the included example scripts:

```sh
python scripts/examples/sync_client_example.py \
  "Acme Corp is acquiring GlobalTech for $2.5 billion"

python scripts/examples/async_client_example.py \
  "Acme Corp is acquiring GlobalTech for $2.5 billion"
```

## 3) Dev Mode With Demo Frontends

Start backend + choose frontend(s) interactively:

```sh
./scripts/launch/run_dev.sh
```

Non-interactive examples:

```sh
KAYPOH_FRONTENDS=legacy PIPELINE_LAYERS=lexicon ./scripts/launch/run_dev.sh
KAYPOH_FRONTENDS=all ./scripts/launch/run_dev.sh
```

Default demo base URL:

```txt
http://localhost:8081
```

## 4) API Key Mode

Start backend with API key requirement:

```sh
KAYPOH_API_KEY="dev-secret" ./scripts/launch/run_backend_only.sh
```

Call classify with auth header:

```sh
curl -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-secret" \
  -d '{"text":"Acme Corp is acquiring GlobalTech for $2.5 billion"}'
```

## 5) Troubleshooting

If startup stalls, inspect readiness and diagnostics:

```sh
curl http://localhost:8000/ready
curl http://localhost:8000/diagnostics
```

If required artifacts are missing:

```sh
python3 scripts/bootstrap_artifacts.py
python3 scripts/preflight.py --strict
```

If port `8000` is occupied:

```sh
KAYPOH_PORT=8010 ./scripts/launch/run_backend_only.sh
```

If you need per-request tracing by `X-Request-ID`:

```sh
./scripts/launch/run_backend_only.sh | tee reports/backend.log
curl -sS -D /tmp/kaypoh-headers.txt -o /tmp/kaypoh-body.json \
  -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{"text":"Acme Corp is acquiring GlobalTech for $2.5 billion"}'
REQUEST_ID="$(grep -i '^x-request-id:' /tmp/kaypoh-headers.txt | awk '{print $2}' | tr -d '\r')"
./scripts/trace_request_logs.sh --log-file reports/backend.log --request-id "${REQUEST_ID}"
```

## 6) API Docs

```txt
http://localhost:8000/docs
http://localhost:8000/redoc
http://localhost:8000/openapi.json
```
