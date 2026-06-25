# Install Guide

## Local macOS desktop SKU

Build:

```sh
uv sync --extra local --extra packaging
uv run python -m spacy download en_core_web_sm
./scripts/package_macos_desktop.sh
```

Optional release env:

```sh
export KAYPOH_CODESIGN_IDENTITY="Developer ID Application: Example Pte Ltd (TEAMID)"
export KAYPOH_NOTARYTOOL_PROFILE=kaypoh-notary
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

## Browser extension

Package:

```sh
./scripts/package_browser_extension.sh
```

Chrome on macOS/Windows must use Chrome Web Store or enterprise policy for self-hosted extension rollout. The generated ZIP is for store upload, developer loading, or managed packaging. Set `KAYPOH_CHROME_EXTENSION_KEY` to produce a CRX with Chrome's packer for enterprise-controlled channels.

## Office add-ins

Manifests:

- Outlook: `integrations/outlook_addin/manifest.xml`
- Word: `integrations/word_addin/manifest.xml`

Deploy with Microsoft 365 admin-managed deployment for production users. Outlook pre-send review uses Smart Alerts `OnMessageSend` with `SendMode="SoftBlock"` and requires clients that support Mailbox requirement set 1.12+; the manifest requests 1.15 for newer Smart Alerts behavior.

## Server SKU

```sh
uv sync --extra dev
uv run python -m spacy download en_core_web_sm
KAYPOH_DEPLOYMENT_MODE=production uv run python scripts/preflight.py --deployment production --strict
./scripts/launch/run_prod.sh
```

Docker:

```sh
docker compose up --build
curl http://localhost:8000/ready
```

Managed LLM deployment requires explicit tenant/deployer opt-in:

```sh
KAYPOH_LLM_API_KEY=... \
KAYPOH_LLM_TENANT_OPT_IN_OPENAI=1 \
SERPER_API_KEY=... \
docker compose -f docker-compose.yml -f docker-compose.managed-llm.yml up --build
```
