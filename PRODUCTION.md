# Production Notes

This repo is currently hardened for a single, internet-facing node with a persistent
data volume. It is not safe to scale horizontally behind a load balancer because:

- live room fan-out is process-local SSE pub/sub
- room/app state is stored in SQLite on local disk

## Compose Workflow

1. Copy the example env file and replace the placeholder secrets:

   ```console
   cp compose.env.example .env
   openssl rand -hex 32
   openssl rand -base64 32
   ```

2. Bootstrap the shared `/data` volume once before starting the API:

   ```console
   docker compose --profile bootstrap run --rm kilter-together-bootstrap
   ```

3. Start the runtime containers:

   ```console
   docker compose up -d --build
   ```

The API container now fails fast when `/data` is missing or incomplete. It no longer
downloads the Kilter dataset implicitly during `serve`.

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
docker compose stop kilter-together-api
docker compose --profile bootstrap run --rm --entrypoint sh kilter-together-bootstrap -lc \
  'tar -C /data -czf - .' > "backups/kilter-together-$(date +%Y%m%d-%H%M%S).tgz"
docker compose start kilter-together-api
```

### Restore

```console
docker compose down
cat backups/kilter-together-YYYYMMDD-HHMMSS.tgz | \
  docker compose --profile bootstrap run --rm --entrypoint sh kilter-together-bootstrap -lc \
  'rm -rf /data/* && tar -C /data -xzf -'
docker compose up -d
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
