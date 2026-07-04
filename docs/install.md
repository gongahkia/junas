# Install Guide

Junas installs as a backend service, a local offline desktop daemon, and optional workflow adapters. Deploy the server or local daemon first, then deploy only the adapters needed for the pilot.

Uninstall and rollback runbook: `docs/deployment-rollback.md`.

Package-manager status: `docs/distribution.md` is the source of truth for
Cargo, Nix, Homebrew, signed DMG, wheel, and source-distribution availability.
As of Junas v0.1.0, only the GitHub release wheel/source distribution and
checkout-first local path are current install paths.

## Server Install

Use this path for a hosted or customer-managed FastAPI backend.

```sh
uv sync --extra dev
uv run python -m spacy download en_core_web_sm
JUNAS_DEPLOYMENT_MODE=production uv run python scripts/preflight.py --deployment production --strict
./scripts/launch/run_prod.sh
curl http://localhost:8000/ready
```

Docker:

```sh
docker compose up --build
curl http://localhost:8000/ready
```

Production Docker example:

```sh
docker compose -f docker-compose.production.example.yml up --build
curl -fsS http://localhost:8000/ready
```

The production example enables tenant auth, policy config, journal keys, no body logs, and readiness checks. Replace `deploy/docker/` sample files and secrets first.

Managed LLM deployment requires explicit tenant/deployer opt-in:

```sh
JUNAS_LLM_API_KEY=... \
JUNAS_LLM_ALLOW_REMOTE_BASE_URL=1 \
JUNAS_LLM_TENANT_OPT_IN_OPENAI=1 \
JUNAS_LLM_INPUT_MODE=structured_tokens \
SERPER_API_KEY=... \
docker compose -f docker-compose.yml -f docker-compose.managed-llm.yml up --build
```

See `docs/security/remote-llm-config.md` before enabling remote raw-text mode.

## Local Offline Desktop Install

Use this path for the packaged macOS `junas-local` daemon and optional LaunchAgent.
See `docs/deployment-local-only.md` before relying on this mode for pilots; public
evidence, remote LLM adjudication, tenant-wide auth, central SIEM, shared reviewer
queues, and DMS/server-side hooks are not part of local-only deployment.

Build:

```sh
uv sync --extra local --extra packaging
uv run python -m spacy download en_core_web_sm
./scripts/package_macos_desktop.sh
```

Optional release env:

```sh
export JUNAS_CODESIGN_IDENTITY="Developer ID Application: Example Pte Ltd (TEAMID)"
export JUNAS_NOTARYTOOL_PROFILE=junas-notary
```

`scripts/package_macos_desktop.sh` runs `codesign`, `notarytool`, and `stapler` when those release env vars are set.

Install and auto-start:

```sh
packaging/macos/install.sh
curl http://127.0.0.1:8765/ready
```

Update:

```sh
./scripts/package_macos_desktop.sh
packaging/macos/update.sh
```

Uninstall:

```sh
packaging/macos/uninstall.sh
```

## Outlook Add-In Deployment

Source: `integrations/outlook_addin/manifest.xml`.
Packaging guide: `docs/integrations/adapter-packaging.md`.

Start the backend or local daemon first, then render and validate the add-in manifest for the hosted add-in origin:

```sh
./scripts/launch/run_backend_only.sh
uv run python scripts/render_outlook_manifest.py --profile production --origin https://outlook-addin.example.com
uv run python scripts/validate_outlook_manifest.py dist/outlook-addin/production/manifest.xml --profile production
```

Deploy `dist/outlook-addin/production/manifest.xml` with Microsoft 365 admin-managed deployment. Outlook pre-send review uses Smart Alerts `OnMessageSend` with `SendMode="SoftBlock"` and requires clients that support Mailbox requirement set 1.12+; the manifest requests 1.15 for newer Smart Alerts behavior.

See `docs/integrations/outlook.md` for admin roles, CORS, well-known URI, client compatibility, and QA.

## Browser Extension Deployment

Source: `integrations/browser_extension/`.
Packaging guide: `docs/integrations/adapter-packaging.md`.

Start the backend or local daemon first, then package the MV3 extension:

Package:

```sh
./scripts/launch/run_backend_only.sh
./scripts/package_browser_extension.sh
```

Chrome on macOS/Windows must use Chrome Web Store or enterprise policy for self-hosted extension rollout. The generated ZIP is for store upload, developer loading, or managed packaging. Set `JUNAS_CHROME_EXTENSION_KEY` to produce a CRX with Chrome's packer for enterprise-controlled channels.

See `docs/integrations/genai-browser.md` and `docs/integrations/browser-extension.md` before expanding browser coverage claims.

## Word Taskpane Deployment

Source: `integrations/word_addin/manifest.xml`.
Packaging guide: `docs/integrations/adapter-packaging.md`.

Start the backend or local daemon first, replace manifest URLs with a deployer-controlled HTTPS origin, then deploy with Microsoft 365 admin-managed deployment or a controlled sideload path:

```sh
./scripts/launch/run_backend_only.sh
integrations/word_addin/manifest.xml
```

The Word taskpane is user-triggered document review, not send-time enforcement. See `docs/integrations/word.md` for the deployment boundary, required `ReadDocument` permission, and failure behavior.
