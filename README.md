[![](https://img.shields.io/badge/kilter_together_1.0.0-passing-green)](https://github.com/gongahkia/kilter-together/releases/tag/1.0.0)
![](https://github.com/gongahkia/kilter-together/actions/workflows/ci.yml/badge.svg)

# `Kilter Together`

Kilter Together is a self-hostable collaborative board session app. It provisions
its own local Kilter dataset and images, serves a read-only solo browser, and now
adds invite-only rooms where one host account can connect Kilter or Crux while
guests join from their phones to vote and queue climbs.

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

The Docker stack now also seeds development-only room secrets so the collaborative
room flow works out of the box on `localhost`. Replace those values before any
shared or internet-exposed deployment.

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

- `/` landing page for collaborative rooms and solo browse
- `/rooms/new` to create a room
- `/join/:slug` to join a room from an invite
- `/rooms/:slug?q=&sort=&climb=` for collaborative sessions
- `/solo` for solo Kilter browsing
- `/solo/boards/:boardId?angle=40&sort=popular&q=&setter=&climb=` for solo climb browsing
- `/boards/:boardId?...` remains available as a compatibility route

## Collaboration Flow

1. Open `/rooms/new`.
2. Pick `kilter` or `crux`.
3. Enter the host display name and create the room.
4. Inside the room, connect one provider account:
   - Kilter uses `username` + `password`
   - Crux uses a bearer token
5. Choose the shared board or wall context.
6. Share the invite link with guests.
7. Guests join with a display name, then vote and add climbs to the queue.

Room state is stored locally in `app.db`. Provider credentials stay server-side
and are encrypted at rest with `KILTER_TOGETHER_ENCRYPTION_KEY`.

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
- Collaborative rooms expose room/session APIs under `/api/rooms/*` and currently ship with `kilter` and `crux` providers.
- Kilter bootstrap remains network-dependent on first run. After bootstrap, Kilter catalog reads are local. Crux catalog reads are fetched server-side and cached in `app.db`.

## License

Provisioned under the [MIT License](./LICENSE).
