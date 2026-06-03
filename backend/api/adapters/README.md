# Legal Source Adapters

Two-tier adapter architecture for ingesting Singapore legal sources into
the benchmark corpus and the copilot.

```
backend/api/adapters/
├── base.py                       LegalSourceAdapter protocol + provenance
├── public/                       free, public-domain SG legal sources
│   ├── sso.py                    Singapore Statutes Online (#28)
│   ├── pdpc.py                   PDPC enforcement decisions (#27)
│   ├── pdpc_guidance.py          PDPC Advisory Guidelines (#60)
│   ├── elitigation.py            eLitigation public judgments (TOS-gated, #34)
│   ├── commonlii_sg.py           CommonLII SG fallback
│   ├── austlii_sg.py             AustLII SG section
│   ├── mom.py                    MOM Employment Practices (#59)
│   ├── iras.py                   IRAS (v0.3)
│   └── hansard.py                Singapore Parliament Hansard (v0.3)
└── user_credentialed/            paid sources; copilot-only, never benchmark
    ├── lawnet.py                 SAL LawNet (phase 3)
    ├── practical_law_sg.py       Thomson Reuters PL SG (phase 3)
    └── lexisnexis_sg.py          LexisNexis SG (phase 3)
```

## Hard rules

These rules are enforced by the test suite (`tests/test_adapters.py`) and
should be treated as architectural invariants.

1. **Benchmark uses public adapters only.** Every benchmark dataset row
   must trace to an adapter where `metadata.tier == AdapterTier.PUBLIC`
   and `metadata.benchmark_eligible is True`.
2. **`benchmark_safe_adapters()` is the gate.** Any ingestion pipeline
   that emits benchmark rows must route through this filter. Bypassing
   is a methodology violation.
3. **Credentialed adapters must use official APIs.** Never session
   cookies, never password forwarding. The server never persists user
   credentials.
4. **Provenance is mandatory.** Every `SourceDocument` carries a full
   provenance record (source_id, source_url, document_id, legis_id,
   doc_type, country, sort_date, year, dates, licence summary, tier).
5. **Unimplemented fetches raise loudly.** Stubs raise `SourceAdapterError`
   rather than returning empty iterators so silent benchmark builds
   against a non-implemented adapter cannot happen.
6. **Each adapter declares `doc_type` + `extra_schema`.** `doc_type` must
   be a value from `DocType`; `extra_schema` documents the per-source
   fields populated on `SourceDocument.extra`. Both are enforced by tests.

## Envelope alignment

`SourceDocument` carries a core envelope that mirrors the contract
adjacent SG legal ingestion pipelines normalise into:

| Field | Source | Notes |
|---|---|---|
| `legis_id` | derived by `derive_legis_id()` if not provided | falls back from raw_id → title slug → hash |
| `document_id` | adapter-supplied | stable per source |
| `source_url` | adapter-supplied | canonical public URL |
| `country` | `metadata.country` (defaults to "SG") | exposed as property |
| `doc_type` | adapter-declared (`DocType` value) | enforces canonical taxonomy |
| `sort_date` | `published_date or fetched_date` ISO string | property |
| `year` | year of `sort_date` | property |
| `extra` | per-source `dict` | shape documented in `extra_schema` |

A junas-scraped corpus is therefore drop-in compatible with downstream
SG legal AI tooling that expects this envelope, without re-mapping.

## When a `benchmark_eligible` flag is False

A `PUBLIC` tier adapter may temporarily have `benchmark_eligible=False`
when:

- TOS clearance is pending (e.g. `ElitigationAdapter` until #34 closes).
- Coverage is deferred to a later release (e.g. `IrasAdapter`,
  `HansardAdapter` deferred to v0.3 per `docs/coverage-matrix.md` §7).

Flip the flag to `True` only after the gating issue is closed and the
adapter has a real `fetch_all()` implementation.

## Adding a new adapter

1. Pick a tier. If the source charges money or requires login, it is
   `USER_CREDENTIALED` and is automatically excluded from the benchmark.
2. Add a module under `public/` or `user_credentialed/`.
3. Implement the `LegalSourceAdapter` protocol: `metadata`, `fetch_all`,
   `fetch_by_id`.
4. Write a license summary that names the source's licence regime and
   any attribution requirements. Keep it concrete; "see source" is not
   acceptable.
5. Re-export from the relevant `__init__.py`.
6. Add a smoke test asserting the tier, the `benchmark_eligible` flag,
   and that the protocol is satisfied.
