# Assumptions

## General
- all text input is pre-processed english
- single-document classification per API call
- batch classification is limited to 32 items per call
- models run on CPU by default; GPU auto-detected via `torch.cuda.is_available()`
- no auth by default unless `NOUPE_API_KEY` is configured
- archived demo surfaces call the backend over HTTP and are not mounted by FastAPI

## Lexicon Layer
- thresholds are configurable via env/config (`MNPI_ABS_THRESHOLD`, `MNPI_PCT_THRESHOLD`)
- lexicon score threshold defaults to a fixed `score_threshold`, but can be switched to dynamic mode with `LEXICON_SCORE_THRESHOLD_MODE=dynamic`
- dynamic lexicon threshold uses `score_threshold + (len(text) / dynamic_chars_per_point) * dynamic_threshold_increment`
- deterministic high-risk short-circuit triggers:
  - restricted entity match
  - money threshold breach
- restricted list schema: `{"entities": [{"name": str, "ticker": str, "isin": str}]}`
- spaCy model: `en_core_web_sm`
- Presidio recognizers include credit card/IBAN/financial-id/phone/email

## Labels
- canonical training labels are `non`, `low`, `high`
- ingestion normalizes legacy labels (`non-sensitive`, `low sensitivity`, `high sensitivity`) into canonical labels

## Embeddings
- model: `all-mpnet-base-v2` (768-dim)
- embeddings generated offline for training and on-the-fly at inference

## Model-1 (FinBERT)
- base model: `ProsusAI/finbert`
- labels: `0=safe`, `1=risk`
- threshold configurable with `MODEL1_THRESHOLD`
- inference runs over overlapping sliding windows so the response can expose an approximate top-risk window

## Model-2 (BERT Severity)
- base model: `bert-base-uncased`
- labels: `0=low_risk`, `1=high_risk`
- threshold configurable with `MODEL2_THRESHOLD`
- invoked only when model-1 predicts risk
- inference runs over overlapping sliding windows so the response can expose an approximate top-risk window

## Clustering (Isolation Forest)
- trained on `all_embeddings.npy`
- checkpoint path: `backend/workflow/layer3-clustering/checkpoints/anomaly_detector.joblib`
- `IF_CONTAMINATION`, `IF_MAX_FEATURES`, `IF_N_ESTIMATORS` are configurable

## Mosaic Aggregation
- Redis TTL-based fragment tracking
- escalation threshold: 10+ low-risk fragments for same entity within TTL
- if Redis is unavailable, mosaic layer is a no-op

## Regression
- regression is optional and only loaded when a trained model checkpoint exists
- no random/stub regression is used at runtime

## FastAPI Orchestration
- canonical app entrypoint is `backend.main:app`
- configurable layer order from `config.toml`/`PIPELINE_LAYERS`/`--layers`
- optional API key auth is enabled when `NOUPE_API_KEY` is set (applies to both `POST /classify` and `POST /classify/batch`)
- response includes per-layer outputs, final classification, timings, and observability metadata
- `include_offending_spans=true` adds exact lexicon spans and approximate classifier-window spans for `LOW_RISK` and `HIGH_RISK` responses
- health endpoint: `GET /health`
- readiness endpoint: `GET /ready`
- diagnostics endpoint: `GET /diagnostics`
- metrics endpoint: `GET /metrics`
- classify endpoint: `POST /classify`
- batch endpoint: `POST /classify/batch`
- Swagger and ReDoc are served by FastAPI at `/docs` and `/redoc`
