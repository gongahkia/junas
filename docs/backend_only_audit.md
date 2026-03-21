# Backend-Only Audit

## Active Runtime

- Canonical API entrypoint: `backend.main:app`
- Canonical request/response schemas: `backend/schemas.py`
- Active workflow root: `backend/workflow/`
- Active workflow stages:
  - `backend/workflow/layer0-parser/`
  - `backend/workflow/layer1-lexicon/`
  - `backend/workflow/layer2-embeddings/`
  - `backend/workflow/layer3-clustering/`
  - `backend/workflow/layer4-classification/`
  - `backend/workflow/layer5-mosaic/`
  - `backend/workflow/layer6-regression/`
- Supporting runtime code:
  - `configs/`
  - `helper/`
  - `scripts/`
  - `training/`
  - `test/`

## Archived Demo Surfaces

- Archived frontend demos now live under `archive/frontend-demos/`
- Active backend runtime no longer mounts `/chat`, `/email`, or `/slack`
- Demo launch is handled by `scripts/launch/run_dev.sh` and `scripts/launch/run_prod.sh`
- The canonical backend-only run path is `scripts/launch/run_backend_only.sh`

## Active Runtime Artifacts

- Keep:
  - `backend/workflow/layer3-clustering/checkpoints/anomaly_detector.joblib`
  - `backend/workflow/layer4-classification/model-1/checkpoints/best/`
  - `backend/workflow/layer4-classification/model-2/checkpoints/best/`
  - `backend/workflow/layer6-regression/checkpoints/`
- Archive training residue under `archive/training-checkpoints/`

## Removed Root Duplicates

- The duplicate root shim folders were removed:
  - `clustering/`
  - `embeddings/`
  - `lexicon/`
  - `model-1/`
  - `model-2/`
- `api/` remains as the only compatibility shim because it preserves older import paths for `api.main` and `api.schemas`.

## Audit Findings

- The active backend is now API-only; demo UI serving moved out of FastAPI.
- The active runtime workflow now lives under `backend/workflow/`, which keeps the repository root focused on runtime, docs, scripts, tests, and archive surfaces.
- The archived demo surfaces still integrate with the current backend contract and request richer classify metadata such as `include_offending_spans`, timings, cache state, and request ids.
- Exact match locations are implemented for lexicon-derived findings.
- Classifier outputs can now surface approximate top-risk windows via sliding-window inference without changing the external request shape.
- Regression remains an aggregate document-level synthesis layer and does not localize text directly.
- Import-time `torch` setup was moved out of module import to avoid heavy side effects during test import.
