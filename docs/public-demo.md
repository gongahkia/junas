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

## Public Evidence And Limitations

This page is the public evidence/limitations page for the hosted demo launch.
All examples and screenshots used for the public demo must be synthetic only:
demo prompts may include fake SG NRIC-shaped text, fake M&A codenames, and
clean internal notes, but must not include customer, employee, matter, or
credential material.

The hosted demo runs strict deterministic review only. It does not run public
evidence retrieval, LLM adjudication, LLM helpers, image scanning, tenancy, or
review-session persistence, and it does not persist submitted text.

Screen/video redaction artifacts in the README, release assets, or demo
captures are demo-only and not endpoint enforcement. They illustrate local
redaction concepts; they do not prove device management, screen capture control,
clipboard governance, file-system policy, EDR, or universal adapter coverage.

Selected host: Hugging Face Docker Space on free CPU Basic. Free CPU Basic
Spaces sleep after 48 hours of inactivity; the first visitor after that idle
period may wait longer while the Space wakes. If the selected host changes,
update this section and the README cold-start copy before linking the public
URL.

Tracked launch work:

- Deployment and README URL linking: [#84](https://github.com/gongahkia/junas/issues/84).
- Hosted verification and launch checks: [#85](https://github.com/gongahkia/junas/issues/85).

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

The image generates an ephemeral internal `JUNAS_API_KEY` at startup when one is
not supplied. That keeps normal protected endpoints such as `/review`,
`/pseudonymize`, and `/redact` closed to unauthenticated visitors while leaving
only `/demo` and `/demo/review` public.

## Free Hosting Notes

Web check performed 2026-07-02 against official provider docs. Hugging Face
Spaces remains the prepared target for this repo state because the checked-in
deploy script can publish the Docker/FastAPI image without provider secrets or
persistence.

### Hugging Face Spaces

- Docker Spaces are configured by setting `sdk: docker` in the Space
  `README.md` YAML block and can expose a non-default port with `app_port`.
  Source: <https://huggingface.co/docs/hub/spaces-sdks-docker>
- The running app uses a direct Space URL of the form
  `https://<space-subdomain>.hf.space`, served from the root of that subdomain.
  Source: <https://huggingface.co/docs/hub/spaces-embed>
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

Deploy with an authenticated Hugging Face CLI session:

```sh
hf auth login
./scripts/deploy_hf_space.sh <hf-namespace/space-name>
```

CI can pass `HF_TOKEN` instead of using an interactive login. The script creates
or reuses a Docker Space, uploads `Dockerfile.public-demo` as `Dockerfile`, adds
`deploy/huggingface-space/README.md` as the Space metadata file, and copies only
the package files needed to run the deterministic public demo. It prints the
direct app URL, for example `https://gongahkia-junas-demo.hf.space`. Set
`JUNAS_PUBLIC_DEMO_URL` only when Hugging Face reports a different direct URL or
a custom domain is configured.

GitHub Actions can also publish the Space through
`.github/workflows/deploy-public-demo.yml`. Run the manual workflow with a
`space_id` input after adding an `HF_TOKEN` repository secret. The workflow
prints the direct Space URL to the step summary and runs:

```sh
python scripts/verify_public_demo.py --base-url "$PUBLIC_DEMO_URL"
```

The verifier checks `GET /demo`, PII/MNPI/clean examples through
`POST /demo/review`, strict profile forcing, legal-basis citations,
`policy_decision.required_actions`, `send_allowed`, and disabled
public-evidence/LLM/persistence surfaces. Do not link the README hero until it
prints `public_demo_verified: true` for the hosted URL.

After hosted verification passes, link the README with the same direct app URL:

```sh
uv run python scripts/link_public_demo.py --base-url "$PUBLIC_DEMO_URL"
```

`scripts/link_public_demo.py` re-runs `scripts/verify_public_demo.py` before it
writes README markers, so a stale or unreachable hosted URL cannot be linked by
the release process.

Cold-start copy for the README link:

> Hosted on free Hugging Face CPU Basic. The first visit after 48 hours of
> inactivity may take longer while the Space wakes. The demo runs strict
> deterministic review only and does not persist submitted text.

### Render

Render Free web services are viable for FastAPI, but official docs say they
spin down after 15 minutes without inbound traffic and spin back up on the next
request, taking about one minute. Render also documents ephemeral local files
for Free web services and monthly usage limits. Source:
<https://render.com/docs/free>.

Use the same `Dockerfile.public-demo` runtime gates if deploying there:

```sh
JUNAS_PUBLIC_DEMO_ENABLED=1
JUNAS_REVIEW_PERSIST=0
PIPELINE_LAYERS=""
JUNAS_PUBLIC_EVIDENCE_ENABLED=0
JUNAS_LLM_ENABLED=0
```

`render.yaml` provides a checked-in Render Blueprint for this fallback path. It
uses the free Docker web-service runtime, `Dockerfile.public-demo`, `/ready` as
the health check, and the same deterministic-only environment gates.

README cold-start copy must mention the 15-minute idle spin-down if Render is
chosen.

### Railway

Railway Serverless can sleep a service after more than 10 minutes with no
outbound packets, wakes on traffic, and docs warn that the first request may
return `502 Bad Gateway`. Source:
<https://docs.railway.com/deployments/serverless>.

Do not use Railway as the default public-demo target unless the deployment
account, billing/free-trial posture, and first-request `502` behavior are
documented for the exact live URL.

This repo state does not include a live hosted URL. The remaining hosted-demo
work is to deploy this deterministic profile to a free/public runtime, document
cold-start behavior, and link the public URL from the README hero.
