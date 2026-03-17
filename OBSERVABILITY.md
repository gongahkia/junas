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

## Environment Variables

- `KILTER_TOGETHER_OPERATOR_TOKEN`
- `KILTER_TOGETHER_OTEL_EXPORTER_OTLP_ENDPOINT`
- `KILTER_TOGETHER_OTEL_EXPORTER_OTLP_INSECURE`
- `KILTER_TOGETHER_OTEL_SERVICE_NAME`
- `KILTER_TOGETHER_SENTRY_DSN`
- `KILTER_TOGETHER_SENTRY_ENVIRONMENT`
- `KILTER_TOGETHER_SENTRY_RELEASE`

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

That dashboard now includes:

- runtime readiness
- HTTP request rate and p95 latency
- room funnel activity
- provider-auth failures
- create/join outcomes
- SSE subscriber count and churn
- room `429` rate
- maintenance outcomes

## Recommended Alert Routing

The committed Alertmanager config uses a default receiver so the stack starts cleanly. For real deployments, replace the receiver with email, Slack, PagerDuty, or another webhook target.

The repo now includes:

- a reusable notification template at [`observability/alertmanager/templates/default.tmpl`](/Users/gongahkia/Desktop/coding/projects/kilter-together/observability/alertmanager/templates/default.tmpl)
- a production routing example at [`observability/alertmanager/alertmanager.production.example.yml`](/Users/gongahkia/Desktop/coding/projects/kilter-together/observability/alertmanager/alertmanager.production.example.yml)
- a renderable production template at [`observability/alertmanager/alertmanager.production.tmpl.yml`](/Users/gongahkia/Desktop/coding/projects/kilter-together/observability/alertmanager/alertmanager.production.tmpl.yml)
- an env template at [`observability/alertmanager/alertmanager.env.example`](/Users/gongahkia/Desktop/coding/projects/kilter-together/observability/alertmanager/alertmanager.env.example)
- a render script at [`scripts/render-alertmanager-config.sh`](/Users/gongahkia/Desktop/coding/projects/kilter-together/scripts/render-alertmanager-config.sh)

That production example fans alerts out by severity and intent:

- `critical` alerts page PagerDuty and also continue to Slack
- `warning` and `critical` alerts land in the ops Slack channel
- create/join conversion regressions can fan out to a product or incident webhook

To activate it in a deployment:

1. Copy `observability/alertmanager/alertmanager.production.example.yml` to a deployment-local config.
2. Replace the placeholder Slack, PagerDuty, and webhook values.
3. Point the `alertmanager` container at that config instead of the default `alertmanager.yml`.
4. Recreate the `alertmanager` service.

The default compose file already mounts the shared template directory, so both the starter config and the production example can render the same alert body.

If you want a repeatable env-driven workflow instead of editing YAML by hand:

1. Copy `observability/alertmanager/alertmanager.env.example` to `observability/alertmanager/alertmanager.env`.
2. Replace the placeholder Slack, PagerDuty, and webhook values.
3. Run:

```console
./scripts/render-alertmanager-config.sh
```

4. Start the observability stack with the production override:

```console
docker compose -f docker-compose.observability.yml -f docker-compose.observability.production.yml up -d
```

That override switches Alertmanager to the rendered config under `observability/alertmanager/generated/alertmanager.production.yml`.

The default Prometheus rule set now covers:

- API scrape failures
- elevated `5xx` rate
- room `429` spikes
- runtime readiness failures
- provider-auth failure bursts
- SSE subscriber churn
- room create conversion drops
- room join conversion drops
- background maintenance failures

## Operator Workflow

When an alert fires, start with Grafana and then use the protected operator endpoint to confirm runtime state:

```console
curl -H "Authorization: Bearer $KILTER_TOGETHER_OPERATOR_TOKEN" \
  http://localhost:8080/api/operator/status
```

Use the response to confirm:

- runtime data and both SQLite databases are configured
- provider cache size and expiration look sane
- active SSE subscriber count matches expected traffic
- trace export and error reporting are actually enabled
- recent maintenance jobs are succeeding

Then pivot by signal:

- `KilterTogetherRuntimeUnavailable`: inspect the operator status response plus `PRODUCTION.md` for restore/bootstrap recovery.
- `KilterTogetherProviderAuthFailures`: inspect recent `connect_provider` traces/logs and verify provider credentials plus encryption-key state.
- `KilterTogetherSSEChurn` or room `429` alerts: inspect frontend error reporting, SSE traces, and reverse-proxy behavior for reconnect loops.
- create/join conversion alerts: compare `room_actions_total` outcomes and recent frontend error reports to isolate whether the drop is on room creation, auth, join, or session recovery.

## Hosted Operator Workflow

For hosted or multi-operator environments, treat Alertmanager as the notification fanout layer and keep Grafana plus the operator endpoint as the investigation sources of truth.

Recommended drilldown order:

1. Alert fires in Slack, PagerDuty, or the product webhook.
2. Open Grafana and confirm the alert window against HTTP, room funnel, provider auth, and SSE churn panels.
3. Query `/api/operator/status` to confirm readiness, maintenance state, trace export, and cache health.
4. Use `request_id` and `trace_id` from logs, traces, and GlitchTip to isolate the failing flow.
5. Only then rotate secrets, restart workers, or restore runtime data.

For teams that want a hosted operator surface outside Grafana, the committed production example is meant to fan alerts into an external webhook so an incident bot, ticketing system, or NOC dashboard can mirror the same signal set without changing the Kilter Together app itself.

For backup, restore, and encryption-key rotation procedures, use [PRODUCTION.md](/Users/gongahkia/Desktop/coding/projects/kilter-together/PRODUCTION.md).

## GlitchTip

GlitchTip is not bundled into `docker-compose.observability.yml` because it is materially heavier than the rest of the stack and many deployments already run it centrally.

Use the DSN from your GlitchTip project in:

- `KILTER_TOGETHER_SENTRY_DSN` for backend exception capture

The app uses the standard Sentry protocol, so GlitchTip works without custom adapters.
