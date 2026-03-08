# Kilter Together Frontend

## Development

```console
npm ci
npm run dev
```

By default, the app serves at `/` and calls the API at `/api`. During development,
Vite proxies `/api` to `http://localhost:8082`.

The app uses URL-addressable routes:

- `/` for board selection
- `/boards/:boardId?angle=40&sort=popular&q=&setter=&climb=` for climb browsing

## Build

```console
npm run build
```
