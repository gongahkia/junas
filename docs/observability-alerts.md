# Observability Alerts

Prometheus rules live at `deploy/prometheus/junas-alerts.yml`. Alert labels and annotations must not include raw prompts, email bodies, document text, filenames, recipient addresses, matched spans, reviewer rationale, auth headers, or local pairing tokens.

| Alert | Source | Meaning |
|---|---|---|
| `JunasBackendHighErrorRate` | `junas_http_requests_total` | Backend 5xx share is above the production threshold. |
| `JunasPolicyConfigValidationFailure` | `junas_preflight_check_status{check="policy_config"}` | Production policy config preflight is failing or missing. |
| `JunasExternalHelperFailure` | `junas_dependency_configured`, `junas_dependency_healthy` | A configured helper such as OCR, public evidence, or LLM support is down. |
| `JunasAdapterAuthFailureSpike` | `junas_http_requests_total` 401/403 on adapter-facing routes | Tenant auth, API key, JWT, or adapter backend URL setup is failing. |
| `JunasLocalDaemonPairingAnomalies` | `junas_http_requests_total` 4xx/429 on local pairing routes | Local daemon pairing attempts are failing, conflicting, or rate limited. |

Publish policy preflight metrics through a textfile collector before or during production deploys:

```sh
python3 scripts/preflight.py --deployment production --strict --prometheus-output /var/lib/node_exporter/textfile_collector/junas-preflight.prom
```

The generated metric is status-only:

```prometheus
junas_preflight_check_status{check="policy_config"} 1
```

Use `/diagnostics` for dependency detail during triage. Keep alert payloads limited to status, component, route, status code, dependency name, and bounded policy/config check names.
