# Assumptions

## General
- all text input is pre-processed english
- single-document classification per API call
- batch classification is limited to 32 items per call
- models run on CPU by default; GPU auto-detected via `torch.cuda.is_available()`
- no auth by default unless `KAYPOH_API_KEY` is configured
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
- checkpoint path: `artifacts/layer3_clustering/anomaly_detector.joblib`
- `IF_CONTAMINATION`, `IF_MAX_FEATURES`, `IF_N_ESTIMATORS` are configurable

## Mosaic Aggregation
- Redis rolling-window event tracking keyed by entity
- escalation threshold is evaluated on unique low-risk fragment hashes within the active window
- response exposes `unique_fragment_count`, `recent_event_count`, and `matched_event_ids`
- if Redis is unavailable, mosaic layer is a no-op

## Regression
- regression is optional and only loaded when a trained model checkpoint exists
- no random/stub regression is used at runtime

## Public Evidence
- public-source retrieval is optional and disabled by default
- external providers receive only sanitized entity/ticker/event/date queries
- original request text, offending spans, emails, phone numbers, and exact private financial values are not sent externally
- `privacy_ledger` records every outbound query decision

## Local LLM Adjudication
- local LLM adjudication is optional and disabled by default
- the local model may receive the full request text only when served from a local/private base URL or when explicitly allowed by config
- adjudication output is structured JSON and can downgrade model-only risk when public evidence supports that the claim is already public
- deterministic high-risk short-circuit floors remain high risk

## FastAPI Orchestration
- canonical app entrypoint is `kaypoh.backend.main:app` with compatibility shim `backend.main:app`
- configurable layer order from `config.toml`/`PIPELINE_LAYERS`/`--layers`
- optional API key auth is enabled when `KAYPOH_API_KEY` is set (applies to both `POST /classify` and `POST /classify/batch`)
- response includes per-layer outputs, final classification, timings, and observability metadata
- `include_offending_spans=true` adds exact lexicon spans and approximate classifier-window spans for `LOW_RISK` and `HIGH_RISK` responses
- health endpoint: `GET /health`
- readiness endpoint: `GET /ready`
- diagnostics endpoint: `GET /diagnostics`
- metrics endpoint: `GET /metrics`
- classify endpoint: `POST /classify`
- batch endpoint: `POST /classify/batch`
- Swagger and ReDoc are served by FastAPI at `/docs` and `/redoc`
