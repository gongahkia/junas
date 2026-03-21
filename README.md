# Noupe

Noupe is a backend-first MNPI screening repository.

## Layout

- `api/`: compatibility exports for older `api.main` and `api.schemas` imports
- `archive/`: archived demo frontends and archived training checkpoints
- `backend/`: FastAPI runtime, schemas, observability, and the active workflow stages
- `configs/`: runtime config helpers and evaluation config files
- `docs/`: operator docs, schema docs, architecture notes, and sample corpus JSON
- `helper/`: shared utilities used by runtime and training code
- `reports/`: generated benchmark and training reports
- `scripts/`: launchers, benchmarking, preflight, validation, and maintenance commands
- `test/`: automated tests and fixtures
- `training/`: end-to-end model and pipeline training entrypoints

## Canonical Runtime Paths

- FastAPI app: `backend.main:app`
- Workflow stages: `backend/workflow/`
- Backend-only launcher: `scripts/launch/run_backend_only.sh`
- Dev launcher: `scripts/launch/run_dev.sh`
- Production-style launcher: `scripts/launch/run_prod.sh`

## Common Commands

```sh
./scripts/launch/run_backend_only.sh
./scripts/launch/run_dev.sh
./scripts/launch/run_prod.sh
./.venv/bin/python -m unittest discover -s test -p 'test*.py'
```
