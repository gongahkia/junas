# Scripts Folder

This folder contains stable CLI entrypoints. Keep paths stable because docs, fixtures, and operator runbooks reference them directly.

Runtime and launch:
- `launch/`: UV-first backend launchers.
- `demo.sh`, `demo.py`, `preflight.py`, `preflight_production.py`, `verify_runtime.sh`, `watch_backend_status.py`, `trace_request_logs.sh`, `trace_policy_decision.sh`, `smoke_local_daemon_acl.py`

Evaluation and corpus:
- `recall_gate.py`, `generate_accuracy_doc.py`, `generate_detector_dashboard.py`, `check_promoted_lock_freshness.py`, `check_false_negative_risk.py`, `check_precision_risk.py`, `benchmark_latency.py`, `benchmark_latency_corpus.sh`, `check_latency_slo.py`
- `fetch_tab_fixture.sh`, `run_tab_eval.py`: clone the independent TAB fixture locally and report span-level P/R/F2 without touching candidate-corpus locks.
- `fetch_ai4privacy_fixture.py`, `run_ai4privacy_eval.py`: fetch the English ai4privacy `pii-masking-200k` fixture and report semi-independent recall on documented US/UK label-proxy slices.
- candidate corpus, autolabel, bucketing, stage-gate, layer-attribution, defensibility, and frequency-table scripts

Admin and audit:
- `export_audit_pack.py`, `verify_audit_pack.py`, `verify_journal.py`, `erase_subject.py`, `purge_mappings.py`
- `generate_tenant_credentials.py`, `scan_dms_manifest.py`, `check_retention_manifest.py`, `promote_journal_to_corpus.py`, `export_false_positive_queue.py`, `export_false_negative_queue.py`
- `generate_product_value_report.py`: privacy-safe JSON report from Prometheus text metrics.

Packaging and clients:
- `package_macos_desktop.sh`, `package_browser_extension.sh`, `render_outlook_manifest.py`, `validate_outlook_manifest.py`, `check_python_clients.sh`, `export_openapi_examples.py`
- `examples/`: runnable sync and async Python client examples.
