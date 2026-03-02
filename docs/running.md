# Running Noupe

## Prerequisites

- Python 3.10+
- pip
- macOS/Linux

## Setup

```sh
pip install -r requirements.txt
python3 -m spacy download en_core_web_sm
```

## Preflight

```sh
python3 scripts/preflight.py
```

Use strict mode to fail on warnings:

```sh
python3 scripts/preflight.py --strict
```

## Running the API

```sh
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Healthcheck: `curl http://localhost:8000/health`

Readiness: `curl http://localhost:8000/ready`
Diagnostics: `curl http://localhost:8000/diagnostics`

Classify:

```sh
curl -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{"text": "Acme Corp is acquiring GlobalTech for $2.5 billion", "debug": false}'
```

API docs auto-served at `http://localhost:8000/docs` (Swagger) and `http://localhost:8000/redoc`.

## Pipeline Behavior

The `/classify` endpoint runs configured layers sequentially:

1. **Lexicon filter** — regex, spaCy NER, Presidio PII, restricted list cross-ref. Deterministic short-circuit to `HIGH_RISK` when a restricted entity or a money threshold breach is detected.
2. **Embedding generation** — sentence embedding with `all-mpnet-base-v2`.
3. **Clustering** — Isolation Forest anomaly score (if checkpoint exists).
4. **Model-1 (FinBERT)** — binary classifier: safe vs risk (if checkpoint exists).
5. **Model-2 (BERT)** — binary classifier: low_risk vs high_risk (if checkpoint exists and Model-1 predicts risk).
6. **Mosaic aggregation** — Redis TTL-based fragment tracking; can escalate repeated `LOW_RISK` entity activity.
7. **Regression** — optional final risk synthesis only when a trained regression checkpoint exists.

## Training Models

Both classification training scripts expect CSVs with columns `text,label`.

### Model-1 (FinBERT — public vs non-public)

Labels: `0` = public/safe, `1` = non-public/risk.

```sh
python3 layer4-classification/model-1/classifier.py data/train.csv data/val.csv
```

Checkpoint directory: `layer4-classification/model-1/checkpoints/best/`.

### Model-2 (BERT — high risk vs low risk)

Labels: `0` = low_risk, `1` = high_risk. Train on violation corpus only (no safe/public rows).

```sh
python3 layer4-classification/model-2/classifier.py data/train_violations.csv data/val_violations.csv
```

Checkpoint directory: `layer4-classification/model-2/checkpoints/best/`.

## Generating Embeddings

```sh
python3 layer2-embeddings/generate_embeddings.py
```

Outputs `public_embeddings.npy`, `violation_embeddings.npy`, and `all_embeddings.npy`.

## Training the Anomaly Detector (Isolation Forest)

```sh
python3 layer3-clustering/isolation_forest.py all_embeddings.npy
```

Checkpoint saved to `layer3-clustering/checkpoints/anomaly_detector.joblib`.

Optional custom output path:

```sh
python3 layer3-clustering/isolation_forest.py all_embeddings.npy path/to/output.joblib
```

## Configuration

Primary runtime config is `config.toml`. Environment variables override config values.

Notable keys:

- `MNPI_ABS_THRESHOLD`
- `MNPI_PCT_THRESHOLD`
- `MODEL1_THRESHOLD`
- `MODEL2_THRESHOLD`
- `IF_CONTAMINATION`
- `IF_MAX_FEATURES`
- `IF_N_ESTIMATORS`
- `MOSAIC_TTL_HOURS`
- `MOSAIC_THRESHOLD`
- `REDIS_HOST`
- `REDIS_PORT`
- `NOUPE_ALLOWED_ORIGINS` (comma-separated CORS origins)
- `NOUPE_API_KEY` (optional; when set, `POST /classify` requires `X-API-Key`)

## Restricted List

Edit `layer1-lexicon/restricted_list.json`:

```json
{"entities": [{"name": "...", "ticker": "...", "isin": "..."}]}
```

Matches are case-insensitive on name and exact on ticker/ISIN.

## Container Runtime

```sh
docker compose up --build
```

This starts:

- `noupe-api` on `http://localhost:8000`
- `redis` on `localhost:6379`
