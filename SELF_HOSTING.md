# Self-Hosting the Go Backend

This guide is for people who want to run their own Kilter Together backend without
reverse-engineering the development setup first.

Use it when you want to:

- run the Go API for the Flutter mobile app
- run the bundled Docker stack on a laptop, mini PC, or home server
- test from phones on the same local network
- understand which URL clients should actually enter

If you want a hosted GitHub-to-public-URL deployment on Railway instead of
self-hosting your own machine, use [RAILWAY.md](./RAILWAY.md).

The backend is single-node only right now. Do not put multiple API instances behind
a load balancer. Live room fan-out is process-local and room state is stored in
SQLite on local disk.

## Pick a Deployment Path

| Path | Best for | Client URL |
| --- | --- | --- |
| `docker compose` | easiest local or home-LAN setup, includes the legacy web app | `http://<host>:8080` |
| `go run . serve` | backend-only setup for the mobile app or local development | `http://<host>:8082` |
| `docker-compose.production.yml` | internet-facing deployment with TLS and a domain | `https://<your-domain>` |

If you only care about the mobile app, the backend-only Go path is enough.

## What the Backend Does

There are two separate phases:

1. `bootstrap`
   Downloads the base Kilter dataset, downloads the board images referenced by that
   dataset, and writes a bootstrap state manifest.
2. `serve`
   Starts the API server that mobile and web clients talk to.

Do not treat `serve` and `bootstrap` as the same thing. The hardened Docker path
expects bootstrap to happen first.

## Before You Start

You need one of these:

- Docker Desktop or Docker Engine with Compose support
- Go `1.23+` if you want to run the API directly

You also need:

- a machine reachable by your phones
- outbound internet access during bootstrap
- enough disk space for the Kilter SQLite data and downloaded images

Important network rules:

- phones cannot use `localhost` to reach your laptop or server
- use your machine's LAN IP, for example `http://192.168.1.50:8082`
- the mobile app assumes `https://` if you omit the scheme, so type the full
  `http://...` URL for local HTTP testing

## Option A: Easiest Local Setup With Docker

This runs the API and the legacy web app together. The API stays internal to Docker
and the web container exposes everything on port `8080`.

### 1. Clone the repo and create the env file

```console
git clone https://github.com/lczm/kilter-together
cd kilter-together
cp compose.env.example .env
```

### 2. Generate the required secrets

```console
openssl rand -hex 32
openssl rand -base64 32
```

Put them in `.env` as:

```env
KILTER_TOGETHER_APP_SECRET=<hex value from openssl rand -hex 32>
KILTER_TOGETHER_ENCRYPTION_KEY=<base64 value from openssl rand -base64 32>
```

Recommended `.env` choices for local-network testing:

- set `KILTER_TOGETHER_SECURE_COOKIES=false` if you are serving plain HTTP on your
  LAN instead of HTTPS
- leave `KILTER_TOGETHER_ALLOWED_ORIGINS=` blank for the default same-origin Docker
  setup
- only set `KILTER_TOGETHER_KILTER_USERNAME` and `KILTER_TOGETHER_KILTER_PASSWORD`
  if you want the optional shared-data sync

### 3. Run bootstrap once

```console
docker compose --profile bootstrap run --rm kilter-together-bootstrap
```

Repo shortcut:

```console
make docker-bootstrap
```

Bootstrap can take a while on the first run because it downloads the database and
image set.

### 4. Start the stack

```console
docker compose up --build -d
```

Repo shortcut:

```console
make docker-up
```

### 5. Verify the stack

```console
curl http://localhost:8080/api/healthz
docker compose ps
```

If health fails, inspect logs:

```console
docker compose logs kilter-together-api
docker compose logs kilter-together-web
```

### 6. Connect clients

- mobile app server URL: `http://<LAN-IP>:8080`
- browser URL: `http://<LAN-IP>:8080`

Do not enter `http://<LAN-IP>:8082` for this Docker setup unless you have separately
published the API port yourself.

## Option B: Run Only the Go API

This is the simplest path when you only want the mobile app to talk directly to the
backend.

### 1. Install Go and enter the API directory

```console
cd api
go version
```

You want Go `1.23` or newer.

### 2. Export the required environment variables

The Go binary reads real environment variables. `api/.env.example` is a reference
file, not something the server auto-loads by itself.

```console
export KILTER_TOGETHER_APP_SECRET="$(openssl rand -hex 32)"
export KILTER_TOGETHER_ENCRYPTION_KEY="$(openssl rand -base64 32)"
export KILTER_TOGETHER_PORT=8082
export KILTER_TOGETHER_SECURE_COOKIES=false
```

Optional:

```console
export KILTER_TOGETHER_KILTER_USERNAME="<your-kilter-username>"
export KILTER_TOGETHER_KILTER_PASSWORD="<your-kilter-password>"
```

If you want the legacy web app to run from a different origin than the API, also set
`KILTER_TOGETHER_ALLOWED_ORIGINS` explicitly, for example:

```console
export KILTER_TOGETHER_ALLOWED_ORIGINS="http://localhost:5173,http://127.0.0.1:5173,http://192.168.1.50:5173"
```

Native mobile clients do not need CORS, so this variable mainly matters for browser
clients.

### 3. Bootstrap the local dataset

```console
go run . bootstrap
```

### 4. Start the API

```console
go run . serve
```

From the repo root, the equivalent dev shortcut is:

```console
make dev-api
```

For local development only, you can use:

```console
go run . serve --bootstrap-if-missing
```

That convenience flag is fine on a dev laptop. It is not the hardened deployment
path.

### 5. Verify the API

```console
curl http://localhost:8082/api/healthz
```

You can also run:

```console
go test ./...
go build ./...
```

### 6. Connect the mobile app

Enter:

```text
http://<LAN-IP>:8082
```

Examples:

- `http://192.168.1.50:8082`
- `http://10.0.0.24:8082`

Do not use:

- `localhost:8082`
- `192.168.1.50:8082` without `http://`
- `https://192.168.1.50:8082` unless you actually configured TLS there

## Finding Your LAN IP

Use the IP for the network interface your phone can reach.

macOS:

```console
ipconfig getifaddr en0
```

If that returns nothing, try:

```console
ipconfig getifaddr en1
```

Linux:

```console
hostname -I
```

Windows:

```console
ipconfig
```

Look for an address on your local network such as `192.168.x.x` or `10.x.x.x`.

## Where Data Lives

Local Go runs write under `api/data` by default:

- `kilter.db`
- `app.db`
- `images/`
- `bootstrap-state.json`

Docker runs store the same runtime data in the named volume `kilter-together-data`.

Back up the whole data directory or volume, not just one SQLite file.

## Common Problems

### `KILTER_TOGETHER_ENCRYPTION_KEY is required`

Room creation and provider credential storage require
`KILTER_TOGETHER_ENCRYPTION_KEY`. Set it before running `serve`.

### `/api/healthz` fails right after startup

Usually means bootstrap never completed or the data directory is incomplete. Rerun
bootstrap and start the server again.

### The phone cannot connect

Check these first:

- the phone and host machine are on the same network
- you used the machine's LAN IP, not `localhost`
- you included `http://` for local HTTP
- you used the right port for the stack you chose: `8080` for Docker, `8082` for
  API-only Go
- the machine firewall is not blocking inbound connections

### The browser web app gets CORS errors

Set `KILTER_TOGETHER_ALLOWED_ORIGINS` to the exact web origin or origins that should
be allowed. Do not use `*`.

### Docker starts but the API container exits immediately

The runtime container now fails fast when `/data` is missing or partial. Run the
bootstrap container first:

```console
docker compose --profile bootstrap run --rm kilter-together-bootstrap
```

## When You Want HTTPS and a Real Domain

Once you want internet-facing access instead of LAN-only testing, switch to the
production stack in [PRODUCTION.md](./PRODUCTION.md). That path adds the Caddy edge
proxy, automatic TLS, backup guidance, and key rotation notes.

In that setup:

- users should connect to `https://<your-domain>`
- `KILTER_TOGETHER_SECURE_COOKIES` should stay `true`
- `KILTER_TOGETHER_ALLOWED_ORIGINS` should be set deliberately
