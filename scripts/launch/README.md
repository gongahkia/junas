# Launcher Scripts

This folder contains the runnable shell launchers for the repository.

- `run_backend_only.sh`: backend-only startup
- `run_dev.sh`: local backend launcher with reload enabled by default
- `run_prod.sh`: stricter production-style backend launcher with multi-worker metrics support
- `common.sh`: shared launcher helpers

Optional launcher telemetry:

- Set `KAYPOH_LAUNCH_TELEMETRY_FILE=reports/launch_telemetry.json`
- Supported by backend-only, dev, and prod launchers
- Writes startup readiness + diagnostics snapshots after the backend reports ready
