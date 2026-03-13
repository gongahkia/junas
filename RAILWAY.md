# Railway Deployment

This repo can run on Railway as a single-node API service with a persistent
volume and an optional separate web service.

The mobile app remains the primary collaborative client. Users should enter the
backend root URL such as `https://kilter-together-api.up.railway.app`, not
`/api`, because the client appends `/api/` itself.

## What Railway Must Provide

- one API service from the `api/` directory
- one persistent volume mounted for runtime data
- a public domain or Railway-generated domain for the API
- optional separate web service from `kilter-together-app/`

This app is intentionally single-node only. Keep the Railway API service at one
replica.

Railway config files do not automatically follow a service root directory inside
monorepos, so set the config source path explicitly for each service.

## API Service

1. Create a new Railway service from this GitHub repo.
2. Set the service root directory to `api`.
3. In the service settings, set the config source to `/api/railway.toml`.
4. Attach a volume and mount it at `/data`.
5. Set these variables:

```env
KILTER_TOGETHER_APP_SECRET=<openssl rand -hex 32>
KILTER_TOGETHER_ENCRYPTION_KEY=<openssl rand -base64 32>
KILTER_TOGETHER_AUTO_BOOTSTRAP_IF_MISSING=true
```

Optional:

```env
KILTER_TOGETHER_KILTER_USERNAME=<your-kilter-username>
KILTER_TOGETHER_KILTER_PASSWORD=<your-kilter-password>
KILTER_TOGETHER_ALLOWED_ORIGINS=https://<your-web-domain>
KILTER_TOGETHER_STORAGE_WARN_PERCENT=80
KILTER_TOGETHER_STORAGE_CRITICAL_PERCENT=90
```

Notes:

- The API now reads Railway's injected `PORT` automatically.
- The runtime data directory falls back to Railway's mounted volume path when
  `KILTER_TOGETHER_DATA_DIR` is not set.
- `KILTER_TOGETHER_AUTO_BOOTSTRAP_IF_MISSING=true` makes the container perform
  the first-run Kilter bootstrap before serving. That is the Railway-friendly
  path because the repo's normal hardened flow expects a separate bootstrap job.

After deploy, Railway should wait on `GET /api/readyz`.

## Optional Web Service

If you still want the legacy web UI:

1. Create a second Railway service from the same repo.
2. Set the service root directory to `kilter-together-app`.
3. Set the config source to `/kilter-together-app/railway.toml`.
4. Set:

```env
VITE_API_BASE_URL=https://<your-api-domain>/api
```

If the web and API services use different domains, keep
`KILTER_TOGETHER_ALLOWED_ORIGINS` on the API in sync with the web domain.

## Storage Warnings

The backend now exposes `GET /api/runtime/status`, which reports whether runtime
storage is healthy, nearing full, or critically low. The mobile landing/settings
surfaces and the legacy web landing/settings pages render a warning banner when
the hosted backend is above the configured storage threshold.

This warning is meant for users and hosts, while Railway's own volume metrics and
alerts should still be used for operator monitoring.
