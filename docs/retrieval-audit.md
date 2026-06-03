# Retrieval Audit

Comparison of junas's hybrid retrieval implementation against a
production SG legal-AI retrieval surface, with recommendations for
v0.2 changes.

Tracking issue: [#41](https://github.com/gongahkia/junas/issues/41).
Companion: [`docs/coverage-matrix.md`](coverage-matrix.md),
[`backend/api/indices.py`](../backend/api/indices.py).

## TL;DR

| Dimension | junas v0.2 | Reference impl | Recommendation |
|---|---|---|---|
| Region-per-index naming | Adopted (`junas_sg_*`) | `search-sg_*` style | ✅ done |
| Query type detection | None | Heuristic router (keyword / semantic / boolean / proximity) | **Adopt in v0.3** |
| Search modes available | BM25 (ES) + dense (Qdrant) + RRF merge | + boolean + proximity (span_near) | **Add boolean + proximity** |
| Collapse / dedupe | None | `collapse` on `legisId` per index | **Adopt — high-leverage** |
| Re-rank | Cross-encoder (already present) | Re-score on `legis_status=Current` | **Add current-law boost** |
| Highlighting | Off | On, with `inner_hits` for chunked docs | Adopt when FE needs it |
| Pagination | Top-K only | `search_after` cursor | **Adopt — required for leaderboard FE** |
| Aggregations / facets | None | Available behind flag | Adopt when FE needs filters |

The two changes that matter for v0.2 are **dedupe by `legis_id`** and
**adopting `search_after` cursors**. The rest is correctness for the
copilot but doesn't affect the benchmark.

## 1. Reference architecture

The reference (which I had read access to during this audit; see
session transcript) follows a clean pattern:

- **Region-per-index mapping.** A `REGION_INDICES` dict maps each
  country code to its set of indices keyed by doc type (`cases`,
  `legislation`, `hansard`, `news`, `regulations`).
- **Query builders.** Distinct builders for keyword, semantic,
  boolean, proximity. Each returns a `SearchQuery` dataclass with
  `index` and `body`.
- **Query-type detection.** Heuristics inspect the user query string
  for proximity patterns (`/n` operators), boolean operators (`AND`,
  `OR`, `NOT`), question patterns, and legal-term density. The result
  is a `QueryType` enum used to dispatch to the right builder.
- **Auto-search orchestrator.** Picks a builder, runs it, returns the
  ES response.
- **Cross-cutting features.** Highlighting with `inner_hits` per
  chunk, `search_after` cursors, `collapse` on `legisId` to dedupe,
  optional `rescore` to boost current legislation, optional aggregations.

## 2. junas v0.2 current state

- **Region-per-index naming:** ✅ adopted in this PR. `api.indices`
  module exposes `ES.statutes`, `ES.glossary`, `ES.cases`,
  `QDRANT.statutes`, `QDRANT.cases`, with `junas_sg_*` naming.
- **Search modes:**
  - `retrieval_orchestrator.RetrievalOrchestrator` runs a BM25 query
    against ES *and* a vector query against Qdrant, then RRF-merges
    (constant `k=60`).
  - For glossary and case-law, only BM25 (ES) is wired.
  - No query-type detection: every call uses the same path.
- **No collapse** on `legis_id` or any other field. Duplicate-section
  documents are not de-duplicated server-side.
- **No `search_after`.** Pagination relies on `from/size`, which is
  fine for top-K research-paper-style runs but doesn't scale to a
  leaderboard UI that wants to drill into a run's per-case results.
- **No highlighting** in the response payload. Citation extraction is
  done post-hoc by `citation_verifier` regex.
- **No legislation-status rescore.** Junas's statute lookup does not
  distinguish current vs historical at retrieval time.

## 3. Concrete recommendations (priority-ordered)

### R1 — Dedupe by `legis_id` (high leverage, low effort)

Add ES `collapse` on `legis_id` for case + legislation queries. Same
pattern as `legal_id` upstream:

```python
body["collapse"] = {"field": "legis_id"}
```

`SourceDocument.legis_id` is already derived as part of #62/#64.
Wire it through `retrieval_orchestrator` so callers don't see
duplicates of the same statute across the BM25 / dense halves.

### R2 — `search_after` cursors (required for leaderboard FE)

The benchmark leaderboard FE (PR #65) currently lists every entry. For
deeper drill-down ("show me the 30 cases under run X") we need stable
pagination. Implement `search_after` keyed on
`(finished_at, run_id)` for the leaderboard, and on
`(sort_date, legis_id)` for case/statute search.

Add to `retrieval_orchestrator.RetrievalOrchestrator.retrieve()`:

```python
def retrieve(self, ..., cursor: PaginationCursor | None = None):
    ...
    if cursor:
        body["search_after"] = cursor.sort_values
```

### R3 — Boolean + proximity builders (copilot-scope, not benchmark)

Most SG legal practitioner queries use boolean operators ("PDPA AND
penalty NEAR/5 trafficking"). Junas's current BM25 implicitly ANDs
terms but doesn't expose explicit operators. Add:

- `boolean_search(query, …)` using ES `bool` + `query_string`.
- `proximity_search(query, distance=10, …)` using `span_near`.

These are copilot ergonomics; the benchmark itself doesn't need
either. Move to v0.3 if the copilot doesn't ship before then.

### R4 — Query-type detection (R3's natural companion)

If R3 lands, add a `detect_query_type(query)` heuristic that routes
to the right builder. Inputs come from the reference impl's pattern:
proximity operators, boolean operators, question patterns, legal-term
density. Returns a `QueryType` enum (`keyword | semantic | boolean |
proximity`).

### R5 — Current-law rescore (copilot UX)

For statute lookup, boost current-version sections via an ES
`rescore` block. Requires:

- `SourceDocument.extra["doc_status"]` populated by `SsoAdapter`
  (already in `extra_schema`).
- An ES field mapping that exposes `doc_status` for scoring.

Move to v0.3 once SSO ingestion (#28) lands.

### R6 — Highlighting / `inner_hits`

When the FE renders search results in the copilot UI, highlighting
becomes high-value. The cost is modest (one extra block in the ES
body). Defer until the copilot has a real search-results screen.

## 4. What I deliberately do NOT recommend adopting

- **Same query-DSL surface area as a multi-region production system.**
  Junas SG-only stays simpler. The reference impl handles MY / ID /
  UK / AU on the same code path; we get to skip a lot of that.
- **The full chunk-level `inner_hits` system.** Useful for big
  judgments but adds non-trivial indexing complexity. Defer until the
  benchmark or copilot needs it.
- **Caching layers.** Adding Redis-backed query caching would be a
  premature optimisation given our QPS targets.

## 5. Methodology hygiene

For the SG-LegalBench retrieval-flavoured tasks (SGLB-02 Statute-QA,
SGLB-03 Case-Holding, SGLB-10 Citation-Generation):

- **Disclose the retrieval setting per leaderboard row.** If a model
  used semantic + BM25 + cross-encoder + collapse, all four are
  reported. A closed-book number with no retrieval is a different
  thing than a retrieval-augmented number; conflating them is snake-
  oil.
- **Reproducibility:** the receipt JSON (see
  [`backend/benchmark/runner.py`](../backend/benchmark/runner.py))
  should grow a `retrieval_config` block when a task uses retrieval.
  Coverage matrix §4.4 already mandates this.

## 6. Action items

| Item | PR target |
|---|---|
| R1 dedupe by `legis_id` | v0.2 follow-up |
| R2 `search_after` cursors | required before leaderboard drill-down ships |
| R3 boolean + proximity builders | v0.3 |
| R4 query-type detection | v0.3 (paired with R3) |
| R5 current-law rescore | v0.3 (paired with SSO ingestion) |
| R6 highlighting | when copilot search UI ships |

Region-prefixed naming is already done (this PR).
