![CI](https://github.com/gongahkia/kilter-together/actions/workflows/ci.yml/badge.svg)

# Kilter Together

Backend for collaborative climbing-board sessions.

A FastAPI service that aggregates real climbing boards (Kilter, Tension, Grasshopper, MoonBoard, plus the rest of the Aurora ecosystem) and brokers multiplayer sessions where climbers queue, vote on, and finalize climbs together over WebSockets.

The host owns the session and supplies any board credentials they want to enable. Guests join with a session code, no credentials required.

## Status

Greenfield rewrite. The previous Flutter P2P client and FastAPI Cornifer service have been deleted. This repository now contains the backend only; a thin client will sit on top later.

## Architecture

```
clients
  | REST (sessions, credentials, climb search)
  | WebSocket /ws/sessions/{code}  (queue, votes, presence)
  v
FastAPI app
  - api/        REST + WS handlers
  - realtime/   session engine, hub, protocol
  - providers/  Aurora / Kilter / MoonBoard adapters
  - repos/      SQLite-backed persistence
  - security/   Fernet-encrypted host credentials
  v
SQLite (single file, mounted volume in Docker)
```

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

## Dev

```
make dev      # uvicorn with reload
make test     # pytest
make lint     # ruff + mypy
make docker   # build + run via docker compose
```

See `.env.example` for required env (notably `KT_CRED_KEY`, a base64 Fernet key).

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

Envelope: `{"type": "...", "payload": {...}}`.

Client → server actions: `joinRoom`, `leaveRoom`, `setRole`, `setProviders`, `addToQueue`, `voteClimb`, `reorderQueue`, `removeFromQueue`, `markFinalist`, `markCompleted`.

Server → client events: `roomStateUpdate` (full snapshot, sent after every action), `participantsUpdate`, `queueUpdate`, `finalistsUpdate`, `historyUpdate`, `providersUpdate`, `sessionEnded`, `error`.

Permissions: `host` for provider/role admin, `host`+`cohost` for queue reorder/finalist, `host`+`cohost`+`participant` for queue add/vote/complete. Participants can only remove their own queue entries.

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

`KT_CRED_KEY` is a Fernet key. Rotation procedure:

1. Generate a new key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
2. End all active sessions (their credentials are deleted on session end), or accept that existing ciphertexts will become unreadable.
3. Restart the server with the new `KT_CRED_KEY`.
4. Hosts must reattach their credentials.

For zero-downtime rotation we'd need MultiFernet — not implemented; out of scope until there is a public deployment to protect.

