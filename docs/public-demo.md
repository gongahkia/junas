# Public Demo Playground

The public demo is a gated FastAPI playground for deterministic-only review. It
is disabled by default and exists to support a hosted demo deployment without
turning the normal authenticated API into an unauthenticated service.

Enable it only for a synthetic, no-persistence demo runtime:

```sh
JUNAS_PUBLIC_DEMO_ENABLED=1 \
JUNAS_REVIEW_PERSIST=0 \
PIPELINE_LAYERS="" \
JUNAS_PUBLIC_EVIDENCE_ENABLED=0 \
JUNAS_LLM_ENABLED=0 \
JUNAS_LLM_HELPERS_ENABLED=0 \
uv run uvicorn junas.backend.main:app --host 0.0.0.0 --port 8000
```

Routes:

- `GET /demo`: static single-page playground.
- `POST /demo/review`: unauthenticated strict-profile text review for the
  playground.

Safety properties:

- disabled unless `JUNAS_PUBLIC_DEMO_ENABLED=1`;
- forces `review_profile="strict"`;
- accepts text only and ignores document upload fields;
- uses a fresh `PreSendReviewEngine()` with no public-evidence retriever and no
  LLM helpers;
- bypasses review-session persistence even if `JUNAS_REVIEW_PERSIST=1`;
- caps request bodies and text length;
- rate-limits by client IP;
- tells users to submit synthetic, non-confidential text only.

Tunable caps:

```sh
JUNAS_PUBLIC_DEMO_BODY_MAX_BYTES=8192
JUNAS_PUBLIC_DEMO_TEXT_MAX_CHARS=4000
JUNAS_PUBLIC_DEMO_RATE_LIMIT=30
JUNAS_PUBLIC_DEMO_RATE_LIMIT_WINDOW_SECONDS=60
```

This repo state does not include a live hosted URL. The remaining hosted-demo
work is to deploy this deterministic profile to a free/public runtime, document
cold-start behavior, and link the public URL from the README hero.

