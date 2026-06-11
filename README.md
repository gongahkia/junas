# Kaypoh

> Start with `docs/architecture.md`, then `docs/statutory-coverage.md`, `docs/known-limitations.md`, and this README.

Kaypoh is an API-first pre-send safety engine for PII anonymization and MNPI review. The deterministic review engine is the runtime source of truth; `/classify` is now a compatibility shim over `engine.review()`.

## Runtime

- `kaypoh-local`: offline-default desktop SKU. Deterministic engine + Presidio + spaCy + FastAPI. No `torch`, `transformers`, `sentence-transformers`, `redis`, `xgboost`, `scikit-learn`, `pandas`, or external HTTP.
- `kaypoh-server`: same deterministic engine plus opt-in public evidence and LLM adjudication. Retrieval providers currently supported: Exa, Tinyfish, Serper, SerpAPI. External calls must pass `PrivacyGuard` and tenant/deployer opt-in.

## Layout

- `src/kaypoh/backend/`: FastAPI app, auth, schemas, observability, and SIEM.
- `src/kaypoh/review/`: deterministic PII/MNPI review engine, citations, and jurisdiction packs.
- `src/kaypoh/anonymize/`: placeholder rewriting, mapping persistence, and reidentification.
- `src/kaypoh/external/`: PrivacyGuard and opt-in public-evidence providers.
- `src/kaypoh/advisory/`: advisory-only LLM helpers and signals.
- `src/kaypoh/ingest/`: document/corpus parser support.
- `scripts/`: UV-first launchers, preflight, recall gates, audit, and packaging tooling.
- `test/`: automated tests and legal-contract corpora.
- `reports/`: committed evaluation evidence and generated benchmark reports.
- `training/distillation/`: pivot-aligned local-student distillation work.
- `packaging/`: PyInstaller local desktop packaging.

The archived layer1-6 classifier stack, old artifact manifest, root helper folder, classifier training entrypoints, and root import shims have been removed.

## Common Commands

```sh
uv sync --extra dev
uv run python -m spacy download en_core_web_sm

./scripts/launch/run_backend_only.sh
./scripts/launch/run_dev.sh
./scripts/launch/run_prod.sh
./scripts/verify_runtime.sh

curl -X POST http://localhost:8000/pseudonymize -H "Content-Type: application/json" \
  -d '{"text":"Send Dr Jane Tan S1234567D the confidential draft.","source_jurisdiction":"SG","destination_jurisdiction":"US","document_type":"SPA"}'

uv run python scripts/recall_gate.py
uv run python scripts/generate_accuracy_doc.py --check
```

## Docker

```sh
docker compose up --build
curl http://localhost:8000/ready
```

The compose service defaults to deterministic-only. Set `KAYPOH_PUBLIC_EVIDENCE_ENABLED=1` plus a provider key, or `KAYPOH_LLM_ENABLED=1` plus the explicit LLM opt-in gates, only for tenant-approved server deployments. Audit-grade LLM helpers are separate opt-ins via `KAYPOH_LLM_DEFINED_TERMS_ENABLED=1` and `KAYPOH_LLM_COVERAGE_AUDIT_ENABLED=1`; `strict` never invokes them.
Compose reads `.env` for variable substitution but passes only Kaypoh runtime/provider variables into the container.

For an accuracy-first managed deployment where Kaypoh provides the LLM key for an opted-in tenant:

```sh
KAYPOH_LLM_API_KEY=... \
KAYPOH_LLM_TENANT_OPT_IN_OPENAI=1 \
SERPER_API_KEY=... \
docker compose -f docker-compose.yml -f docker-compose.managed-llm.yml up --build
```

## Desktop SKU

```sh
uv sync --extra local --extra packaging
uv run python -m spacy download en_core_web_sm
uv run pyinstaller packaging/kaypoh-local.spec
./dist/kaypoh-local/kaypoh-local
```

See `packaging/README.md` for packaging notes. Python client docs live in `docs/api/python_client.md`.
