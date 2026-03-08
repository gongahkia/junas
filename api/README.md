# Kilter Together API

## Commands

Bootstrap the local database and images:

```console
go run . bootstrap
```

Serve the API:

```console
go run . serve
```

Bootstrap automatically when local data is missing:

```console
go run . serve --bootstrap-if-missing
```

## Endpoints

- `GET /api/healthz`
- `GET /api/boards`
- `GET /api/climbs?angle=40&board_id=14&name=swooped&setter=jwebxl&sort=popular`
- `GET /api/images/{filename}`
- `GET /swagger/index.html`

`GET /api/climbs` requires `angle` and supports the optional query params
`cursor`, `page_size`, `name`, `setter`, `board_id`, and `sort=popular|newest`.

## Configuration

The API reads the following environment variables:

```env
KILTER_TOGETHER_DATA_DIR=./data
# KILTER_TOGETHER_DB_PATH=./data/kilter.db
# KILTER_TOGETHER_IMAGE_DIR=./data/images
# KILTER_TOGETHER_KILTER_USERNAME=
# KILTER_TOGETHER_KILTER_PASSWORD=
# KILTER_TOGETHER_PORT=8082
```

When credentials are provided, bootstrap will log in to `kilterboardapp.com`
and run the Aurora-style shared sync before serving.

Bootstrap also writes a local runtime manifest so the server can detect stale or
partial image state on future starts and via `/api/healthz`.

## Verification

Run the local checks:

```console
go test ./...
go build ./...
curl http://localhost:8082/api/healthz
```
