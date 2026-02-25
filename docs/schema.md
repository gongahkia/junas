# I/O Schemas

Per-layer input/output contracts for the Noupe MNPI pipeline.

---

## Training Data — `TrainingDocument`

All training data JSON files must conform to this schema (validated by `scripts/validate_training_data.py` on commit).

```json
{
  "document_creation": "ISO 8601 datetime string (e.g. 2024-01-15T09:30:00)",
  "document_name": "string",
  "document_sentence_array": [
    {"text": "string", "label": "string"},
    {"text": "string", "label": "string"}
  ]
}
```

| Field | Type | Constraints |
|---|---|---|
| `document_creation` | `datetime` (ISO 8601) | required |
| `document_name` | `str` | required |
| `document_sentence_array` | `list[TrainingSentence]` | min 1 element |

`TrainingSentence`:

| Field | Type | Description |
|---|---|---|
| `text` | `str` | raw sentence text |
| `label` | `str` | class label (`"non"`, `"low"`, `"high"`) |

**Validation:** `scripts/validate_training_data.py <file.json>` — exits `0` on pass, `1` on failure. Runs automatically as a pre-commit hook on all staged `.json` files.

---

## `lexicon/` — Rule-based Lexicon Filter

### Input

`LexiconFilter.run(text: str)`

| Param | Type | Description |
|---|---|---|
| `text` | `str` | raw text to scan |

### Output

`LexiconResult` dataclass:

| Field | Type | Description |
|---|---|---|
| `flagged` | `bool` | `True` if any high-severity hit found |
| `high_risk_short_circuit` | `bool` | `True` if restricted entity or money threshold exceeded — downstream models skipped |
| `hits` | `list[LexiconHit]` | all matched rules |
| `restricted_entities_found` | `list[dict]` | matched entries from `restricted_list.json` |

`LexiconHit` dataclass:

| Field | Type | Values |
|---|---|---|
| `rule` | `str` | `money_threshold`, `pct_threshold`, `restricted_list`, `ner_money`, `ner_org`, `ner_person`, `presidio_credit_card`, `presidio_financial_id`, etc. |
| `matched_text` | `str` | the substring that triggered the rule |
| `severity` | `str` | `"high"` or `"info"` |
| `detail` | `str` | human-readable context (e.g. `parsed=2500000000 >= threshold=1000000`) |

### Config

`restricted_list.json`:

```json
{"entities": [{"name": "str", "ticker": "str", "isin": "str"}]}
```

---

## `embeddings/` — Sentence-BERT Vectorisation

### Input

| Param | Type | Description |
|---|---|---|
| `public_texts` | `list[str]` | corpus of public/safe text |
| `violation_texts` | `list[str]` | corpus of violation text |
| `all_texts` | `list[str]` | all sentences regardless of label (used for IsolationForest) |

### Output

| File | Shape | Description |
|---|---|---|
| `public_embeddings.npy` | `(n, 768)` | float32 ndarray, one 768-dim vector per public text |
| `violation_embeddings.npy` | `(m, 768)` | float32 ndarray, one 768-dim vector per violation text |
| `all_embeddings.npy` | `(n+m, 768)` | float32 ndarray, all sentences combined — used to train the Isolation Forest |

Model: `all-mpnet-base-v2` (768-dim embeddings).

---

## `clustering/` — Isolation Forest Anomaly Detector

### Training Input

`train(embeddings_path: str, save_path: str)`

| Param | Type | Description |
|---|---|---|
| `embeddings_path` | `str` | path to `.npy` file of all-sentence embeddings (public + violation), shape `(n, 768)` — use `all_embeddings.npy` |
| `save_path` | `str` | output path for the joblib checkpoint (default: `clustering/checkpoints/anomaly_detector.joblib`) |

### Training Output

Joblib checkpoint saved to `clustering/checkpoints/anomaly_detector.joblib` containing the fitted `IsolationForest` object.

### Inference Input

`MNPIAnomalyDetector.score(embedding: np.ndarray)`

| Param | Type | Description |
|---|---|---|
| `embedding` | `np.ndarray` shape `(768,)` | single document embedding vector |

### Inference Output

`dict`:

| Field | Type | Description |
|---|---|---|
| `anomaly_score` | `float` (0–1) | sigmoid-inverted IF score; higher = more anomalous. Use as regression input feature. |
| `is_anomaly` | `bool` | `True` if IF predicts this point as an outlier |
| `raw_score` | `float` | raw `score_samples` value from IF; lower (more negative) = more anomalous |

### Config

| Env Var | Default | Description |
|---|---|---|
| `IF_CONTAMINATION` | `0.05` | expected anomaly fraction in training data |
| `IF_MAX_FEATURES` | `0.3` | fraction of embedding dims sampled per tree (replaces PCA) |
| `IF_N_ESTIMATORS` | `100` | number of trees |

---

## `model-1/` — FinBERT Binary Classifier (Public vs Non-Public)

### Training Input

CSV with columns:

| Column | Type | Values |
|---|---|---|
| `text` | `str` | document text |
| `label` | `int` | `0` = public/safe, `1` = non-public/risk |

### Training Output

HuggingFace checkpoint saved to `model-1/checkpoints/best/` (model weights, tokenizer, config).

### Inference Input

`FinBERTClassifier.predict(text: str)`

| Param | Type | Description |
|---|---|---|
| `text` | `str` | single document to classify |

### Inference Output

`Model1Result` dataclass:

| Field | Type | Description |
|---|---|---|
| `label` | `str` | `"safe"` or `"risk"` |
| `confidence` | `float` | probability of the predicted class (0.0–1.0) |
| `risk_score` | `float` | probability of the risk class specifically (0.0–1.0) |

---

## `model-2/` — BERT Severity Classifier (High Risk vs Low Risk)

### Training Input

CSV with columns (violation corpus only — no public/safe data):

| Column | Type | Values |
|---|---|---|
| `text` | `str` | violation document text |
| `label` | `int` | `0` = low_risk, `1` = high_risk |

### Training Output

HuggingFace checkpoint saved to `model-2/checkpoints/best/` (model weights, tokenizer, config).

### Inference Input

`BERTSeverityClassifier.predict(text: str)`

| Param | Type | Description |
|---|---|---|
| `text` | `str` | single document to classify (already flagged as risk by Model-1) |

### Inference Output

`Model2Result` dataclass:

| Field | Type | Description |
|---|---|---|
| `label` | `str` | `"low_risk"` or `"high_risk"` |
| `confidence` | `float` | probability of the predicted class (0.0–1.0) |
| `high_risk_score` | `float` | probability of the high_risk class specifically (0.0–1.0) |

---

## `api/` — FastAPI Orchestration Layer

### `POST /classify`

**Request:**

```json
{"text": "str (min 1 char)"}
```

**Response:**

```json
{
  "classification": "SAFE | LOW_RISK | HIGH_RISK",
  "lexicon": {
    "flagged": "bool",
    "high_risk_short_circuit": "bool",
    "hits": [{"rule": "str", "matched_text": "str", "severity": "str", "detail": "str"}],
    "restricted_entities": [{"name": "str", "ticker": "str", "isin": "str"}]
  },
  "model1": {"label": "str", "confidence": "float", "risk_score": "float"} | null,
  "model2": {"label": "str", "confidence": "float", "high_risk_score": "float"} | null
}
```

`model1` is `null` when lexicon short-circuits. `model2` is `null` when Model-1 returns safe or is unavailable.

### `GET /health`

**Response:**

```json
{"status": "ok", "lexicon_loaded": "bool", "model1_loaded": "bool", "model2_loaded": "bool"}
```

---

## `regression/` — XGBoost (not implemented)

Intended input features:

| Feature | Source | Type |
|---|---|---|
| `lexicon_hits` | lexicon layer | `int` (count of high-severity hits) |
| `anomaly_score` | clustering layer | `float` |
| `bert_risk_score` | model-1 | `float` |
| `bert_severity_score` | model-2 | `float` |
| `mosaic_frequency` | Redis mosaic aggregation | `int` |

Intended output: single `float` MNPI risk probability (0.0–1.0).
