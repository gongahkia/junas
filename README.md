[![](https://img.shields.io/badge/kilter_together_1.0.0-passing-green)](https://github.com/gongahkia/kilter-together/releases/tag/1.0.0)
![](https://github.com/gongahkia/kilter-together/actions/workflows/ci.yml/badge.svg)

# `Kilter Together`

Kilter Together is a self-hostable collaborative board session app. It provisions
its own local Kilter dataset and images, serves read-only solo catalog access, and
adds invite-only rooms where one host can use the self-hosted Kilter dataset or connect Crux while
guests join from their phones to vote and queue climbs. The repo now also carries
an in-progress Flutter mobile client in `kilter-together-mobile/`.

## Quick Start

The hardened Docker flow now treats bootstrap as an explicit init step instead of
letting the API container download runtime data during `serve`.

```console
git clone https://github.com/lczm/kilter-together
cd kilter-together
cp compose.env.example .env
# set KILTER_TOGETHER_ENCRYPTION_KEY in .env
docker compose --profile bootstrap run --rm kilter-together-bootstrap
docker compose up --build -d
```

The API is available at `http://localhost:8080` (API-only, no web frontend). Verify with:

```console
curl http://localhost:8080/api/healthz
```

For mobile clients, prefer HTTPS-backed deployments even during self-hosting.

The one-time bootstrap job will:

1. Download the base Kilter SQLite database from the APKPure-hosted Android bundle.
2. Optionally run a fresher shared-data sync if Kilter credentials are configured.
3. Download the board images referenced by the database into the persistent data volume.
4. Persist a bootstrap manifest so future starts can detect partial runtime state.

The runtime containers now fail fast when `/data` is missing or incomplete. Production
notes, backup/restore steps, and key rotation instructions live in [PRODUCTION.md](./PRODUCTION.md).
If you want a step-by-step guide for self-hosting just the Go backend, local-network
phone testing, or choosing between Docker and direct `go run`, start with
[SELF_HOSTING.md](./SELF_HOSTING.md).
If you want a GitHub-connected hosted deployment on Railway with a public URL and
volume-backed runtime data, use [RAILWAY.md](./RAILWAY.md).
The persona roadmap lives in [PRODUCT_PLAN.md](./PRODUCT_PLAN.md).
The detailed mobile-first collaborative functional requirements for the
Session Captain and Phone-First Guest flow live in
[P1_P2_COLLABORATIVE_FLOW_REQUIREMENTS.md](./P1_P2_COLLABORATIVE_FLOW_REQUIREMENTS.md).

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
| `KILTER_TOGETHER_APP_SECRET` | unset | Legacy cookie-signing secret retained only for backward compatibility while the mobile rewrite is in flight |
| `KILTER_TOGETHER_ENCRYPTION_KEY` | unset | Required for encrypting stored provider credentials at rest |
| `KILTER_TOGETHER_PREVIOUS_ENCRYPTION_KEY` | unset | Optional old encryption key used during rotation |
| `KILTER_TOGETHER_PORT` | `8082` | API listen port |
| `PORT` | unset | Platform-injected listen port fallback used when `KILTER_TOGETHER_PORT` is unset |
| `KILTER_TOGETHER_ALLOWED_ORIGINS` | `http://localhost:8080,http://127.0.0.1:8080` | Comma-separated CORS allowlist |
| `KILTER_TOGETHER_STORAGE_WARN_PERCENT` | `80` | Public runtime-status warning threshold for storage usage |
| `KILTER_TOGETHER_STORAGE_CRITICAL_PERCENT` | `90` | Public runtime-status critical threshold for storage usage |

Example files live at [api/.env.example](./api/.env.example) and
[compose.env.example](./compose.env.example).

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

Mobile client:

```console
cd kilter-together-mobile
# install Flutter locally first, then:
flutter create . --platforms=android,ios
flutter pub get
flutter run
```

## Collaboration Flow

1. Open the Flutter mobile app and configure or scan the self-hosted server URL.
2. Pick `kilter` or `crux`.
3. Enter the host display name and complete provider setup while creating the room:
   - Kilter uses the self-hosted local dataset and does not require a provider login
   - Crux uses a bearer token
4. Inside the room, choose the shared board or wall context.
5. Share the mobile invite or host QR code with guests. The invite payload carries both the server URL and room slug.
6. Guests join with a display name, then vote and add climbs to the queue.

Guests can paste an app invite like `kiltertogether://join?...` or scan the same payload from the host QR code.

Room state is stored locally in `app.db`. When a provider requires credentials,
they stay server-side and are encrypted at rest with `KILTER_TOGETHER_ENCRYPTION_KEY`.

Provider capabilities are exposed at `GET /api/providers/capabilities`, and room creation/join now return a `{ room, session }` envelope whose `session.token` must be sent back as `Authorization: Bearer <token>` on authenticated room APIs.

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
- JSON error responses now include machine-readable `code` values plus `request_id` when available.
- Collaborative rooms expose room/session APIs under `/api/rooms/*` and currently ship with `kilter` and `crux` providers.
- Kilter room hosting reads from the self-hosted local dataset, so only Crux-style live providers require host credentials during room setup.
- Kilter bootstrap remains network-dependent during the explicit bootstrap step. After bootstrap, Kilter catalog reads are local. Crux catalog reads are fetched server-side and cached in `app.db`.
- `GET /api/runtime/status` exposes a user-safe runtime/storage summary that the clients can surface when hosted storage is nearing full.
- This release is intentionally single-node only. Room live updates rely on in-process SSE fan-out plus SQLite-backed local state, so horizontal scaling needs a different event and storage design.

## License

Provisioned under the [MIT License](./LICENSE).
