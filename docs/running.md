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

## Running the API

```sh
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Healthcheck: `curl http://localhost:8000/health`

Classify: `curl -X POST http://localhost:8000/classify -H "Content-Type: application/json" -d '{"text": "Acme Corp is acquiring GlobalTech for $2.5 billion"}'`

API docs auto-served at `http://localhost:8000/docs` (Swagger) and `http://localhost:8000/redoc`.

## Pipeline Behavior

The `/classify` endpoint runs layers sequentially:

1. **Lexicon filter** — regex, spaCy NER, Presidio PII, restricted list cross-ref. Short-circuits to `HIGH_RISK` if a restricted entity or financial figure above threshold ($1M default) is detected.
2. **Model-1 (FinBERT)** — binary classifier: safe vs risk. Only runs if lexicon doesn't short-circuit. Skipped if checkpoint doesn't exist (falls back to lexicon-only).
3. **Model-2 (BERT)** — binary classifier: low_risk vs high_risk. Only runs if Model-1 outputs risk. Skipped if checkpoint doesn't exist (defaults to `LOW_RISK`).

## Training Models

Both training scripts expect CSVs with columns `text,label`.

### Model-1 (FinBERT — public vs non-public)

Labels: `0` = public/safe, `1` = non-public/risk.

```sh
python3 model-1/classifier.py data/train.csv data/val.csv
```

Checkpoints saved to `model-1/checkpoints/best/`.

### Model-2 (BERT — high risk vs low risk)

Labels: `0` = low_risk, `1` = high_risk. Train on violation corpus only (no safe/public data).

```sh
python3 model-2/classifier.py data/train_violations.csv data/val_violations.csv
```

Checkpoints saved to `model-2/checkpoints/best/`.

## Generating Embeddings

```sh
python3 embeddings/generate_embeddings.py
```

Outputs `public_embeddings.npy` and `violation_embeddings.npy`. Requires `public_texts` and `violation_texts` variables to be defined (currently a placeholder script).

## Configuration

| Env Var | Default | Description |
|---|---|---|
| `MNPI_ABS_THRESHOLD` | `1000000` | Dollar amount that triggers lexicon high-risk flag |
| `MNPI_PCT_THRESHOLD` | `5.0` | Percentage that triggers lexicon high-risk flag |
| `MODEL1_THRESHOLD` | `0.5` | Model-1 risk probability cutoff |
| `MODEL2_THRESHOLD` | `0.5` | Model-2 high-risk probability cutoff |

## Restricted List

Edit `lexicon/restricted_list.json` to add/remove entities. Schema:

```json
{"entities": [{"name": "...", "ticker": "...", "isin": "..."}]}
```

Matches are case-insensitive on name, exact on ticker/ISIN.

## Not Yet Implemented

- Clustering (Isolation Forest anomaly detection)
- Mosaic aggregation (Redis TTL-based fragment tracking)
- XGBoost regression (multivariate risk scoring)

See `docs/assumption.md` for all assumed schemas and thresholds.
