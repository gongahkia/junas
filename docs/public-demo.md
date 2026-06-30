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

## Hosted Demo Image

Use `Dockerfile.public-demo` for public demo hosting. It installs the base/local
SKU with `uv sync --frozen --no-dev` and sets the demo runtime gates in the
image:

- `JUNAS_PUBLIC_DEMO_ENABLED=1`;
- `JUNAS_REVIEW_PERSIST=0`;
- `PIPELINE_LAYERS=""`;
- public evidence, LLM adjudication, LLM helper, image-scan, and tenancy paths
  disabled.

It serves FastAPI on `${PORT:-8000}` so hosts that inject `PORT` can run the same
image without command edits.

## Hugging Face Spaces Notes

Web check performed 2026-06-30 against official Hugging Face docs:

- Docker Spaces are configured by setting `sdk: docker` in the Space
  `README.md` YAML block and can expose a non-default port with `app_port`.
  Source: <https://huggingface.co/docs/hub/spaces-sdks-docker>
- Spaces config is read from the YAML block at the top of the Space
  `README.md`; `cpu-basic` is a valid suggested hardware value.
  Source: <https://huggingface.co/docs/hub/spaces-config-reference>
- CPU Basic is listed as free, with 2 vCPU, 16 GB RAM, and 50 GB disk.
  Source: <https://huggingface.co/docs/hub/spaces-overview>
- Free CPU Basic Spaces sleep after 48 hours of inactivity; a visitor wakes the
  Space. Source: <https://huggingface.co/docs/hub/spaces-gpus>
- Space disk is ephemeral unless an attached storage bucket is configured.
  Source: <https://huggingface.co/docs/hub/spaces-storage>

Space metadata template:

```yaml
---
title: Junas Deterministic Demo
sdk: docker
app_port: 8000
suggested_hardware: cpu-basic
---
```

No Hugging Face secrets or variables are required for the deterministic public
demo image.

Cold-start copy for the README link:

> Hosted on free Hugging Face CPU Basic. The first visit after 48 hours of
> inactivity may take longer while the Space wakes. The demo runs strict
> deterministic review only and does not persist submitted text.

This repo state does not include a live hosted URL. The remaining hosted-demo
work is to deploy this deterministic profile to a free/public runtime, document
cold-start behavior, and link the public URL from the README hero.
