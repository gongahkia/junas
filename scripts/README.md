# Scripts Folder

This folder contains operational and maintenance commands.

- `launch/`: runnable backend launchers
- `examples/`: runnable sync and async Python client examples
- `check_python_clients.sh`: syntax and unit checks for the sync and async Python clients; used by tracked git hooks
- `benchmark_latency.py`: latency benchmark runner
- `benchmark_latency_corpus.sh`: shell wrapper that benchmarks all `.txt` files in `test/fixtures/latency-corpus/` by default
- `bootstrap_artifacts.py`: verify, hydrate, or regenerate runtime artifacts from the committed manifest
- `export_openapi_examples.py`: generate Postman and cURL examples from the current OpenAPI contract
- `generate_accuracy_doc.py`: regenerate `docs/accuracy.md` from committed corpus locks
- `preflight.py`: runtime readiness checks
- `purge_mappings.py`: delete persisted anonymization mappings by document hash or retention age
- `trace_request_logs.sh`: tail backend logs and filter by a specific `X-Request-ID`
- `verify_runtime.sh`: one-command verification that runs linting, type checks, tests, and end-to-end smoke checks across lexicon, embedding, clustering, model1, model2, regression, and a temporary Redis-backed mosaic flow
- `watch_backend_status.py`: watch-style terminal dashboard for `/health`, `/ready`, `/diagnostics`, and `/metrics` summaries
- `validate_training_data.py`: corpus validation
- `data_quality_report.py`: corpus quality reporting
- `tune_thresholds.py`: threshold tuning utility
- `clean_dev.sh`: local artifact cleanup
- `train_dev.sh`: interactive training launcher
