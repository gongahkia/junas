# Noupe

Noupe is a backend-first MNPI screening repository.

## Layout

- `api/`: compatibility exports for older `api.main` and `api.schemas` imports
- `archive/`: archived demo frontends and archived training checkpoints
- `artifacts/`: runtime checkpoints verified by `artifacts/manifest.json`
- `backend/`: compatibility exports for `backend.main:app` and related legacy imports
- `configs/`: compatibility exports for runtime config helpers
- `docs/`: operator docs, schema docs, architecture notes, and sample corpus JSON
- `reports/`: generated benchmark and training reports
- `scripts/`: launchers, benchmarking, preflight, validation, and maintenance commands
- `src/noupe/`: canonical Python package for runtime, workflow, config, helper, and training code
- `test/`: automated tests and fixtures
- `training/`: end-to-end model and pipeline training entrypoints

## Canonical Runtime Paths

- FastAPI app: `src/noupe/backend/main.py` with compatibility shim `backend.main:app`
- Workflow stages: `src/noupe/workflow/`
- Runtime artifacts: `artifacts/` with manifest verification in `artifacts/manifest.json`
- Backend-only launcher: `scripts/launch/run_backend_only.sh`
- Dev launcher: `scripts/launch/run_dev.sh`
- Production-style launcher: `scripts/launch/run_prod.sh`

## Common Commands

```sh
./scripts/launch/run_backend_only.sh
./scripts/launch/run_dev.sh
./scripts/launch/run_prod.sh
./scripts/verify_runtime.sh
python3 scripts/bootstrap_artifacts.py --sync-from-legacy
python3 scripts/preflight.py --strict
./.venv/bin/python -m unittest discover -s test -p 'test*.py'
```

`./scripts/verify_runtime.sh` is the end-to-end verifier: it runs the static checks, test suite, and live smoke coverage for every runtime layer, including a temporary local Redis-backed mosaic pass.
