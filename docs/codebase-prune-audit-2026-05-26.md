# Codebase Prune Audit - 2026-05-26

Kaypoh's active product path is the pivot architecture: deterministic pre-send PII/MNPI review, anonymization, jurisdiction packs, public evidence, and gated LLM adjudication. The legacy layer1-layer6 classifier stack is not part of that path.

## Kept

- `src/kaypoh/review/`: deterministic review engine, jurisdiction packs, citations, decisions, journals, metadata, and session state.
- `src/kaypoh/anonymize/`: placeholder rewriting and mapping persistence.
- `src/kaypoh/backend/`: FastAPI app, auth, schemas, cache, observability, SIEM.
- `src/kaypoh/client.py`: supported Python client.
- `src/kaypoh/ingest/parser_tools/`: active parser helper.
- `src/kaypoh/external/public_evidence/`: Exa, Tinyfish, Serper, and SerpAPI retrieval path.
- `src/kaypoh/advisory/llm_adjudicator/`: local/remote LLM adjudication.
- `src/kaypoh/external/privacy_guard.py`: required gate for external calls.
- `training/distillation/`: pivot-aligned local-student distillation pipeline.

## Removed

- root `helper/` duplicate.
- root `api/`, `backend/`, and `configs/` import shims.
- `src/kaypoh/helper/trello/`.
- `backend/workflow/` archived classifier copy.
- `docs/json/` old training corpus.
- `artifacts/manifest.json` and artifact manifest helper modules.
- `configs/eval_*.toml`, root `configs/`, and `src/kaypoh/configs/eval_*.toml`.
- `src/kaypoh/training/` and legacy classifier training entrypoints.
- `scripts/bootstrap_artifacts.py`, `scripts/data_quality_report.py`, `scripts/tune_thresholds.py`, `scripts/train_dev.sh`, and stale `scripts/run_test.py`.
- Generated historical `reports/historical/latency/latency_*.txt`.
- Quarantined legacy tests for the old classifier/mosaic/runtime-artifact stack.

## Notes

- `training/distillation/` stays because it supports the pivot's local-student LLM path.
- `test/fixtures/archived-latency-corpus/` stays as a historical benchmark fixture.
- The local PyInstaller packaging path now excludes cloud-capable retrieval/LLM modules.
- `uv.lock`, `Dockerfile`, and `docker-compose.yml` are now the canonical portable runtime path.
