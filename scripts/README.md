# Scripts Folder

This folder contains operational and maintenance commands.

- `launch/`: runnable backend and demo launchers
- `benchmark_latency.py`: latency benchmark runner
- `benchmark_latency_corpus.sh`: shell wrapper that benchmarks all `.txt` files in `test/fixtures/latency-corpus/` by default
- `bootstrap_artifacts.py`: verify, hydrate, or regenerate runtime artifacts from the committed manifest
- `preflight.py`: runtime readiness checks
- `validate_training_data.py`: corpus validation
- `data_quality_report.py`: corpus quality reporting
- `tune_thresholds.py`: threshold tuning utility
- `clean_dev.sh`: local artifact cleanup
- `train_dev.sh`: interactive training launcher
