# Kilter Together

Kilter Together is a self-hostable Kilter Board browser. It can provision its own
local database and board images, then serve the existing read-only API and web UI
without requiring a separately installed `boardlib` CLI.

## Quick Start

The primary local hosting flow is Docker:

```console
git clone https://github.com/lczm/kilter-together
cd kilter-together
docker compose up --build
```

Open the app at `http://localhost:8080` and verify the API with:

```console
curl http://localhost:8080/api/healthz
```

On the first boot, the API container will:

1. Download the base Kilter SQLite database from the APKPure-hosted Android bundle.
2. Optionally run a fresher shared-data sync if Kilter credentials are configured.
3. Download the board images referenced by the database into the persistent data volume.
4. Persist a bootstrap manifest so future starts can detect partial runtime state.

## Runtime Configuration

Backend env vars:

| Variable | Default | Purpose |
| --- | --- | --- |
| `KILTER_TOGETHER_DATA_DIR` | `./data` | Base directory for runtime data when not using explicit DB/image paths |
| `KILTER_TOGETHER_DB_PATH` | `${KILTER_TOGETHER_DATA_DIR}/kilter.db` | SQLite database location |
| `KILTER_TOGETHER_IMAGE_DIR` | `${KILTER_TOGETHER_DATA_DIR}/images` | Downloaded board image directory |
| `KILTER_TOGETHER_KILTER_USERNAME` | unset | Optional Kilter username for shared-data sync |
| `KILTER_TOGETHER_KILTER_PASSWORD` | unset | Optional Kilter password for shared-data sync |
| `KILTER_TOGETHER_PORT` | `8082` | API listen port |

Frontend env vars:

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_APP_BASE_PATH` | `/` | Browser/router base path for self-hosted builds |
| `VITE_API_BASE_URL` | `/api` | Same-origin API base URL |

Example files live at [api/.env.example](./api/.env.example) and
[kilter-together-app/.env.example](./kilter-together-app/.env.example).

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

Frontend:

```console
cd kilter-together-app
npm ci
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8082`, so local development
uses the same-origin API contract without CORS setup.

The browser UI uses URL-addressable routes:

- `/` for board selection
- `/boards/:boardId?angle=40&sort=popular&q=&setter=&climb=` for climb browsing

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

- Downloaded databases, images, and bootstrap manifests are runtime artifacts and are not committed.
- `GET /api/climbs` requires a valid `angle` and also supports `name`, `setter`, and `sort=popular|newest`.
- `GET /api/healthz` validates that the local database and image set are usable, not just that the process is running.

## License

Provisioned under the [MIT License](./LICENSE).
