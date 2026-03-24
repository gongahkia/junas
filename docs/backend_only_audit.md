# Backend-Only Audit

## Active Runtime

- Canonical API entrypoint: `src/noupe/backend/main.py` with compatibility shim `backend.main:app`
- Canonical request/response schemas: `src/noupe/backend/schemas.py`
- Active workflow root: `src/noupe/workflow/`
- Active workflow stages:
  - `src/noupe/workflow/layer0_parser/`
  - `src/noupe/workflow/layer1_lexicon/`
  - `src/noupe/workflow/layer2_embeddings/`
  - `src/noupe/workflow/layer3_clustering/`
  - `src/noupe/workflow/layer4_classification/`
  - `src/noupe/workflow/layer5_mosaic/`
  - `src/noupe/workflow/layer6_regression/`
- Supporting runtime code:
  - `src/noupe/configs/`
  - `src/noupe/helper/`
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
  - `artifacts/layer3_clustering/anomaly_detector.joblib`
  - `artifacts/layer4_classification/model1/best/`
  - `artifacts/layer4_classification/model2/best/`
  - `artifacts/layer6_regression/`
- Verify artifacts against `artifacts/manifest.json`
- Archive training residue under `archive/training-checkpoints/`

## Removed Root Duplicates

- The duplicate root shim folders were removed:
  - `clustering/`
  - `embeddings/`
  - `lexicon/`
  - `model-1/`
  - `model-2/`
- `backend/`, `api/`, and `configs/` remain as compatibility shims for older import paths and launcher entrypoints.

## Audit Findings

- The active backend is now API-only; demo UI serving moved out of FastAPI.
- The canonical runtime workflow now lives under `src/noupe/workflow/`, while `backend/`, `api/`, and `configs/` remain compatibility shims.
- The archived demo surfaces still integrate with the current backend contract and request richer classify metadata such as `include_offending_spans`, timings, cache state, and request ids.
- Exact match locations are implemented for lexicon-derived findings.
- Classifier outputs can now surface approximate top-risk windows via sliding-window inference without changing the external request shape.
- Mosaic now tracks rolling-window event evidence and exposes explainable aggregation fields rather than a single public counter.
- Regression remains an aggregate document-level synthesis layer and does not localize text directly.
- Import-time `torch` setup was moved out of module import to avoid heavy side effects during test import.
