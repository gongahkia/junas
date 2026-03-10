# Observability

Kilter Together now supports a self-hosted observability stack built around:

- `Prometheus` for metrics
- `Grafana` for dashboards
- `Alertmanager` for alerts
- `Loki` for logs
- `Grafana Alloy` for Docker log collection and OTLP ingestion
- `Tempo` for traces
- `GlitchTip` as the recommended Sentry-compatible exception backend

## What Changed In The App

### Backend
- `/api/metrics` now remains the metrics scrape target.
- room actions emit dedicated counters through `kilter_together_room_actions_total`.
- HTTP responses can include `X-Trace-Id`.
- JSON error responses now include:
  - `code`
  - `request_id`
  - `trace_id`
- `/api/operator/status` exposes a protected runtime summary for operators.

### Frontend
- failed API actions are forwarded through the client observability wrapper
- SSE reconnect storms and QR-scanner failures are reported outside the browser console
- uncaught frontend exceptions can be sent to a Sentry-compatible DSN such as GlitchTip

## Environment Variables

Backend:

- `KILTER_TOGETHER_OPERATOR_TOKEN`
- `KILTER_TOGETHER_OTEL_EXPORTER_OTLP_ENDPOINT`
- `KILTER_TOGETHER_OTEL_EXPORTER_OTLP_INSECURE`
- `KILTER_TOGETHER_OTEL_SERVICE_NAME`
- `KILTER_TOGETHER_SENTRY_DSN`
- `KILTER_TOGETHER_SENTRY_ENVIRONMENT`
- `KILTER_TOGETHER_SENTRY_RELEASE`

Frontend:

- `VITE_SENTRY_DSN`
- `VITE_SENTRY_ENVIRONMENT`
- `VITE_APP_RELEASE`

## Running The Stack

Start the app stack first:

```console
docker compose up --build -d
```

Then start the observability sidecars:

```console
docker compose -f docker-compose.yml -f docker-compose.observability.yml up -d
```

Default local ports:

- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- Alertmanager: `http://localhost:9093`
- Loki: `http://localhost:3100`
- Tempo: `http://localhost:3200`
- Alloy UI: `http://localhost:12345`

Grafana ships with provisioned datasources and one starter dashboard:

- [`observability/grafana/dashboards/kilter-together-overview.json`](/Users/gongahkia/Desktop/coding/projects/kilter-together/observability/grafana/dashboards/kilter-together-overview.json)

## Recommended Alert Routing

The committed Alertmanager config uses a default receiver so the stack starts cleanly. For real deployments, replace the receiver with email, Slack, PagerDuty, or another webhook target.

## GlitchTip

GlitchTip is not bundled into `docker-compose.observability.yml` because it is materially heavier than the rest of the stack and many deployments already run it centrally.

Use the DSN from your GlitchTip project in:

- `KILTER_TOGETHER_SENTRY_DSN` for backend exception capture
- `VITE_SENTRY_DSN` for frontend exception capture

The app uses the standard Sentry protocol, so GlitchTip works without custom adapters.
