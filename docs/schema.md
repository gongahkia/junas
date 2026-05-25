# I/O Schemas

Per-layer input/output contracts for the Kaypoh MNPI pipeline.

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

Python integration surfaces for this contract:

- `KaypohClient`: synchronous wrapper over the HTTP API
- `AsyncKaypohClient`: asynchronous wrapper over the same HTTP API
- usage and run instructions: `docs/api/python_client.md`

Request:

```json
{
  "text": "string",
  "entity_id": "string | null",
  "debug": "boolean | null",
  "include_offending_spans": "boolean | null"
}
```

If `KAYPOH_API_KEY` is configured, include header:

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
  "mosaic": {
    "entity_id": "string",
    "escalated": "bool",
    "recent_event_count": "int",
    "unique_fragment_count": "int",
    "window_hours": "float",
    "threshold": "int",
    "escalation_reason": "string",
    "matched_event_ids": ["event ids"]
  } | null,
  "regression": {"risk_score": "float", "reasoning": "string"} | null,
  "public_evidence": {
    "status": "disabled|skipped|queried|error",
    "provider": "exa|tinyfish|none",
    "detail": "string",
    "queries": [
      {"query": "sanitized string", "blocked": "bool", "reason": "string"}
    ],
    "sources": [
      {
        "title": "string",
        "url": "string",
        "published_date": "string",
        "author": "string",
        "highlights": ["string"],
        "text": "string",
        "score": "float | null"
      }
    ],
    "privacy_ledger": [
      {
        "destination": "string",
        "operation": "string",
        "allowed": "bool",
        "reason": "string",
        "query": "sanitized string",
        "redactions": ["string"],
        "input_mode": "raw_text or structured_tokens for LLM ledger events; empty otherwise"
      }
    ]
  } | null,
  "llm_adjudication": {
    "status": "disabled|adjudicated|error",
    "provider": "vllm|ollama|none",
    "model": "string",
    "risk_label": "SAFE | LOW_RISK | HIGH_RISK | null",
    "public_status": "public|not_public|ambiguous|not_checked",
    "confidence": "float",
    "materiality_reason": "string",
    "matched_public_sources": ["url or source id"],
    "unverified_claims": ["string"],
    "review_recommendation": "string",
    "input_mode": "raw_text|structured_tokens",
    "output_clamped": "bool"
  } | null,
  "privacy_ledger": [
    {
      "destination": "string",
      "operation": "string",
      "allowed": "bool",
      "reason": "string",
      "query": "sanitized string",
      "redactions": ["string"],
      "input_mode": "raw_text or structured_tokens for LLM ledger events; empty otherwise"
    }
  ],
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
- `public_evidence` and `llm_adjudication` are populated only when their optional pipeline layers are configured.
- External retrieval layers must use sanitized queries only; the private document text and offending spans are not sent to public-source providers.
- `observability.degraded=true` means the pipeline returned a best-effort result because a configured layer that should have executed was unavailable or failed at runtime.

## API — `POST /review`

Pre-send review endpoint for customer workflows where a document is screened before it is sent. It scores PII and MNPI separately, applies source and destination jurisdictions with a strictest-wins policy, returns exact character offsets for highlights, and suggests redactions or rewrites.

Request:

```json
{
  "text": "string | null",
  "document_base64": "base64 text/docx/pdf | null",
  "document_filename": "string | null",
  "document_mime_type": "text/plain | application/pdf | application/vnd.openxmlformats-officedocument.wordprocessingml.document | null",
  "source_jurisdiction": "SG",
  "destination_jurisdiction": "SG",
  "document_type": "generic",
  "review_profile": "strict",
  "entity_id": "issuer or company name | null",
  "include_suggestions": true
}
```

Response:

```json
{
  "request_id": "string | null",
  "overall_risk": "SAFE | LOW_RISK | HIGH_RISK",
  "classification": "SAFE | LOW_RISK | HIGH_RISK",
  "document_score": "float",
  "pii_score": "float",
  "mnpi_score": "float",
  "source_jurisdiction": "SG",
  "destination_jurisdiction": "US",
  "jurisdictions_applied": ["SG", "US"],
  "jurisdiction_policy": "strictest_wins",
  "document_type": "research_note",
  "review_profile": "strict",
  "document": {
    "filename": "inline.txt",
    "mime_type": "text/plain",
    "extraction_method": "inline_text | base64_text | docx_xml | pypdf",
    "page_count": "int | null",
    "char_count": "int"
  },
  "findings": [
    {
      "id": "string",
      "category": "PII | MNPI",
      "rule": "string",
      "jurisdiction": "SG",
      "severity": "low | medium | high",
      "score": "float",
      "matched_text": "string",
      "start_char": "int",
      "end_char": "int",
      "reason": "string",
      "legal_basis": "string"
    }
  ],
  "suggestions": [
    {
      "id": "string",
      "finding_id": "string",
      "action": "redact | remove_or_hold | verify_or_rewrite",
      "replacement_text": "string",
      "rationale": "string"
    }
  ],
  "public_evidence": "same shape as POST /classify public_evidence | null",
  "llm_adjudication": "same shape as POST /classify llm_adjudication | null",
  "privacy_ledger": [],
  "timings_ms": {"extract": "float", "review": "float", "total": "float"}
}
```

Notes:

- `text` and `document_base64` are mutually optional at the field level, but at least one is required.
- `classification` is intentionally duplicated from `overall_risk` so existing classifier consumers can read a familiar field.
- External retrieval is only used when public evidence is enabled. It receives sanitized public-source queries, not private document text.
- The local LLM adjudicator is only used when enabled and allowed by the configured local/private base URL policy.

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
- if `KAYPOH_API_KEY` is configured, `X-API-Key` is also required for `POST /classify/batch`

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

Outputs from `src/kaypoh/workflow/layer2_embeddings/generate_embeddings.py`:

- `public_embeddings.npy`
- `violation_embeddings.npy`
- `all_embeddings.npy`

## Clustering

Isolation Forest checkpoint:

- `artifacts/layer3_clustering/anomaly_detector.joblib`

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

- `artifacts/layer4_classification/model1/best/`

Model-2 checkpoint:

- `artifacts/layer4_classification/model2/best/`

## Mosaic

Redis-backed state output:

```json
{
  "entity_id": "string",
  "escalated": "bool",
  "recent_event_count": "int",
  "unique_fragment_count": "int",
  "window_hours": "float",
  "threshold": "int",
  "escalation_reason": "string",
  "matched_event_ids": ["event ids"]
}
```

## Regression

Regression is optional and loaded only from trained checkpoint.
