# Backend-Only Audit

## Active Runtime

- Canonical API entrypoint: `backend.main:app`
- Canonical request/response schemas: `backend/schemas.py`
- Active inference layers:
  - `layer1-lexicon/`
  - `layer2-embeddings/`
  - `layer3-clustering/`
  - `layer4-classification/`
  - `layer5-mosaic/`
  - `layer6-regression/`
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
  - `layer3-clustering/checkpoints/anomaly_detector.joblib`
  - `layer4-classification/model-1/checkpoints/best/`
  - `layer4-classification/model-2/checkpoints/best/`
  - `layer6-regression/checkpoints/`
- Archive training residue under `archive/training-checkpoints/`

## Legacy Compatibility Paths

- Thin legacy/demo paths remain archived rather than active:
  - `archive/frontend-demos/legacy/`
  - `api/`
  - `model-1/`
  - `model-2/`
  - `lexicon/`
  - `embeddings/`
  - `clustering/`

## Audit Findings

- The active backend is now API-only; demo UI serving moved out of FastAPI.
- The archived demo surfaces still integrate with the current backend contract and request richer classify metadata such as `include_offending_spans`, timings, cache state, and request ids.
- Exact match locations are implemented for lexicon-derived findings.
- Classifier outputs can now surface approximate top-risk windows via sliding-window inference without changing the external request shape.
- Regression remains an aggregate document-level synthesis layer and does not localize text directly.
- Import-time `torch` setup was moved out of module import to avoid heavy side effects during test import.
