# Scripts Folder

This folder contains operational and maintenance commands.

- `launch/`: UV-first backend launchers.
- `examples/`: runnable sync and async Python client examples.
- `check_python_clients.sh`: syntax and unit checks for the sync and async Python clients.
- `benchmark_latency.py`: latency benchmark runner for current HTTP surfaces.
- `benchmark_latency_corpus.sh`: shell wrapper for `test/fixtures/latency-corpus/`.
- `check_latency_slo.py`: opt-in p95 SLO gate for `/review` and `/anonymize` strict/audit-grade paths, using in-process or live HTTP mode.
- `export_openapi_examples.py`: generate Postman and cURL examples from the current OpenAPI contract.
- `generate_accuracy_doc.py`: regenerate `docs/accuracy.md` from committed corpus locks.
- `preflight.py`: current runtime readiness checks.
- `erase_subject.py`: rebuild/query the HMAC subject-erasure reverse index and erase by subject value.
- `purge_mappings.py`: delete persisted anonymization mappings by document hash or retention age.
- `trace_request_logs.sh`: tail backend logs and filter by a specific `X-Request-ID`.
- `verify_runtime.sh`: UV-first verification for lint, focused tests, and live HTTP smoke.
- `watch_backend_status.py`: watch-style terminal dashboard for `/health`, `/ready`, `/diagnostics`, and `/metrics`.
- `clean_dev.sh`: local artifact cleanup.
- `smoke_audit_grade_azure.py`: one-document Azure `audit_grade` LLM smoke test; use `--use-gpt5-mini-env` to map `GPT5_MINI_*` env vars into `KAYPOH_LLM_*`.
- `preflight_production.py`: strict production preflight wrapper around `preflight.py --deployment production --strict`.
- `smoke_audit_pack.py`: seed a temporary review journal, export an audit pack, and verify the pack HMAC/chain.
- `run_layer_attribution_eval.py`: candidate attribution runner; use `--audit-grade-cost-cap-usd` with `--allow-external-cost` to stop before paid calls when the estimate exceeds budget.
- `scan_dms_manifest.py`: read-side scan of neutral iManage / NetDocuments export manifests.
- `generate_tenant_credentials.py`: generate tenant API-key registry JSON for server deployments.
- `promote_journal_to_corpus.py`: queue journal decisions for human-reviewed corpus promotion without touching recall locks.
- `smoke_local_daemon_acl.py`: smoke-test local daemon Origin/CORS and token gates for browser/Office clients.
