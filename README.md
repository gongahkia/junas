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
| moonboard    | ok            | HTML scraper, 24h cache                                   |
| kilter       | experimental  | Kilter split from Aurora 2026-03; new infra (Keycloak)    |

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
