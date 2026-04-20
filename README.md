![CI](https://github.com/gongahkia/kilter-together/actions/workflows/ci.yml/badge.svg)

# Kilter Together

Backend API for climbing-board data access.

This service is intentionally focused on:

1. Provider discovery (Aurora ecosystem boards, MoonBoard, Kilter, Crux).
2. Per-session credential attachment for upstream providers.
3. Climb and layout retrieval/aggregation from enabled providers.
4. Physical board-location lookup (GeoJSON-backed).
5. Grade-system conversion helpers.

All routes are served under `/api/v1/*`. Legacy `/api/*` aliases still work and emit deprecation headers.

## Usage

```sh
make dev
make test
make lint
make security
make docker
```

Open <http://localhost:8000/docs> after `make dev`.

## Core API

### Providers

```text
GET /api/v1/providers
```

Each provider descriptor includes status, credentials requirement, capability
flags (`list_layouts`, `search_climbs`, `get_climb`, `live_data`), source,
and optional status reason.
Descriptors also include normalized taxonomy fields:
`taxonomy_version`, `readiness`, and `is_data_ready`.

### Session (credential context)

```text
POST   /api/v1/sessions
GET    /api/v1/sessions/{code}
DELETE /api/v1/sessions/{code}
POST   /api/v1/sessions/{code}/credentials
```

Session create returns `code`, `host_secret`, and `session_read_token`.
Session summary returns enabled providers and currently attached providers.
Providers that are not data-ready are rejected at session creation with
`provider_not_ready`.

### Climb/layout access

```text
GET /api/v1/sessions/{code}/layouts
GET /api/v1/sessions/{code}/climbs
```

`/climbs` supports cursor pagination, grade filters, hold filters, and sorting.
If a session has multiple enabled providers and no `provider` query is passed,
the API aggregates across all enabled providers and returns partial-failure
warnings per provider instead of hard-failing the whole response.

Both `/climbs` and `/layouts` responses include:

- `meta`: provider context (`provider` or `multi`), cache freshness details, and `served_by`.
- `warnings`: provider-scoped errors (including stale-cache fallback usage).

Each climb/layout carries provenance metadata in `extras._provenance`
(`source_provider`, `fetched_at`, `normalized_fields`).

### Boards directory

```text
GET  /api/v1/boards
GET  /api/v1/boards/types
GET  /api/v1/boards/{id}
POST /api/v1/boards/reload
```

`POST /boards/reload` requires `X-Boards-Reload-Secret` to match `KT_BOARDS_RELOAD_SECRET`.
Board responses include normalized metadata fields (`board_family`, `setup_year`,
`layout_type`, `holdset_version`, `is_adjustable`) alongside original source
properties.
Reload supports `source=configured|sample|remote|auto`. Configure remote sync
with `KT_BOARDS_SOURCE_MODE`, `KT_BOARDS_SOURCE_URL`, and enable scheduled
refresh with `KT_BOARDS_SYNC_ENABLED=true` plus `KT_BOARDS_SYNC_INTERVAL_SECONDS`.

### Grade conversion

```text
GET /api/v1/grades/systems
GET /api/v1/grades/convert?value=7A&from=font&to=v
```

### Observability

```text
GET /healthz
GET /readyz
GET /metrics
```

`/readyz` includes provider capabilities/source/status reason plus
`rate_limiter_backend`.
Rate limiting supports `KT_RL_BACKEND=in_memory|redis` with Redis settings:
`KT_RL_REDIS_URL`, `KT_RL_REDIS_PREFIX`, `KT_RL_REDIS_TTL_SECONDS`.

## Supported providers

- `tension`
- `grasshopper`
- `decoy`
- `soill`
- `touchstone`
- `aurora`
- `moonboard`
- `moonboard_catalog`
- `kilter` (experimental Kilter v2; PowerSync integration pending)
- `kilter_legacy` (experimental; local legacy SQLite catalog via `KT_KILTER_LEGACY_DB_PATH`)
- `crux`

MoonBoard notes:
- `moonboard` uses authenticated web logbook access (personal entries), not a
  bulk public problems scrape.
- `moonboard_catalog` uses bundled static datasets and now exposes setup-specific
  benchmark layouts including 2019/2024 and mini variants.

## Credentials

Host-supplied provider credentials are encrypted at rest with Fernet (`KT_CRED_KEY`) and removed when a session is ended or swept as idle.
`KT_CRED_KEY` is required at startup.

## Session Security Headers

- `X-Session-Read-Token` is required for `GET /sessions/{code}`, `GET /sessions/{code}/layouts`, and `GET /sessions/{code}/climbs`.
- `X-Host-Secret` is required for `DELETE /sessions/{code}`.
