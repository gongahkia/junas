# Docker Production Example

This directory contains sample files for `docker-compose.production.example.yml`. Replace every example secret and domain before use.

Run:

```sh
export JUNAS_TENANT_CREDENTIALS_JSON='{"replace-api-key":{"tenant_id":"tenant-a","subject":"pilot-service","roles":["reviewer","maker","checker","auditor","admin"]}}'
export JUNAS_MAPPING_STORE_KEY='replace-with-fernet-key'
export JUNAS_SUBJECT_INDEX_KEY='replace-with-random-hmac-key'
docker compose -f docker-compose.production.example.yml up --build
curl -fsS http://127.0.0.1:8000/ready
```

Generate a Fernet key with:

```sh
python3 - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode("ascii"))
PY
```

The compose file:

- enables tenant auth with `JUNAS_TENANCY_ENABLED=1`
- mounts a versioned production policy at `/etc/junas/policy.toml`
- requires `JUNAS_JOURNAL_KEYS_FILE`, `JUNAS_MAPPING_STORE_KEY`, and `JUNAS_SUBJECT_INDEX_KEY`
- enables review persistence under `/var/lib/junas/journal`
- runs `scripts/preflight.py --deployment production --strict` before `uvicorn`
- disables Uvicorn access logs with `--no-access-log`; keep reverse-proxy body logs disabled too
- uses a readiness healthcheck that requires `/ready` JSON to contain `"ready": true`

Do not use the example tenant credential, policy domains, journal key, or retention policy as production values.
