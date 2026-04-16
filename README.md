![CI](https://github.com/gongahkia/kilter-together/actions/workflows/ci.yml/badge.svg)

# Kilter Together

<div align="center">
  <img src="./asset/reference/1.gif" width="25%">
</div>

Backend-only service for collaborative climbing-board sessions.

A FastAPI service that aggregates real climbing boards (Kilter, Tension, Grasshopper, MoonBoard, plus the rest of the Aurora ecosystem) and brokers multiplayer sessions where climbers queue, vote on, and finalize climbs together over WebSockets.

The host owns the session and supplies any board credentials they want to enable. Guests join with a session code, no credentials required. Optional user accounts unlock a personal logbook, favorites/projects, per-climb notes, grade-system conversion, and BoardLib CSV import/export.

All routes live under `/api/v1/*`. Legacy `/api/*` aliases still work but emit `Deprecation`/`Sunset`/`Link` headers pointing to their v1 successors.

## Usage

```
make dev            # backend uvicorn with reload (port 8000)
make test           # pytest
make lint           # ruff + mypy
make docker         # build + run via docker composeq
```

Open <http://localhost:8000/docs> for the generated OpenAPI UI after `make dev`.

See `.env.example` for required env (notably `KT_CRED_KEY`, a base64 Fernet key).

## Boards

| Provider     | Status        | Notes                                                     |
|--------------|---------------|-----------------------------------------------------------|
| tension      | ok            | Aurora ecosystem                                          |
| grasshopper  | ok            | Aurora ecosystem                                          |
| decoy        | ok            | Aurora ecosystem                                          |
| soill        | ok            | Aurora ecosystem                                          |
| touchstone   | ok            | Aurora ecosystem                                          |
| aurora       | ok            | Aurora ecosystem                                          |
| moonboard    | ok            | Host's logbook (web `/Logbook/GetLogbook`)                |
| moonboard_catalog | ok       | Bundled simonchase benchmarks + lucien1011 catalogs, no auth |
| kilter       | experimental  | Kilter split from Aurora 2026-03; new infra (Keycloak)    |
| crux         | ok            | cruxapp.ca, gym-scoped (Bearer token + gym_slug in creds) |

Aurora boards share one client; one provider class is parameterized per board key.

## Architecture

```mermaid
...
```


## ToS / credentials

The backend never ships with a service account. Per session, the host attaches their own board credentials, encrypted at rest with Fernet and deleted when the session ends.

## REST + WS recipes

Generate a Fernet key and start the server:

```sh
export KT_CRED_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
make dev
```

List providers:

```sh
curl -s http://localhost:8000/api/providers | jq
```

Create a session (host enables Tension):

```sh
curl -s -XPOST http://localhost:8000/api/sessions \
  -H 'content-type: application/json' \
  -d '{"host_display_name":"Alex","enabled_providers":["tension"]}' | jq
# -> {"code":"...","host_secret":"...","host_participant_id":"..."}
```

Attach Tension credentials (host only):

```sh
curl -s -XPOST http://localhost:8000/api/sessions/$CODE/credentials \
  -H 'content-type: application/json' \
  -d '{"provider":"tension","credentials":{"username":"...","password":"..."},"host_secret":"'$HOST_SECRET'"}'
```

Search climbs (uses host's stored credentials):

```sh
curl -s "http://localhost:8000/api/sessions/$CODE/climbs?provider=tension&text=alpha&limit=20" | jq
```

Guest joins:

```sh
curl -s -XPOST http://localhost:8000/api/sessions/$CODE/join \
  -H 'content-type: application/json' -d '{"display_name":"Guest"}'
# -> {"participant_id":"...","ws_token":"..."}
```

Connect over WebSocket (use `websocat`):

```sh
websocat "ws://localhost:8000/ws/sessions/$CODE?token=$WS_TOKEN"
# send actions like:
{"type":"addToQueue","payload":{"provider":"tension","climb_id":"abc","name":"Project"}}
{"type":"voteClimb","payload":{"queue_id":"tension:abc"}}
{"type":"markCompleted","payload":{"queue_id":"tension:abc","result":"sent"}}
```

End the session (host only, deletes credentials):

```sh
curl -s -XDELETE "http://localhost:8000/api/sessions/$CODE?host_secret=$HOST_SECRET"
```

## WS protocol

Envelope: `{"type": "...", "payload": {...}, "seq": <int>}`.

Client → server actions: `joinRoom`, `leaveRoom`, `setRole`, `setProviders`, `addToQueue`, `voteClimb`, `reorderQueue`, `removeFromQueue`, `markFinalist`, `markCompleted`, `sendChat`, `sendBeta`, `voteQuality`, `voteGrade`, `setSessionMeta`.

Server → client events: `roomStateUpdate` (full snapshot, sent after every action), `participantsUpdate`, `queueUpdate`, `finalistsUpdate`, `historyUpdate`, `providersUpdate`, `chatMessage`, `betaMessage`, `qualityVote`, `gradeVote`, `sessionMetaUpdate`, `sessionEnded`, `error`.

Every event carries a monotonic `seq`. On reconnect, pass `?since_seq=<N>` to the `/ws/sessions/{code}` URL to replay events with seq > N before the snapshot arrives.

Permissions: `host` for provider/role/meta admin, `host`+`cohost` for queue reorder/finalist, `host`+`cohost`+`participant` for queue add/vote/complete/chat/beta. Participants can only remove their own queue entries.

## Accounts (optional)

Register, log in, magic-link, refresh, logout:

```
POST /api/v1/auth/register     {email, password, display_name, grade_system_pref?}
POST /api/v1/auth/login        {email, password}
POST /api/v1/auth/magic-link   {email}              # token returned inline when KT_AUTH_RETURN_MAGIC_LINKS=true
POST /api/v1/auth/magic-link/verify {token}
POST /api/v1/auth/refresh      {refresh_token}
POST /api/v1/auth/logout       {refresh_token}
GET  /api/v1/me
PATCH /api/v1/me               {display_name?, grade_system_pref?}
```

Pass `Authorization: Bearer <access_token>` on `POST /api/v1/sessions` and `/join` to link the participant to your account. A signed-in participant gets a **stable participant_id across rejoins**, and every `markCompleted` auto-writes to their personal logbook.

## Personal logbook, favorites, notes

```
GET  /api/v1/me/logbook?provider=&before=&limit=
POST /api/v1/me/logbook        {provider, climb_id, result, grade_at_send?, attempts?, rpe?, duration_seconds?, angle?, notes?}
DELETE /api/v1/me/logbook/{id}
GET  /api/v1/me/logbook/export?format=json|csv
POST /api/v1/me/logbook/import (multipart, BoardLib CSV)
GET  /api/v1/me/stats          # per-result counts, send pyramid, hardest V

POST /api/v1/me/favorites      {provider, climb_id, list?="favorites"}
DELETE /api/v1/me/favorites    {provider, climb_id, list?="favorites"}
GET  /api/v1/me/favorites?list=favorites
GET  /api/v1/me/favorites/lists

PUT  /api/v1/me/notes/{provider}/{climb_id}  {body, tags?}
GET  /api/v1/me/notes/{provider}/{climb_id}
DELETE /api/v1/me/notes/{provider}/{climb_id}
GET  /api/v1/me/notes
```

## Climb search (v1 enhancements)

`GET /api/v1/sessions/{code}/climbs` now returns typed grades (`grades: {raw, v, font, yds, uiaa}`), quality stars, setter refs, and media URLs in a typed `ClimbOut`. Cursor pagination, grade-band filtering, and sort are supported:

```
?limit=50 &cursor=<opaque>
?grade_min_v=6 &grade_max_v=9
?stars_min=3.5
?sort=stars|ascents|grade_asc|grade_desc|newest|default
```

## Grade conversion

```
GET /api/v1/grades/systems
GET /api/v1/grades/convert?value=7A&from=font&to=v    # -> {to: {system: v, value: V6}, all: {…}}
```

## Session extras

```
GET /api/v1/sessions/{code}/messages?kind=chat|beta|all&since_seq=&limit=
GET /api/v1/sessions/{code}/consensus?provider=&climb_id=   # quality_avg, grade_v_avg, distribution
GET /api/v1/sessions/{code}/export?format=json|csv
```

## Boards directory

The server bundles a sample GeoJSON of physical training-board locations (Kilter / Tension / MoonBoard / …) and exposes spatial search. Replace the table from a full `hangtime-climbing-boards` feed via `POST /api/v1/boards/reload`.

```
GET /api/v1/boards?lat=&lon=&radius_km=&board_type=&country=&limit=
GET /api/v1/boards/types
GET /api/v1/boards/{id}
POST /api/v1/boards/reload    # reload bundled sample
```

## Observability

```
GET /healthz   # liveness
GET /readyz    # DB + provider statuses + live session count
GET /metrics   # Prometheus text format: kt_http_requests_total, kt_http_request_duration_seconds
```

Rate limits auto-key on the authenticated user when a bearer token is present, falling back to X-Forwarded-For, then the direct client IP.

## Crash recovery

Session state is persisted to SQLite on every mutation. Restart the server mid-session and reconnect with a fresh `ws_token` — the room snapshot is restored from the database.

## Rate limiting

Per-IP token-bucket on the public REST endpoints. Defaults (`KT_RL_*` overridable):

| Route                          | Per minute |
|--------------------------------|------------|
| `POST /api/sessions`           | 10         |
| `POST /api/sessions/{c}/join`  | 30         |
| `GET  /api/sessions/{c}/climbs`| 60         |

Set the value to `0` to disable. Behind a reverse proxy, set `X-Forwarded-For` so the limiter sees the real client.

## Session sweeper

A background task ends sessions idle for `KT_SESSION_IDLE_MAX_HOURS` (default 24h) and drops their stored credentials and ws_tokens. Runs every `KT_SWEEP_INTERVAL_SECONDS` (default 5 min).

## Rotating `KT_CRED_KEY`

`KT_CRED_KEY` accepts either a single Fernet key or a comma-separated list (primary first) via `MultiFernet`, which enables zero-downtime rotation:

1. Generate a new key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
2. Restart with `KT_CRED_KEY=<new>,<old>` — any listed key can decrypt, but only the first (primary) encrypts new ciphertexts.
3. Opportunistically re-wrap stored credentials (via `CredentialCipher.rewrap`) the next time a session's credentials are touched.
4. Once all active ciphertexts have been re-wrapped, restart again with `KT_CRED_KEY=<new>` only.
