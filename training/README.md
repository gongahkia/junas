# Training experiments

Training is separate from the default classifier. `distillation/` contains teacher collection, student training, corpus evaluation and a promotion gate. `severity_calibrator/` fits a transparent decision table from manually prepared, sanitized labelled preferences.

Use independent reviewed data and preserve held-out test splits. Do not train on a benchmark and then present its regression score as evidence of generalization. Provider calls require explicit configuration. Teacher ledgers are research artifacts under `JUNAS_CACHE_DIR`, not production audit records.
