# Scripts Folder

This folder contains operational and maintenance commands.

- `launch/`: UV-first backend launchers.
- `examples/`: runnable sync and async Python client examples.
- `check_python_clients.sh`: syntax and unit checks for the sync and async Python clients.
- `benchmark_latency.py`: latency benchmark runner for current HTTP surfaces.
- `benchmark_latency_corpus.sh`: shell wrapper for `test/fixtures/latency-corpus/`.
- `export_openapi_examples.py`: generate Postman and cURL examples from the current OpenAPI contract.
- `generate_accuracy_doc.py`: regenerate `docs/accuracy.md` from committed corpus locks.
- `preflight.py`: current runtime readiness checks.
- `erase_subject.py`: rebuild/query the HMAC subject-erasure reverse index and erase by subject value.
- `purge_mappings.py`: delete persisted anonymization mappings by document hash or retention age.
- `trace_request_logs.sh`: tail backend logs and filter by a specific `X-Request-ID`.
- `verify_runtime.sh`: UV-first verification for lint, focused tests, and live HTTP smoke.
- `watch_backend_status.py`: watch-style terminal dashboard for `/health`, `/ready`, `/diagnostics`, and `/metrics`.
- `clean_dev.sh`: local artifact cleanup.
