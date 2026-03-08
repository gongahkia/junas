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
- `GET /api/climbs`
- `GET /api/images/{filename}`
- `GET /swagger/index.html`

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

## Verification

Run the local checks:

```console
go test ./...
go build ./...
curl http://localhost:8082/api/healthz
```
