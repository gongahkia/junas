# Running Kaypoh

Kaypoh uses `uv` as the canonical Python workflow.

## Setup

```sh
uv sync --extra dev
uv run python -m spacy download en_core_web_sm
uv run python scripts/preflight.py --strict
```

The default runtime is deterministic-only. `PIPELINE_LAYERS` should normally be empty. Optional server layers are `public_evidence` and `llm_adjudicator`.

## Launch

```sh
./scripts/launch/run_backend_only.sh
./scripts/launch/run_dev.sh
./scripts/launch/run_prod.sh
```

Manual launch:

```sh
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## Docker

```sh
docker compose up --build
curl http://localhost:8000/ready
```

Compose reads `.env` for variable substitution but passes only Kaypoh runtime/provider variables into the container. Build-time fixture keys and future OCR/media keys are not forwarded by default.

Accuracy-first managed deployment, for a tenant that has opted in and where Kaypoh supplies the provider key:

```sh
KAYPOH_LLM_API_KEY=... \
KAYPOH_LLM_TENANT_OPT_IN_OPENAI=1 \
SERPER_API_KEY=... \
docker compose -f docker-compose.yml -f docker-compose.managed-llm.yml up --build
```

This overlay enables `public_evidence,llm_adjudicator`, uses remote LLM `structured_tokens` by default, and refuses to start unless the LLM key and tenant opt-in flag are present.

## Public Evidence

Public evidence is disabled by default and only receives PrivacyGuard-sanitized queries.

```sh
KAYPOH_PUBLIC_EVIDENCE_ENABLED=1 \
KAYPOH_PUBLIC_EVIDENCE_PROVIDER=serper \
SERPER_API_KEY=... \
PIPELINE_LAYERS=public_evidence \
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Supported providers: `exa`, `tinyfish`, `serper`, `serpapi`, `none`.

## LLM Adjudication

Remote LLM endpoints default to `structured_tokens`. Remote raw text requires explicit opt-in:

```sh
KAYPOH_LLM_ENABLED=1 \
KAYPOH_LLM_PROVIDER=openai \
KAYPOH_LLM_API_KEY=... \
KAYPOH_LLM_BASE_URL=https://api.openai.com/v1 \
KAYPOH_LLM_ALLOW_REMOTE_BASE_URL=1 \
KAYPOH_LLM_TENANT_OPT_IN_OPENAI=1 \
KAYPOH_LLM_INPUT_MODE=structured_tokens \
PIPELINE_LAYERS=llm_adjudicator \
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## Verification

```sh
./scripts/verify_runtime.sh
uv run python scripts/recall_gate.py
uv run python scripts/generate_accuracy_doc.py --check
```

Audit-pack utilities:

```sh
uv run python scripts/export_audit_pack.py "$REVIEW_ID" --output ./out/audit.zip
uv run python scripts/verify_audit_pack.py ./out/audit.zip
uv run python scripts/verify_journal.py
```
