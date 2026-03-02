# I/O Schemas

Per-layer input/output contracts for the Noupe MNPI pipeline.

## Training Data — `TrainingDocument`

```json
{
  "document_creation": "ISO 8601 datetime",
  "document_name": "string",
  "document_sentence_array": [
    {"text": "string", "label": "non|low|high"}
  ]
}
```

Validation entrypoint:

```sh
python3 scripts/validate_training_data.py docs/json/*.json
```

## API — `POST /classify`

Request:

```json
{
  "text": "string",
  "entity_id": "string | null",
  "debug": "boolean | null"
}
```

Response:

```json
{
  "classification": "SAFE | LOW_RISK | HIGH_RISK",
  "lexicon": {
    "flagged": "bool",
    "high_risk_short_circuit": "bool",
    "total_score": "float",
    "hits": [
      {
        "rule": "string",
        "matched_text": "string",
        "severity": "high|info",
        "detail": "string",
        "score": "float"
      }
    ],
    "restricted_entities": [
      {"name": "string", "ticker": "string", "isin": "string"}
    ]
  },
  "model1": {"label": "string", "confidence": "float", "risk_score": "float"} | null,
  "model2": {"label": "string", "confidence": "float", "high_risk_score": "float"} | null,
  "clustering": {"anomaly_score": "float", "is_anomaly": "bool", "raw_score": "float"} | null,
  "mosaic": {"escalated": "bool", "count": "int"} | null,
  "regression": {"risk_score": "float", "reasoning": "string"} | null,
  "embedding": ["float", "..."] | null
}
```

Notes:

- `embedding` is included only when `debug=true`.
- `model1`/`model2`/`clustering`/`regression` may be `null` when layers are disabled or missing checkpoints.

## API — Health

`GET /health`

```json
{
  "status": "ok",
  "lexicon_loaded": "bool",
  "model1_loaded": "bool",
  "model2_loaded": "bool",
  "embedding_loaded": "bool",
  "clustering_loaded": "bool",
  "mosaic_loaded": "bool",
  "regression_loaded": "bool"
}
```

## API — Readiness

`GET /ready`

```json
{
  "status": "ok|degraded",
  "ready": "bool",
  "pipeline": ["layer names"],
  "missing_required_layers": ["layer names"]
}
```

## Lexicon Output

`LexiconResult`:

- `flagged: bool`
- `high_risk_short_circuit: bool`
- `total_score: float`
- `hits: list[LexiconHit]`
- `restricted_entities_found: list[dict]`

`LexiconHit`:

- `rule: str`
- `matched_text: str`
- `severity: "high" | "info"`
- `detail: str`
- `score: float`

## Embeddings

Outputs from `layer2-embeddings/generate_embeddings.py`:

- `public_embeddings.npy`
- `violation_embeddings.npy`
- `all_embeddings.npy`

## Clustering

Isolation Forest checkpoint:

- `layer3-clustering/checkpoints/anomaly_detector.joblib`

Inference output:

```json
{
  "anomaly_score": "float",
  "is_anomaly": "bool",
  "raw_score": "float"
}
```

## Classification Models

Model-1 checkpoint:

- `layer4-classification/model-1/checkpoints/best/`

Model-2 checkpoint:

- `layer4-classification/model-2/checkpoints/best/`

## Mosaic

Redis-backed state output:

```json
{
  "escalated": "bool",
  "count": "int"
}
```

## Regression

Regression is optional and loaded only from trained checkpoint.
