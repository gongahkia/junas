[![](https://img.shields.io/badge/kilter_together_1.0.0-passing-green)](https://github.com/gongahkia/kilter-together/releases/tag/1.0.0)
![](https://github.com/gongahkia/kilter-together/actions/workflows/ci.yml/badge.svg)

# `Kilter Together`

Kilter Together is a self-hostable collaborative board session app. It provisions
its own local Kilter dataset and images, serves a read-only solo browser, and now
adds invite-only rooms where one host account can connect Kilter or Crux while
guests join from their phones to vote and queue climbs.

## Quick Start

The hardened Docker flow now treats bootstrap as an explicit init step instead of
letting the API container download runtime data during `serve`.

```console
git clone https://github.com/lczm/kilter-together
cd kilter-together
cp compose.env.example .env
# set KILTER_TOGETHER_APP_SECRET and KILTER_TOGETHER_ENCRYPTION_KEY in .env
docker compose --profile bootstrap run --rm kilter-together-bootstrap
docker compose up --build -d
```

Open the app at `http://localhost:8080` and verify the API with:

```console
curl http://localhost:8080/api/healthz
```

For local HTTP smoke testing on `localhost`, set `KILTER_TOGETHER_SECURE_COOKIES=false`
in `.env`. Keep it `true` for real deployments.

The one-time bootstrap job will:

1. Download the base Kilter SQLite database from the APKPure-hosted Android bundle.
2. Optionally run a fresher shared-data sync if Kilter credentials are configured.
3. Download the board images referenced by the database into the persistent data volume.
4. Persist a bootstrap manifest so future starts can detect partial runtime state.

The runtime containers now fail fast when `/data` is missing or incomplete. Production
notes, backup/restore steps, and key rotation instructions live in [PRODUCTION.md](./PRODUCTION.md).
The persona roadmap lives in [PRODUCT_PLAN.md](./PRODUCT_PLAN.md), and the self-hosted
observability stack is documented in [OBSERVABILITY.md](./OBSERVABILITY.md).

## Runtime Configuration

Backend env vars:

| Variable | Default | Purpose |
| --- | --- | --- |
| `KILTER_TOGETHER_DATA_DIR` | `./data` | Base directory for runtime data when not using explicit DB/image paths |
| `KILTER_TOGETHER_DB_PATH` | `${KILTER_TOGETHER_DATA_DIR}/kilter.db` | SQLite database location |
| `KILTER_TOGETHER_APP_DB_PATH` | `${KILTER_TOGETHER_DATA_DIR}/app.db` | SQLite database for rooms, sessions, votes, queues, and provider cache |
| `KILTER_TOGETHER_IMAGE_DIR` | `${KILTER_TOGETHER_DATA_DIR}/images` | Downloaded board image directory |
| `KILTER_TOGETHER_KILTER_USERNAME` | unset | Optional Kilter username for shared-data sync |
| `KILTER_TOGETHER_KILTER_PASSWORD` | unset | Optional Kilter password for shared-data sync |
| `KILTER_TOGETHER_APP_SECRET` | unset | Required for signed host/guest room cookies |
| `KILTER_TOGETHER_ENCRYPTION_KEY` | unset | Required for encrypting stored provider credentials at rest |
| `KILTER_TOGETHER_PREVIOUS_ENCRYPTION_KEY` | unset | Optional old encryption key used during rotation |
| `KILTER_TOGETHER_PORT` | `8082` | API listen port |
| `KILTER_TOGETHER_SECURE_COOKIES` | `true` | Set to `false` only for local HTTP smoke testing |
| `KILTER_TOGETHER_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080` | Comma-separated CORS allowlist for cookie-backed room APIs |
| `KILTER_TOGETHER_OPERATOR_TOKEN` | unset | Optional bearer token required for `/api/operator/status` |
| `KILTER_TOGETHER_OTEL_EXPORTER_OTLP_ENDPOINT` | unset | Optional OTLP gRPC endpoint for trace export |
| `KILTER_TOGETHER_OTEL_EXPORTER_OTLP_INSECURE` | `false` | Set to `true` for local OTLP collectors without TLS |
| `KILTER_TOGETHER_OTEL_SERVICE_NAME` | `kilter-together-api` | Service name attached to exported traces |
| `KILTER_TOGETHER_SENTRY_DSN` | unset | Optional Sentry-compatible DSN for backend exception capture |
| `KILTER_TOGETHER_SENTRY_ENVIRONMENT` | unset | Environment label sent with backend exception events |
| `KILTER_TOGETHER_SENTRY_RELEASE` | unset | Release label sent with backend exception events |

Frontend env vars:

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_APP_BASE_PATH` | `/` | Browser/router base path for self-hosted builds |
| `VITE_API_BASE_URL` | `/api` | Same-origin API base URL |
| `VITE_SENTRY_DSN` | unset | Optional Sentry-compatible DSN for frontend exception capture |
| `VITE_SENTRY_ENVIRONMENT` | unset | Environment label sent with frontend exception events |
| `VITE_APP_RELEASE` | unset | Release label sent with frontend exception events |

Example files live at [api/.env.example](./api/.env.example) and
[kilter-together-app/.env.example](./kilter-together-app/.env.example). For Docker
deployments, start with [compose.env.example](./compose.env.example).

## Local Development

Backend:

```console
cd api
go run . bootstrap
go run . serve
```

Or let the server bootstrap on demand:

```console
cd api
go run . serve --bootstrap-if-missing
```

`serve --bootstrap-if-missing` remains a local-development convenience. The production
Docker path now expects the dataset and images to be bootstrapped before `serve`.

Frontend:

```console
cd kilter-together-app
npm ci
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8082`, so local development
uses the same-origin API contract without CORS setup.

The browser UI uses URL-addressable routes:

- `/` landing page for collaborative rooms and solo browse
- `/join` for scan-first or paste-first room entry
- `/rooms/new` to create a room
- `/join/:slug` to join a room from an invite
- `/rooms/:slug?q=&sort=&climb=` for collaborative sessions
- `/solo` for solo Kilter browsing
- `/solo/boards/:boardId?angle=40&sort=popular&q=&setter=&climb=` for solo climb browsing
- `/boards/:boardId?...` remains available as a compatibility route

## Collaboration Flow

1. Open `/rooms/new`.
2. Pick `kilter` or `crux`.
3. Enter the host display name and authenticate the provider account while creating the room:
   - Kilter uses `username` + `password`
   - Crux uses a bearer token
4. Inside the room, choose the shared board or wall context.
5. Share the invite link or host QR code with guests.
6. Guests join with a display name, then vote and add climbs to the queue.

Guests can either paste the invite URL/slug or open the camera workflow at `/join`
to scan the host QR code directly from their phone.

Room state is stored locally in `app.db`. Provider credentials stay server-side
and are encrypted at rest with `KILTER_TOGETHER_ENCRYPTION_KEY`.

Provider capabilities are now exposed at `GET /api/providers/capabilities`, and operators can
inspect a protected runtime summary at `GET /api/operator/status` when
`KILTER_TOGETHER_OPERATOR_TOKEN` is configured.

## Refreshing Data

To refresh a local dataset:

```console
cd api
KILTER_TOGETHER_KILTER_USERNAME=your_username \
KILTER_TOGETHER_KILTER_PASSWORD=your_password \
go run . bootstrap
```

Credentials are optional. Without them, bootstrap still downloads the base database
and board images and remains fully usable.

## Notes

- Downloaded databases, images, SQLite sidecars, and bootstrap manifests live under `api/data` during local runs and are ignored by git.
- `GET /api/climbs` requires a valid `angle` and also supports `name`, `setter`, and `sort=popular|newest`.
- `GET /api/healthz` validates that the local database and image set are usable, not just that the process is running.
- JSON error responses now include machine-readable `code` values plus `request_id` and `trace_id` when available.
- Collaborative rooms expose room/session APIs under `/api/rooms/*` and currently ship with `kilter` and `crux` providers.
- Kilter bootstrap remains network-dependent during the explicit bootstrap step. After bootstrap, Kilter catalog reads are local. Crux catalog reads are fetched server-side and cached in `app.db`.
- This release is intentionally single-node only. Room live updates rely on in-process SSE fan-out plus SQLite-backed local state, so horizontal scaling needs a different event and storage design.

## Observability Stack

To run the local metrics/logs/traces stack alongside the main app:

```console
docker compose -f docker-compose.yml -f docker-compose.observability.yml up -d
```

That provisions Prometheus, Grafana, Alertmanager, Loki, Tempo, and Grafana Alloy. Use a
GlitchTip DSN in the Sentry-compatible env vars when you also want frontend/backend exception
aggregation. The starter Grafana dashboard and operator workflow live in [OBSERVABILITY.md](./OBSERVABILITY.md), and the protected runtime status endpoint is available at `/api/operator/status` when `KILTER_TOGETHER_OPERATOR_TOKEN` is configured.

## License

Provisioned under the [MIT License](./LICENSE).
