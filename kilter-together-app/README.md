# Kilter Together Frontend

## Development

```console
npm ci
npm run dev
```

By default, the app serves at `/` and calls the API at `/api`. During development,
Vite proxies `/api` to `http://localhost:8082`.

## Build

```console
npm run build
```

Legacy hosted builds can still target the current Pages path and hosted API by
overriding the frontend env vars:

```console
VITE_APP_BASE_PATH=/boardbuddy/ \
VITE_API_BASE_URL=https://lczm.me/boardbuddy/api \
npm run build
```
