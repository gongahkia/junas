![CI](https://github.com/gongahkia/kilter-together/actions/workflows/ci.yml/badge.svg)

# Kilter Together

Backend API for climbing-board data access.

This service is intentionally focused on:

1. Provider discovery (Aurora ecosystem boards, MoonBoard, Kilter, Crux).
2. Per-session credential attachment for upstream providers.
3. Climb and layout retrieval from enabled providers.
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

### Session (credential context)

```text
POST   /api/v1/sessions
GET    /api/v1/sessions/{code}
DELETE /api/v1/sessions/{code}
POST   /api/v1/sessions/{code}/credentials
```

Session create returns `code`, `host_secret`, and `session_read_token`.
Session summary returns enabled providers and currently attached providers.

### Climb/layout access

```text
GET /api/v1/sessions/{code}/layouts
GET /api/v1/sessions/{code}/climbs
```

`/climbs` supports cursor pagination, grade filters, hold filters, and sorting.

### Boards directory

```text
GET  /api/v1/boards
GET  /api/v1/boards/types
GET  /api/v1/boards/{id}
POST /api/v1/boards/reload
```

`POST /boards/reload` requires `X-Boards-Reload-Secret` to match `KT_BOARDS_RELOAD_SECRET`.

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

## Supported providers

- `tension`
- `grasshopper`
- `decoy`
- `soill`
- `touchstone`
- `aurora`
- `moonboard`
- `moonboard_catalog`
- `kilter` (experimental)
- `crux`

## Credentials

Host-supplied provider credentials are encrypted at rest with Fernet (`KT_CRED_KEY`) and removed when a session is ended or swept as idle.
`KT_CRED_KEY` is required at startup.

## Session Security Headers

- `X-Session-Read-Token` is required for `GET /sessions/{code}`, `GET /sessions/{code}/layouts`, and `GET /sessions/{code}/climbs`.
- `X-Host-Secret` is required for `DELETE /sessions/{code}`.
