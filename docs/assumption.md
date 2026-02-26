# Assumptions

## General
- all text input is pre-processed english (OCR/NER upstream already handled)
- single-document classification per API call (batch via async client)
- models run on CPU by default; GPU auto-detected via `torch.cuda.is_available()`
- no auth on FastAPI endpoints (add middleware per deployment)

## Lexicon Layer
- financial figure threshold: $1M USD absolute, 5% of assets percentage — configurable via env vars `MNPI_ABS_THRESHOLD` and `MNPI_PCT_THRESHOLD`
- restricted list stored as static JSON (`lexicon/restricted_list.json`), schema: `{"entities": [{"name": str, "ticker": str, "isin": str}]}`
- spaCy model: `en_core_web_sm` (swap to `en_core_web_trf` for prod accuracy)
- Presidio recognizers: default english recognizers (credit card, IBAN, SSN, etc) + custom financial recognizer
- MONEY regex patterns cover USD, EUR, GBP, JPY and generic `$X.XX` formats
- restricted list match is case-insensitive substring on entity name and exact on ticker/ISIN

## Embeddings
- model: `all-mpnet-base-v2` (768-dim) as already in `embeddings/generate_embeddings.py`
- embeddings pre-computed offline; inference uses same model for on-the-fly encoding
- batch_size=32 for training, batch_size=1 for real-time inference

## Model-1 (FinBERT — Public vs Non-Public)
- base model: `ProsusAI/finbert` from HuggingFace
- binary labels: 0=public (safe), 1=non-public (risk)
- training data schema: CSV with columns `text,label` where label ∈ {0,1}
- default hyperparams: lr=2e-5, epochs=3, batch=16, max_seq_len=512
- positive class: internal memos, draft filings, slack logs
- negative class: SEC EDGAR filings, reuters feeds, press releases
- threshold for risk classification: 0.5 (configurable)

## Model-2 (BERT — High Risk vs Low Risk)
- base model: `bert-base-uncased` from HuggingFace
- binary labels: 0=low_risk, 1=high_risk
- trained ONLY on violation corpus (no public/safe data)
- class weights computed as inverse frequency to handle 90/10 imbalance
- training data schema: CSV with columns `text,label` where label ∈ {0,1}
- default hyperparams: lr=2e-5, epochs=5, batch=16, max_seq_len=512
- only invoked when model-1 outputs risk (label=1)

## Clustering (Isolation Forest — `clustering/isolation_forest.py`)
- fits on all-sentence embeddings (public + violation combined, `all_embeddings.npy`) produced by `embeddings/generate_embeddings.py` — trains on the full distribution of known data so the IF flags only true unknown unknowns of MNPI
- no explicit PCA: `max_features=0.3` (random subsampling of ~230/768 dims per tree) handles the curse of dimensionality without the p >> n instability of PCA on small datasets
- `contamination=0.05`: upper bound on expected anomaly fraction in training data — lower = stricter
- `n_estimators=100`: sufficient for datasets in the hundreds; raise as data grows
- checkpoint saved as `clustering/checkpoints/anomaly_detector.joblib` via `joblib`
- inference: `MNPIAnomalyDetector.score(embedding)` returns `anomaly_score` (0–1, sigmoid-inverted; higher = more anomalous), `is_anomaly` (bool), and `raw_score` (raw IF value)
- `anomaly_score` is intended as a soft input feature for XGBoost regression, not a hard decision gate
- all three IF hyperparameters are configurable via env vars: `IF_CONTAMINATION`, `IF_MAX_FEATURES`, `IF_N_ESTIMATORS`
- plan to retrain when switching from synthetic to real data; synthetic corpus produces a narrower "normal" boundary than real-world data

## Regression (not implemented)
- XGBoost multivariate regression combines lexicon hits, anomaly score, BERT score, mosaic freq
- not implemented in this iteration

## Mosaic Aggregation
- Redis TTL-based fragment tracking (24-48h window)
- escalation threshold: 10+ low-risk fragments on same entity → high risk

## FastAPI Orchestration
- pipeline: lexicon → embeddings → clustering → model-1 → (if risk) model-2 → mosaic → regression
- response includes per-layer scores and final classification
- classification enum: SAFE, LOW_RISK, HIGH_RISK
- lexicon layer can short-circuit to HIGH_RISK if restricted list entity detected or financial threshold exceeded
- healthcheck at GET /health
- classify endpoint at POST /classify
