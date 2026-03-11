# Production Notes

This repo is currently hardened for a single, internet-facing node with a persistent
data volume. It is not safe to scale horizontally behind a load balancer because:

- live room fan-out is process-local SSE pub/sub
- room/app state is stored in SQLite on local disk

## Compose Workflow

1. Copy the production env file and replace the placeholder secrets:

   ```console
   cp compose.production.env.example compose.production.env
   openssl rand -hex 32
   openssl rand -base64 32
   ```

2. Render the TLS edge proxy config from that env file:

   ```console
   ./scripts/render-caddyfile.sh compose.production.env
   ```

3. Bootstrap the shared `/data` volume once before starting the API:

   ```console
   docker compose --env-file compose.production.env -f docker-compose.production.yml \
     --profile bootstrap run --rm kilter-together-bootstrap
   ```

4. Start the runtime containers:

   ```console
   docker compose --env-file compose.production.env -f docker-compose.production.yml \
     up -d --build
   ```

The API container now fails fast when `/data` is missing or incomplete. It no longer
downloads the Kilter dataset implicitly during `serve`.

The production compose stack adds a Caddy edge proxy with automatic TLS for
`KILTER_TOGETHER_PUBLIC_HOST`. The rendered Caddyfile is generated from
[`deploy/caddy/Caddyfile.template`](/Users/gongahkia/Desktop/coding/projects/kilter-together/deploy/caddy/Caddyfile.template)
and should not be committed.

Client-side GlitchTip or Sentry values such as `VITE_SENTRY_DSN`,
`VITE_SENTRY_ENVIRONMENT`, and `VITE_APP_RELEASE` are build-time inputs. After changing
them, rebuild the `kilter-together-web` image so the static bundle picks them up.

## Data Durability

The named Docker volume stores:

- `app.db` plus any `app.db-wal` and `app.db-shm` sidecars
- `kilter.db` plus any `kilter.db-wal` and `kilter.db-shm` sidecars
- the downloaded image set
- the bootstrap manifest

Back up the entire `/data` volume, not just the `*.db` files.

### Backup

Stop the API first so the tarball captures a clean point-in-time copy of the whole
volume, including any SQLite sidecars.

```console
mkdir -p backups
docker compose --env-file compose.production.env -f docker-compose.production.yml stop kilter-together-api
docker compose --env-file compose.production.env -f docker-compose.production.yml --profile bootstrap run --rm --entrypoint sh kilter-together-bootstrap -lc \
  'tar -C /data -czf - .' > "backups/kilter-together-$(date +%Y%m%d-%H%M%S).tgz"
docker compose --env-file compose.production.env -f docker-compose.production.yml start kilter-together-api
```

### Restore

```console
docker compose --env-file compose.production.env -f docker-compose.production.yml down
cat backups/kilter-together-YYYYMMDD-HHMMSS.tgz | \
  docker compose --env-file compose.production.env -f docker-compose.production.yml --profile bootstrap run --rm --entrypoint sh kilter-together-bootstrap -lc \
  'rm -rf /data/* && tar -C /data -xzf -'
docker compose --env-file compose.production.env -f docker-compose.production.yml up -d
```

Run `curl http://localhost:8080/api/healthz` after restore and confirm you can open a
solo board plus an existing room.

## Encryption Key Rotation

Provider credentials are encrypted at rest in `app.db`. To rotate the key:

1. Generate a new base64-encoded 32-byte key.
2. Set `KILTER_TOGETHER_ENCRYPTION_KEY` to the new key.
3. Set `KILTER_TOGETHER_PREVIOUS_ENCRYPTION_KEY` to the old key.
4. Restart the API and exercise room/provider flows so existing secrets are read and
   re-encrypted with the new key.
5. Remove `KILTER_TOGETHER_PREVIOUS_ENCRYPTION_KEY` after the migration window closes.

## Migration Policy

The app still uses GORM `AutoMigrate` for the current schema, but future schema changes
should be introduced with explicit, reviewed migrations instead of relying on implicit
runtime mutation alone.
