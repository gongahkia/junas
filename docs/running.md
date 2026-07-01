# Running Junas

Junas uses `uv` as the canonical Python workflow.

## Setup

```sh
uv sync --extra dev
uv run python -m spacy download en_core_web_sm
uv run python scripts/preflight.py --strict
```

The default runtime is deterministic-only. `PIPELINE_LAYERS` should normally be empty. Optional server layers are `public_evidence`, `llm_adjudicator`, `llm_defined_term_extractor`, and `llm_coverage_auditor`.

Document ingest defaults to fail-open: unsupported or partially unreadable payloads return a degraded best-effort response instead of HTTP 422. Set `JUNAS_DOCUMENT_FAIL_CLOSED=1` to reject those payloads. Review and rewrite calls also accept `degraded_policy=allow|warn|block_send`; `block_send` returns `send_allowed=false` when degraded coverage is present.

Request bodies are capped by `api.max_request_bytes` / `JUNAS_MAX_REQUEST_BYTES` (default `10485760`) before schema validation.

## Backend Launch

Standard backend-only launch:

```sh
./scripts/launch/run_backend_only.sh
curl http://127.0.0.1:8000/ready
```

Development and production-style backend launchers:

```sh
./scripts/launch/run_dev.sh
./scripts/launch/run_prod.sh
```

These launchers start the FastAPI backend only. They do not start browser extensions,
Office add-ins, desktop watchers, DMS hooks, or other adapter runtimes.

Manual backend launch:

```sh
uv run uvicorn junas.backend.main:app --host 0.0.0.0 --port 8000
```

## Adapter Launches

Adapter-specific launch, packaging, sideload, and QA commands live with each integration:

- `docs/integrations/direct-api.md`
- `docs/integrations/outlook.md`
- `docs/integrations/genai-browser.md`
- `docs/integrations/word.md`
- `docs/integrations/desktop-watcher.md`
- `docs/integrations/dms.md`

## Docker

```sh
docker compose up --build
curl http://localhost:8000/ready
```

Compose reads `.env` for variable substitution but passes only Junas runtime/provider variables into the container. Build-time fixture keys and future OCR/media keys are not forwarded by default.

Accuracy-first managed deployment, for a tenant that has opted in and where Junas supplies the provider key:

```sh
JUNAS_LLM_API_KEY=... \
JUNAS_LLM_TENANT_OPT_IN_OPENAI=1 \
SERPER_API_KEY=... \
docker compose -f docker-compose.yml -f docker-compose.managed-llm.yml up --build
```

This overlay enables `public_evidence,llm_adjudicator`, uses remote LLM `structured_tokens` by default, and refuses to start unless the LLM key and tenant opt-in flag are present.

## Public Evidence

Public evidence is disabled by default and only receives PrivacyGuard-sanitized queries.

```sh
JUNAS_PUBLIC_EVIDENCE_ENABLED=1 \
JUNAS_PUBLIC_EVIDENCE_PROVIDER=serper \
SERPER_API_KEY=... \
PIPELINE_LAYERS=public_evidence \
uv run uvicorn junas.backend.main:app --host 0.0.0.0 --port 8000
```

Supported providers: `exa`, `tinyfish`, `serper`, `serpapi`, `none`.

## LLM Adjudication

Remote LLM endpoints default to `structured_tokens`. Remote raw text requires explicit opt-in:

```sh
JUNAS_LLM_ENABLED=1 \
JUNAS_LLM_PROVIDER=openai \
JUNAS_LLM_API_KEY=... \
JUNAS_LLM_BASE_URL=https://api.openai.com/v1 \
JUNAS_LLM_ALLOW_REMOTE_BASE_URL=1 \
JUNAS_LLM_TENANT_OPT_IN_OPENAI=1 \
JUNAS_LLM_INPUT_MODE=structured_tokens \
PIPELINE_LAYERS=llm_adjudicator \
uv run uvicorn junas.backend.main:app --host 0.0.0.0 --port 8000
```

Audit-grade helper layers are separate opt-ins. They are never called by `review_profile=strict`.

```sh
JUNAS_LLM_ENABLED=1 \
JUNAS_LLM_DEFINED_TERMS_ENABLED=1 \
JUNAS_LLM_COVERAGE_AUDIT_ENABLED=1 \
PIPELINE_LAYERS=llm_defined_term_extractor,llm_coverage_auditor \
uv run uvicorn junas.backend.main:app --host 0.0.0.0 --port 8000
```

`llm_defined_term_extractor` sends only the capped document preamble. If the LLM endpoint is remote, it requires `JUNAS_LLM_ALLOW_REMOTE_BASE_URL=1` and `JUNAS_LLM_ALLOW_REMOTE_RAW_TEXT=1`. `llm_coverage_auditor` sends only a structured finding summary plus the document hash.

## Verification

```sh
./scripts/verify_runtime.sh
uv run python scripts/recall_gate.py
uv run python scripts/generate_accuracy_doc.py --check
uv run python training/distillation/promotion_gate.py
```

Audit-pack utilities:

```sh
uv run python scripts/export_audit_pack.py "$REVIEW_ID" --output ./out/audit.zip
uv run python scripts/verify_audit_pack.py ./out/audit.zip
uv run python scripts/verify_journal.py
```
