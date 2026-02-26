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
4. **Mosaic Aggregation** — Redis TTL-based fragment tracking. Escalates `LOW_RISK` outputs to `HIGH_RISK` if multiple occurrences are detected for the same entity within a configured time window.
5. **Regression** — Combines scores from previous layers (currently a stub, not yet fully trained).

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

Outputs `public_embeddings.npy`, `violation_embeddings.npy`, and `all_embeddings.npy` (all sentences combined, used to train the Isolation Forest). Requires `docs/json/` to contain valid training JSON files.

## Configuration

| Env Var | Default | Description |
|---|---|---|
| `MNPI_ABS_THRESHOLD` | `1000000` | Dollar amount that triggers lexicon high-risk flag |
| `MNPI_PCT_THRESHOLD` | `5.0` | Percentage that triggers lexicon high-risk flag |
| `MODEL1_THRESHOLD` | `0.5` | Model-1 risk probability cutoff |
| `MODEL2_THRESHOLD` | `0.5` | Model-2 high-risk probability cutoff |
| `IF_CONTAMINATION` | `0.05` | Expected anomaly fraction in IF training data |
| `IF_MAX_FEATURES` | `0.3` | Fraction of embedding dims each IF tree randomly samples |
| `IF_N_ESTIMATORS` | `100` | Number of trees in the Isolation Forest |
| `MOSAIC_TTL_HOURS` | `24` | Hours to retain history for an entity's occurrences |
| `MOSAIC_THRESHOLD` | `10` | Disparate low-risk events needed for high-risk escalation |

## Restricted List

Edit `lexicon/restricted_list.json` to add/remove entities. Schema:

```json
{"entities": [{"name": "...", "ticker": "...", "isin": "..."}]}
```

Matches are case-insensitive on name, exact on ticker/ISIN.

## Training the Anomaly Detector (Isolation Forest)

Requires `all_embeddings.npy` (output of `embeddings/generate_embeddings.py`). The IF trains on all known sentences (public + violation) so it can detect truly novel/unknown MNPI patterns as anomalies.

```sh
python3 clustering/isolation_forest.py all_embeddings.npy
```

Checkpoint saved to `clustering/checkpoints/anomaly_detector.joblib`. An optional second argument overrides the output path:

```sh
python3 clustering/isolation_forest.py all_embeddings.npy path/to/output.joblib
```

## Not Yet Implemented

- Complete XGBoost regression training (currently using a stub)

See `docs/assumption.md` for all assumed schemas and thresholds.
