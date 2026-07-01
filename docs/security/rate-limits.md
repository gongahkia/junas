# Rate Limits

Junas has an optional in-process sliding-window limiter for abuse-prone routes. Enable it with:

```sh
export JUNAS_RATE_LIMIT_ENABLED=1
export JUNAS_RATE_LIMIT_WINDOW_SECONDS=60
export JUNAS_RATE_LIMIT_REVIEW=120
export JUNAS_RATE_LIMIT_BATCH_CLASSIFY=30
export JUNAS_RATE_LIMIT_REIDENTIFY=60
export JUNAS_RATE_LIMIT_LOCAL_PAIRING=20
export JUNAS_RATE_LIMIT_DECISION=60
```

Equivalent `config.toml`:

```toml
[rate_limit]
enabled = true
window_seconds = 60
review_per_window = 120
batch_classify_per_window = 30
reidentify_per_window = 60
local_pairing_per_window = 20
decision_per_window = 60
```

## Route Groups

| Group | Routes | Default when enabled |
|---|---|---|
| `review` | `POST /review` | 120/window |
| `batch_classify` | `POST /classify/batch` | 30/window |
| `reidentify` | `POST /reidentify` | 60/window |
| `local_pairing` | `POST /local/pairing/start`, `/approve`, `/claim` | 20/window |
| `decision` | `POST /request-approval`, `POST /review/{review_id}/decision` | 60/window |

A limit value of `0` disables that group.

## Keying

Buckets are keyed by authenticated tenant+subject when tenancy is enabled, then API key, bearer token, local daemon token, or forwarded/client IP. Stored bucket keys are SHA-256 digests, not raw tokens.

The limiter returns `429` with `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset`.

## Deployment Boundary

This limiter is process-local. Multi-process, multi-pod, or multi-region deployments must also enforce equivalent limits at the reverse proxy, API gateway, WAF, or service mesh. Trust `X-Forwarded-For` only from that proxy layer.
