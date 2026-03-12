# Kilter Together API

The API now serves both:

- Solo Kilter browsing backed by the locally bootstrapped Kilter dataset
- Collaborative rooms backed by the app-state database and provider adapters

## Commands

Bootstrap the local database and images:

```console
go run . bootstrap
```

Apply app-database migrations:

```console
go run . migrate
```

On a brand-new app database, `migrate` now bootstraps from the single baseline schema in
`api/migrations/001_initial.sql`. Later SQL files are kept only so existing installs can
continue upgrading incrementally.

Serve the API:

```console
go run . serve
```

Bootstrap automatically when local data is missing:

```console
go run . serve --bootstrap-if-missing
```

`serve --bootstrap-if-missing` is intended for local development. The production Docker
path now expects bootstrap to happen as an explicit init step before `serve`.

## Endpoints

- `GET /api/healthz`
- `GET /api/boards`
- `GET /api/climbs?angle=40&board_id=14&name=swooped&setter=jwebxl&sort=popular`
- `GET /api/images/{filename}`
- `POST /api/rooms`
- `POST /api/rooms/{slug}/join`
- `GET /api/rooms/{slug}`
- `GET /api/rooms/{slug}/events`
- `POST /api/rooms/{slug}/provider/connect`
- `POST /api/rooms/{slug}/surface`
- `GET /api/rooms/{slug}/catalog/surfaces`
- `GET /api/rooms/{slug}/catalog/climbs`
- `GET /api/rooms/{slug}/catalog/climbs/{climbId}`
- `PUT /api/rooms/{slug}/fist-bumps/settings`
- `PUT /api/rooms/{slug}/votes/{climbId}`
- `POST /api/rooms/{slug}/queue`
- `PATCH /api/rooms/{slug}/queue/reorder`
- `PATCH /api/rooms/{slug}/queue/{entryId}`
- `DELETE /api/rooms/{slug}/queue/{entryId}`
- `POST /api/rooms/{slug}/clear-votes`
- `POST /api/rooms/{slug}/close`
- `DELETE /api/rooms/{slug}/participants/{participantId}`
- `GET /swagger/index.html`

`GET /api/climbs` requires `angle` and supports the optional query params
`cursor`, `page_size`, `name`, `setter`, `board_id`, and `sort=popular|newest`.

Room cookies require:

- `KILTER_TOGETHER_APP_SECRET` for signed opaque host/guest sessions
- `KILTER_TOGETHER_ENCRYPTION_KEY` for provider credential encryption

## Configuration

The API reads the following environment variables:

```env
KILTER_TOGETHER_DATA_DIR=./data
# KILTER_TOGETHER_DB_PATH=./data/kilter.db
# KILTER_TOGETHER_APP_DB_PATH=./data/app.db
# KILTER_TOGETHER_IMAGE_DIR=./data/images
# KILTER_TOGETHER_KILTER_USERNAME=
# KILTER_TOGETHER_KILTER_PASSWORD=
# KILTER_TOGETHER_APP_SECRET=
# KILTER_TOGETHER_ENCRYPTION_KEY=
# KILTER_TOGETHER_PREVIOUS_ENCRYPTION_KEY=
# KILTER_TOGETHER_PORT=8082
# KILTER_TOGETHER_SECURE_COOKIES=true
# KILTER_TOGETHER_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080
```

When credentials are provided, bootstrap will log in to `kilterboardapp.com`
and run the Aurora-style shared sync before serving.

Bootstrap also writes a local runtime manifest so the server can detect stale or
partial image state on future starts and via `/api/healthz`.

Room state, provider caches, and encrypted provider credentials are stored in the
app DB, separate from the Kilter dataset DB.

For the hardened single-node deployment contract, backup/restore commands, and key
rotation notes, see [../PRODUCTION.md](../PRODUCTION.md).

## Verification

Run the local checks:

```console
go test ./...
go build ./...
curl http://localhost:8082/api/healthz
```
