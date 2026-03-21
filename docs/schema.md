# I/O Schemas

Per-layer input/output contracts for the Noupe MNPI pipeline.

## Training Data — `TrainingBatch`

```json
{
  "batch_name": "string",
  "batch_creation": "ISO 8601 datetime",
  "documents": [
    {
      "document_creation": "ISO 8601 datetime",
      "document_name": "string",
      "document_sentence_array": [
        {"text": "string", "label": "non|low|high"}
      ]
    }
  ]
}
```

Validation entrypoint:

```sh
python3 scripts/validate_training_data.py docs/json/batch*.json
```

## API — `POST /classify`

Request:

```json
{
  "text": "string",
  "entity_id": "string | null",
  "debug": "boolean | null",
  "include_offending_spans": "boolean | null"
}
```

If `NOUPE_API_KEY` is configured, include header:

`X-API-Key: <value>`

Response:

```json
{
  "request_id": "string | null",
  "classification": "SAFE | LOW_RISK | HIGH_RISK",
  "lexicon": {
    "flagged": "bool",
    "high_risk_short_circuit": "bool",
    "total_score": "float",
    "score_threshold": "float",
    "score_threshold_exceeded": "bool",
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
  "observability": {
    "degraded": "bool",
    "cache_status": "hit | miss | disabled",
    "active_pipeline": ["layer names"],
    "executed_layers": ["layer names"],
    "skipped_layers": ["layer names"],
    "layer_errors": [
      {"layer": "string", "phase": "startup|lazy_load|runtime", "message": "string"}
    ]
  },
  "offending_spans": [
    {
      "id": "string",
      "layer": "lexicon | model1 | model2",
      "rule": "string",
      "severity": "string",
      "matched_text": "string",
      "detail": "string",
      "start_char": "int",
      "end_char": "int",
      "start_line": "int",
      "start_column": "int",
      "end_line": "int",
      "end_column": "int",
      "is_exact": "bool",
      "char_length": "int",
      "line_span": "int",
      "context_before": "string",
      "context_after": "string",
      "score": "float | null",
      "score_type": "string | null",
      "window_index": "int | null",
      "window_count": "int | null",
      "window_token_count": "int | null",
      "window_stride": "int | null",
      "window_max_seq_len": "int | null"
    }
  ] | null,
  "embedding": ["float", "..."] | null,
  "timings_ms": {"layer_name": "float"}
}
```

Notes:

- `embedding` is included only when `debug=true`.
- `include_offending_spans=true` returns exact lexicon-derived locations and approximate classifier window locations when the final result is `LOW_RISK` or `HIGH_RISK`.
- `layer=lexicon` spans are exact rule hits; `layer=model1` and `layer=model2` spans are approximate top-risk windows from sliding-window classifier inference.
- `start_char`/`end_char` are zero-based offsets into the normalized request text; `end_char` is exclusive.
- `is_exact=true` means the span is an exact lexicon hit; `is_exact=false` means the span is an approximate classifier window.
- `context_before` and `context_after` include up to 48 characters of local surrounding text.
- `score_type` is usually `rule_score`, `risk_score`, or `high_risk_score`.
- `window_index` is zero-based and only populated for classifier-derived spans.
- `model1`/`model2`/`clustering`/`regression` may be `null` when layers are disabled or missing checkpoints.
- `observability.degraded=true` means the pipeline returned a best-effort result because a configured layer that should have executed was unavailable or failed at runtime.

## API — `POST /classify/batch`

Request:

```json
{
  "items": [
    {
      "text": "string",
      "entity_id": "string | null",
      "debug": "boolean | null",
      "include_offending_spans": "boolean | null"
    }
  ]
}
```

Notes:

- maximum batch size is `32`
- each item reuses the same request contract as `POST /classify`
- if `NOUPE_API_KEY` is configured, `X-API-Key` is also required for `POST /classify/batch`

Response:

```json
{
  "results": [
    {
      "request_id": "string | null",
      "classification": "SAFE | LOW_RISK | HIGH_RISK"
    }
  ]
}
```

Each batch item returns the same full response shape as `POST /classify`.

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
  "missing_required_layers": ["layer names"],
  "warming_required_layers": ["layer names"],
  "reasons": ["string"]
}
```

## API — Diagnostics

`GET /diagnostics`

```json
{
  "status": "ok",
  "pipeline": ["layer names"],
  "loaded_layers": ["layer names"],
  "lazy_layers": ["layer names"],
  "warming_required_layers": ["layer names"],
  "load_errors": [{"layer": "string", "phase": "startup|lazy_load", "error": "string"}],
  "startup_timings_ms": {"layer_name": "float"},
  "metrics_mode": "singleprocess|multiprocess",
  "dependency_status": {
    "redis": {
      "status": "disabled|unknown|up|down",
      "configured": "bool",
      "healthy": "bool | null",
      "detail": "string"
    }
  },
  "runtime_layer_errors": {
    "layer_name": {"count": "int", "last_seen": "ISO 8601 datetime | null", "last_message": "string"}
  }
}
```

## API — Metrics

`GET /metrics`

- Standard Prometheus exposition format generated by `prometheus_client`.
- Supports single-process dev mode by default.
- Supports multiprocess aggregation when `PROMETHEUS_MULTIPROC_DIR` is set before worker startup.

## API Docs

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI JSON: `/openapi.json`

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
