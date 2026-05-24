# Kaypoh

Kaypoh is an API-first pre-send safety engine for PII anonymization and MNPI review.

Two distribution SKUs share the same source tree:

- **`kaypoh-local`** (`pip install kaypoh[local]`) — offline-default desktop SKU. Deterministic engine + Presidio + spaCy + FastAPI. No `torch`, `transformers`, `sentence-transformers`, `redis`, `xgboost`, `scikit-learn`, `pandas`, or external HTTP. PyInstaller spec at `packaging/kaypoh-local.spec` bundles `en_core_web_sm` for desktop distribution.
- **`kaypoh-server`** (`pip install kaypoh[server]`) — full stack: model layers (FinBERT, BERT severity), mosaic aggregation, public-source retrieval (Exa, Tinyfish), local + opt-in remote LLM adjudication.

Both SKUs serve the same wire contracts.

## Layout

- `api/`: compatibility exports for older `api.main`, `api.schemas`, and `api.client` imports
- `archive/`: pruned holding area for tracked artifacts that should stay outside active runtime paths
- `artifacts/`: runtime checkpoints verified by `artifacts/manifest.json`
- `backend/`: compatibility exports for `backend.main:app`, `backend.client`, and related legacy imports
- `configs/`: compatibility exports for runtime config helpers
- `docs/`: operator docs, schema docs, architecture notes, and sample corpus JSON
- `packaging/`: PyInstaller spec + entrypoint for the `kaypoh-local` desktop binary
- `reports/`: generated benchmark and training reports
- `scripts/`: launchers, benchmarking, preflight, validation, recall gate, and audit-pack tooling
- `src/kaypoh/`: canonical Python package for runtime, workflow, config, helper, and training code
- `test/`: automated tests, fixtures, and the legal-contract recall corpus
- `training/`: end-to-end model and pipeline training entrypoints

## Canonical Runtime Paths

- FastAPI app: `src/kaypoh/backend/main.py` with compatibility shim `backend.main:app`
- Python client: `src/kaypoh/client.py` with docs in `docs/api/python_client.md`
- Pivot architecture: `ARCHITECTURE-PIVOT-24-MAY.md`
- Workflow stages: `src/kaypoh/workflow/`
- Runtime artifacts: `artifacts/` with manifest verification in `artifacts/manifest.json`
- Backend-only launcher: `scripts/launch/run_backend_only.sh`
- Dev launcher: `scripts/launch/run_dev.sh`
- Production-style launcher: `scripts/launch/run_prod.sh`

## Primary Endpoints

- `POST /anonymize` — extracts inline text or base64 TXT/DOCX/PDF, returns deterministic placeholders + a local mapping table.
- `POST /reidentify` — deterministic inverse using the caller-supplied mapping. Closes the `anonymise → external LLM → re-identify` round-trip inside the runtime.
- `POST /review` — same evidence stack without rewriting text. Returns findings + suggestions + jurisdiction-scoped scores. The `request_id` returned here is the `review_id` for the decision flow.
- `POST /review/{review_id}/decision` — record `accept | reject | rewrite` per finding. Persisted to the HMAC-chained journal when `KAYPOH_REVIEW_PERSIST=1`.
- `GET /review/{review_id}` — replay the session state from the journal.
- `POST /classify`, `POST /classify/batch` — legacy single-doc / batch classifier (server SKU only).
- `GET /health`, `/ready`, `/diagnostics`, `/metrics` — operational surfaces.

## Common Commands

```sh
./scripts/launch/run_backend_only.sh
./scripts/launch/run_dev.sh
./scripts/launch/run_prod.sh
./scripts/check_python_clients.sh
curl -X POST http://localhost:8000/anonymize -H "Content-Type: application/json" \
  -d '{"text":"Send Dr Jane Tan S1234567D the confidential draft.","source_jurisdiction":"SG","destination_jurisdiction":"US","document_type":"SPA"}'

# round-trip: anonymise -> LLM -> reidentify with the same mapping
curl -X POST http://localhost:8000/reidentify -H "Content-Type: application/json" \
  -d '{"anonymized_text":"Send [PERSON_1] [NRIC_FIN_1] the draft.","mapping":[{"placeholder":"[PERSON_1]","original_text":"Dr Jane Tan"},{"placeholder":"[NRIC_FIN_1]","original_text":"S1234567D"}]}'

# decision flow (KAYPOH_REVIEW_PERSIST=1 + KAYPOH_JOURNAL_KEY set)
curl -X POST http://localhost:8000/review/$REVIEW_ID/decision -H "Content-Type: application/json" \
  -d '{"finding_id":"pii:named_person:5:16:0","action":"reject","rationale":"defined-term false positive"}'

# legal-corpus recall gate
PYTHONPATH=src python3 scripts/recall_gate.py
PYTHONPATH=src python3 scripts/recall_gate.py --update --verbose

# audit-pack export + verify
python3 scripts/export_audit_pack.py $REVIEW_ID --output ./out/audit.zip
python3 scripts/verify_audit_pack.py ./out/audit.zip
python3 scripts/verify_journal.py

python scripts/examples/sync_client_example.py "Acme Corp is acquiring GlobalTech next quarter."
python scripts/examples/async_client_example.py "Acme Corp is acquiring GlobalTech next quarter."
./scripts/verify_runtime.sh
python3 scripts/bootstrap_artifacts.py --sync-from-legacy
python3 scripts/preflight.py --strict
./.venv/bin/python -m unittest discover -s test -p 'test*.py'
```

`./scripts/verify_runtime.sh` is the end-to-end verifier: it runs the static checks, test suite, and live smoke coverage for every runtime layer, including a temporary local Redis-backed mosaic pass. (Server SKU only — uses heavy ML deps.)

`./scripts/check_python_clients.sh` runs the Python client checks plus the legal-corpus recall gate. Wired into the tracked git hooks under `.githooks/` so PRs that drop per-rule recall fail before push.

For Python integrations, Kaypoh ships both `KaypohClient` and `AsyncKaypohClient` over the same backend API. Methods include `review(...)`, `anonymize(...)`, `reidentify(...)`, `classify(...)`, and `classify_batch(...)`. See `docs/api/python_client.md`.

## Desktop SKU

Build the offline-default desktop binary:

```sh
pip install -e ".[local,packaging]"
python -m spacy download en_core_web_sm
pyinstaller packaging/kaypoh-local.spec
# launches on http://127.0.0.1:8765 by default
./dist/kaypoh-local/kaypoh-local
```

See `packaging/README.md` for the offline-guarantee verification recipe.
