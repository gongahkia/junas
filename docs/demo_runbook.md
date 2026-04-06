# Noupe Internal Demo Runbook

Presentation script covering **(a) solution architecture** and **(b) API versatility**.

---

## Prerequisites

```sh
cd /Users/gongahkia/Desktop/coding/smu/Noupe
source .venv/bin/activate
redis-server &                          # mosaic layer needs Redis
./scripts/launch/run_backend_only.sh    # starts FastAPI on :8000
```

Verify backend is live:

```sh
curl -s http://localhost:8000/ready | python3 -m json.tool
```

---

## Part A — Solution Architecture

### A1. Training Data

**Corpus**: 4 JSON batches (`docs/json/batch1–4.json`), **2,446 sentences** across labeled documents.

| Label | Count | % |
|-------|-------|---|
| High (MNPI) | 763 | 31.2% |
| Low (suspicious) | 441 | 18.0% |
| Non (safe) | 1,242 | 50.8% |

Each sentence is annotated at the sentence level inside document-level JSON objects with `document_name`, `document_creation`, and `document_sentence_array`.

**Show**: open `docs/json/batch1.json` and scroll through a few documents — point out the `text` + `label` fields.

```sh
python3 -c "
import json, pathlib, collections
docs=[]
for p in sorted(pathlib.Path('docs/json').glob('batch*.json')):
    docs.extend(json.loads(p.read_text()))
labels=collections.Counter(s['label'].lower() for d in docs for s in d['document_sentence_array'])
print(f'Documents: {len(docs)}')
print(f'Sentences: {sum(labels.values())}')
for k,v in sorted(labels.items()): print(f'  {k}: {v}')
"
```

---

### A2. Pipeline Architecture (7 Layers)

Walk through the pipeline diagram:

```
Input text
  │
  ▼
┌─────────────────────────────────────────────────┐
│  Layer 1 — LEXICON (rule-based)                 │
│  spaCy NER · Presidio PII · regex · restricted  │
│  list · weighted scoring                        │
│  → can SHORT-CIRCUIT to HIGH_RISK               │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│  Layer 2 — EMBEDDINGS                           │
│  Sentence-BERT (all-mpnet-base-v2, 768-dim)     │
│  SHA256-keyed LRU cache (512 slots)             │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│  Layer 3 — CLUSTERING                           │
│  Isolation Forest (100 trees, 5% contamination) │
│  anomaly_score ∈ [0,1] via sigmoid inversion    │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│  Layer 4a — MODEL 1 (FinBERT)                   │
│  Binary: safe / risk                            │
│  Sliding window (512 tok, stride 128)           │
│  Temperature-calibrated                         │
│  → if "safe" → SKIP Model 2                     │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│  Layer 4b — MODEL 2 (BERT base uncased)         │
│  Binary: low_risk / high_risk                   │
│  Only runs on violation corpus (gated by M1)    │
│  Inverse-frequency class weighting              │
│  Temperature-calibrated                         │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│  Layer 5 — MOSAIC (optional, needs Redis)       │
│  Per-entity rolling window (24h TTL)            │
│  Escalates low→high when unique fragments ≥ 10  │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│  Layer 6 — REGRESSION (XGBoost)                 │
│  Ensembles 7 features from all upstream layers  │
│  Outputs final risk_score ∈ [0,1]               │
│  safe ≤0.4 | low_risk ≤0.7 | high_risk >0.7    │
└─────────────────────────────────────────────────┘
```

**Talking point**: each layer can only *raise* the classification floor, never lower it — `max_classification()` logic ensures monotonic escalation.

---

### A3. Heuristics — Lexicon Layer Detail

The lexicon layer (`src/noupe/workflow/layer1_lexicon/filter.py`) applies **5 rule families**, each with configurable weights:

| Rule | Trigger | Severity | Weight |
|------|---------|----------|--------|
| `money_threshold` | Dollar amount ≥ $1M (supports $, €, ¥, K/M/B/T multipliers) | HIGH | 2.0 |
| `pct_threshold` | Percentage ≥ 5% | HIGH | 1.0 |
| `restricted_list` | Entity name / ticker / ISIN match against watchlist | HIGH | 5.0 |
| `ner_event_entity_correlation` | Critical event keyword + org/person entity in same sentence (e.g. "merger" + "Acme Corp") | HIGH | 4.0 |
| `ner_org_money_correlation` | Org + money entity co-occurrence | INFO | 1.0 |
| spaCy NER entities (ORG, PERSON, MONEY, GPE, LAW) | Entity detection | INFO | 0.5 each |
| Presidio PII (CREDIT_CARD, IBAN, FINANCIAL_ID) | PII detection | HIGH | 5.0 each |
| Presidio PII (PHONE, EMAIL) | PII detection | INFO | 1.0 each |

**Critical event keywords**: merger, acquisition, buyout, takeover, bankruptcy, dividend, earnings, guidance, scandal, fraud, resignation, layoff, etc.

**Short-circuit**: restricted entity match OR money threshold breach → immediate HIGH_RISK, skip downstream ML layers.

**Threshold modes**: static (fixed 10.0) or dynamic (scales with text length).

---

### A4. ML Models Detail

| | Model 1 | Model 2 |
|---|---|---|
| **Base** | `ProsusAI/finbert` | `bert-base-uncased` |
| **Task** | public vs non-public (binary) | low vs high risk (binary) |
| **Training samples** | All 2,446 sentences | ~1,204 violation-only sentences (low+high) |
| **Epochs** | 3 | 5 |
| **LR** | 2e-5 | 2e-5 |
| **Batch size** | 8 | 8 |
| **Class weighting** | None | Inverse frequency |
| **Calibration** | Temperature scaling (LBFGS, 100 iter) | Temperature scaling (LBFGS, 100 iter) |
| **Inference** | Sliding window (512 tok, stride 128) | Sliding window (512 tok, stride 128) |
| **Gating** | Always runs | Only if Model 1 → "risk" |

**Clustering**: Isolation Forest on 768-dim embeddings. 100 trees, 30% feature subsampling per tree, 5% contamination. Sigmoid-inverted anomaly score.

**Regression**: XGBoost (`reg:squarederror`, 300 trees, depth 4, lr 0.05). Takes 7 features: `lex_score`, `lex_threshold`, `lex_score_over_threshold`, `m1_score`, `m2_score`, `clust_score`, `mosaic_count`. StandardScaler normalization persisted in `metadata.json`.

---

### A5. Accuracy Testing & Validation

**Methodology** (two-pass):
1. **Pass 1 (80/20 document-level split)**: train on 80%, validate on 20%. No sentence leakage across split. Reports per-model weighted F1, macro F1, precision, recall, and full classification report.
2. **Pass 2 (100%)**: retrain on full corpus → production artifacts.

**Eval configs**: 7 TOML profiles (`configs/eval_1.toml` – `eval_7.toml`) vary pipeline layer ordering and parameters. Each config is scored on the validation split with accuracy, macro F1, micro F1, and 3×3 confusion matrix (SAFE × LOW_RISK × HIGH_RISK).

**Show**: point to `training/train_validate_pipeline.py` and the report output structure.

```sh
# to run (takes ~10-15 min on CPU):
python3 training/train_validate_pipeline.py
# outputs markdown report to stdout with tables and confusion matrices
```

---

## Part B — API Versatility

### B1. The Backend API

#### B1.1 Prettified JSON responses

All responses use `PrettyJSONResponse` (2-space indent). Show this by hitting any endpoint:

```sh
curl -s http://localhost:8000/health
```

Expected output (prettified by default):

```json
{
  "status": "ok",
  "lexicon_loaded": true,
  "model1_loaded": true,
  "model2_loaded": true,
  "embedding_loaded": true,
  "clustering_loaded": true,
  "mosaic_loaded": true,
  "regression_loaded": true
}
```

#### B1.2 Full endpoint reference

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| `GET` | `/health` | Layer load status | No |
| `GET` | `/ready` | Readiness probe (all required layers warmed) | No |
| `GET` | `/diagnostics` | Full runtime state, timings, dependency health, errors | No |
| `GET` | `/metrics` | Prometheus-format metrics (plain text) | No |
| `POST` | `/classify` | Classify single document | Optional (`X-API-Key`) |
| `POST` | `/classify/batch` | Classify 1–32 documents in one call | Optional (`X-API-Key`) |

#### B1.3 Live classify demo

Run these in sequence during the presentation:

**HIGH_RISK example** (triggers restricted entity + money threshold + event correlation):

```sh
curl -s -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Acme Corp is acquiring GlobalTech for $2.5 billion next quarter.",
    "include_offending_spans": true
  }' | python3 -m json.tool
```

**Walk through the response fields**:
- `classification`: the final verdict (`HIGH_RISK`)
- `lexicon.hits[]`: each rule that fired, with `rule`, `matched_text`, `severity`, `score`
- `lexicon.high_risk_short_circuit`: `true` if lexicon alone triggered HIGH_RISK
- `model1`: `{ label, confidence, risk_score }`
- `model2`: `{ label, confidence, high_risk_score }` (or null if gated)
- `clustering`: `{ anomaly_score, is_anomaly }`
- `regression`: `{ risk_score, reasoning }`
- `timings_ms`: per-layer latency breakdown
- `offending_spans[]`: exact character positions of each flagged span with `context_before`/`context_after`
- `observability`: `{ degraded, cache_status, executed_layers, skipped_layers }`

**SAFE example**:

```sh
curl -s -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The weather in Singapore is warm and humid today."
  }' | python3 -m json.tool
```

**LOW_RISK example** (suspicious but below threshold):

```sh
curl -s -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Sources say the company may announce a restructuring plan soon, though no details have been confirmed."
  }' | python3 -m json.tool
```

**Batch example**:

```sh
curl -s -X POST http://localhost:8000/classify/batch \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"text": "Acme Corp is acquiring GlobalTech for $2.5 billion next quarter."},
      {"text": "Public press release for next week earnings call."},
      {"text": "Internal memo: layoffs affecting 30% of staff next Monday."}
    ]
  }' | python3 -m json.tool
```

#### B1.4 Logging demo

In a **separate terminal**, tail the backend logs while making requests:

```sh
# tail logs and filter by a specific request ID
./scripts/trace_request_logs.sh <request-id-from-response>
```

Or just watch raw logs — each request emits structured JSON with:
- `event`: `"request"` or `"classify_summary"`
- `request_id`: UUID (also in `X-Request-ID` response header)
- `method`, `path`, `status_code`, `latency_ms`
- `classification`, `cache_status`, `degraded`, `executed_layers`, `skipped_layers`

**Talking point**: every request is traceable end-to-end via `X-Request-ID`.

#### B1.5 Diagnostics & metrics

```sh
# full runtime diagnostics (startup timings, layer errors, dependency status)
curl -s http://localhost:8000/diagnostics | python3 -m json.tool

# prometheus metrics (scrape-ready)
curl -s http://localhost:8000/metrics
```

#### B1.6 Request/response schema summary

**ClassifyRequest** accepts:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `text` | string (1–100,000 chars) | Yes | Control chars stripped |
| `entity_id` | string (≤128 chars) | No | Enables Mosaic layer |
| `debug` | bool | No | Includes dense embeddings in response |
| `include_offending_spans` | bool | No | Adds exact character-level span data |

**ClassifyResponse** returns:

| Field | Description |
|-------|-------------|
| `request_id` | UUID for tracing |
| `classification` | `SAFE` / `LOW_RISK` / `HIGH_RISK` |
| `lexicon` | Rule hits, scores, restricted entities, short-circuit flag |
| `model1` | Label, confidence, risk_score |
| `model2` | Label, confidence, high_risk_score (null if gated) |
| `clustering` | Anomaly score, is_anomaly flag |
| `mosaic` | Entity aggregation state (null if no entity_id) |
| `regression` | Final risk_score, reasoning string |
| `timings_ms` | Per-layer and total latency in ms |
| `observability` | Degraded flag, cache status, executed/skipped layers |
| `offending_spans` | Character-level spans with context (if requested) |

---

### B2. Python Library Integration

**Show this file**: `scripts/examples/sync_client_example.py`

Then run it live:

```sh
python3 scripts/examples/sync_client_example.py \
  "Acme Corp is acquiring GlobalTech for \$2.5 billion next quarter." \
  --include-offending-spans
```

For the async variant:

```sh
python3 scripts/examples/async_client_example.py \
  "Internal memo: layoffs affecting 30% of staff next Monday." \
  --include-offending-spans
```

#### Minimal integration sample

Show this snippet to demonstrate how simple integration is:

```python
from noupe import NoupeClient

with NoupeClient("http://localhost:8000") as client:
    result = client.classify(
        text="Acme Corp is acquiring GlobalTech for $2.5 billion next quarter.",
        include_offending_spans=True,
    )
    print(result.classification)          # HIGH_RISK
    print(result.lexicon.total_score)     # 12.0
    print(result.model1.label)            # risk
    print(result.regression.risk_score)   # 0.87
    for span in result.offending_spans:
        print(f"  [{span.rule}] {span.matched_text}")
```

Async version:

```python
from noupe import AsyncNoupeClient

async with AsyncNoupeClient("http://localhost:8000") as client:
    result = await client.classify(text="...")
    batch  = await client.classify_batch(items=[
        {"text": "First document..."},
        {"text": "Second document..."},
    ])
```

**Talking point**: the Python library is a thin typed wrapper — `NoupeClient` and `AsyncNoupeClient` return Pydantic models with full autocomplete. Error handling via `NoupeAPIError` with `.status_code`, `.detail`, `.body`.

---

### B3. Frontend Integration Demos

**Key message**: Noupe is a **backend-first solution** — any frontend can consume the REST API. We ship two reference frontends as proof of concept.

#### B3.1 Legacy Analyzer UI

```sh
# if using run_dev.sh, the frontend is served automatically
# otherwise, open the HTML directly:
open archive/frontend-demos/legacy/index.html
```

**What to show**:
- Text input area → paste sample MNPI text
- Hit "Analyze" → watch the classification result render
- Point out: layer status chips (shows which layers are loaded)
- Point out: per-layer timing breakdown
- Point out: offending span cards with highlighted matched text
- Point out: the pipeline flow diagram (Mermaid) generated per-request
- Point out: debug sidebar with the raw cURL command and full JSON response

**Endpoints it calls**: `GET /diagnostics`, `GET /ready`, `POST /classify` (with `include_offending_spans=true`)

#### B3.2 Chat Guard UI

```sh
open archive/frontend-demos/chat/index.html
```

**What to show**:
- Type a message in the chat box → hit send
- Noupe screens the message via `POST /classify` **before** it enters the chat
- **SAFE**: message passes through immediately
- **LOW_RISK**: guardrail popup appears — "Review required", user can override
- **HIGH_RISK**: guardrail popup blocks send — "Cannot send" (no override)
- Supports DOCX file upload (extracts text via `mammoth.js`, then screens)
- Backend readiness indicator (green/red dot)

**Endpoints it calls**: `GET /ready` (periodic), `POST /classify`

#### B3.3 The versatility argument

> Since Noupe exposes a standard REST API with JSON request/response, **any frontend or system can integrate**:
> - Web apps (as demonstrated by both reference UIs)
> - Mobile apps
> - Slack/Teams bots
> - Email gateways
> - Document management systems
> - CI/CD pipelines (scan PRs for leaked MNPI)
> - Any language with an HTTP client
>
> We additionally ship a **native Python client library** (`noupe` package) for direct programmatic integration, with both sync and async support.

---

## Demo Flow Cheat Sheet (suggested order)

| # | Section | Duration | What to show |
|---|---------|----------|--------------|
| 1 | A2 | 3 min | Pipeline architecture diagram — walk through the 7 layers |
| 2 | A1 | 2 min | Training data — show batch JSON, run the count script |
| 3 | A3 | 3 min | Lexicon rules — walk the rule table, show `restricted_list.json` |
| 4 | A4 | 3 min | ML models — FinBERT vs BERT, gating logic, calibration |
| 5 | A5 | 2 min | Validation methodology — 80/20 split, F1 metrics, eval configs |
| 6 | B1 | 5 min | Live API demo — curl classify (HIGH/SAFE/LOW), show prettified JSON, walk response fields |
| 7 | B1.4 | 2 min | Logging — show X-Request-ID tracing, structured JSON logs |
| 8 | B2 | 3 min | Python library — run sync example, show minimal snippet |
| 9 | B3 | 4 min | Frontends — demo both UIs, make the backend-agnostic argument |
| 10 | B3.3 | 1 min | Versatility summary — any system can integrate |

**Total: ~28 min**

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `/ready` shows `ready: false` | Wait for lazy layer warmup or check `missing_required_layers` |
| Mosaic layer not loading | Ensure `redis-server` is running on `localhost:6379` |
| Model load errors | Run `python3 scripts/preflight.py --strict` to diagnose |
| Slow first request | Expected — lazy-loaded models warm on first inference. Subsequent requests use cache. |
| Frontend can't reach API | Check CORS origins in `config.toml` or pass `?api=http://localhost:8000` to frontend URL |
