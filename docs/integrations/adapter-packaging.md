# Adapter Packaging

Adapter packaging is separate from backend deployment. Backend launch scripts start
FastAPI only; they do not publish browser extension ZIPs, CRXs, Office manifests, or
Office taskpane/runtime assets.

Use this page for browser and Office adapter artifacts. Use
`docs/deployment-hardening.md`, `docs/deployment-customer-managed.md`, and
`docs/deployment-local-only.md` for the backend or local daemon that those artifacts
call.

## Browser Extension

Source path: `integrations/browser_extension/`

Package the MV3 extension:

```sh
./scripts/package_browser_extension.sh
```

Outputs:

| Artifact | Path | Use |
|---|---|---|
| ZIP | `dist/browser-extension/junas-local-review.zip` | Chrome Web Store, Edge Add-ons, dev loading, or enterprise packaging intake. |
| CRX | `dist/browser-extension/junas-local-review.crx` | Only when `JUNAS_CHROME_EXTENSION_KEY` is set for a self-hosted or enterprise-controlled channel. |

Packaging environment:

| Variable | Purpose |
|---|---|
| `JUNAS_EXTENSION_SRC` | Override the extension source directory; default is `integrations/browser_extension`. |
| `JUNAS_EXTENSION_OUT_DIR` | Override output directory; default is `dist/browser-extension`. |
| `JUNAS_CHROME_EXTENSION_KEY` | Private key passed to Chrome's packer for CRX output. |
| `JUNAS_CHROME_BIN` | Chrome binary path for CRX packing; defaults to `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`. |

Default manifest posture:

- `host_permissions` contains `http://127.0.0.1:8765/*` for local daemon mode.
- Hosted-server deployments need a tenant-specific manifest with only the exact HTTPS
  backend origin, for example `https://junas.example.com/*`.
- Do not use `<all_urls>` to make hosted mode work.
- Distribution happens through Chrome Web Store, Edge Add-ons, or enterprise extension
  policy; copying the ZIP beside the backend is not browser deployment.

Release checks:

```sh
uv run ruff check test/test_browser_extension.py test/test_adapter_smoke.py
PYTHONPATH=src python3 -m pytest test/test_browser_extension.py test/test_adapter_smoke.py -q
```

## Outlook Smart Alerts Add-In

Source path: `integrations/outlook_addin/`

Render the manifest for each profile:

```sh
uv run python scripts/render_outlook_manifest.py --profile dev
uv run python scripts/render_outlook_manifest.py --profile staging --origin https://outlook-addin.staging.example.com
uv run python scripts/render_outlook_manifest.py --profile production --origin https://outlook-addin.example.com
```

Validate the production manifest:

```sh
uv run python scripts/validate_outlook_manifest.py dist/outlook-addin/production/manifest.xml --profile production
```

Outputs:

| Artifact | Path | Use |
|---|---|---|
| Rendered manifest | `dist/outlook-addin/{profile}/manifest.xml` | Upload to Microsoft 365 admin-managed deployment or provide as an add-in manifest URL. |
| Static runtime files | `integrations/outlook_addin/taskpane.html`, `commands.html`, `launchevent.js`, `taskpane.js` | Host on the same HTTPS origin used by the rendered manifest. |

Packaging boundaries:

- `scripts/render_outlook_manifest.py` replaces `{{JUNAS_OUTLOOK_ADDIN_ORIGIN}}`.
- `scripts/validate_outlook_manifest.py` checks Mailbox requirement set, runtime URLs,
  `OnMessageSend`, and `SendMode="SoftBlock"`.
- Production and staging origins must be non-local HTTPS origins.
- The backend launcher does not host `taskpane.html`, `commands.html`,
  `launchevent.js`, or the `.well-known` Office allowlist file.
- Microsoft 365 admin-managed deployment owns user/group assignment; backend deploys do
  not install the add-in.

Release checks:

```sh
uv run python scripts/render_outlook_manifest.py --profile production --origin https://outlook-addin.example.com
uv run python scripts/validate_outlook_manifest.py dist/outlook-addin/production/manifest.xml --profile production
PYTHONPATH=src python3 -m pytest test/test_outlook_manifest_validate.py test/test_adapter_smoke.py -q
```

## Word Taskpane Add-In

Source path: `integrations/word_addin/`

Current artifacts:

| Artifact | Path | Use |
|---|---|---|
| Manifest | `integrations/word_addin/manifest.xml` | Sideload or deploy after replacing development URLs. |
| Taskpane | `integrations/word_addin/taskpane.html`, `taskpane.js` | Host on the HTTPS origin referenced by the manifest. |

Packaging boundaries:

- The source manifest uses `https://localhost:3000` for development.
- Pilot and production packages must replace every `https://localhost:3000` URL with a
  deployer-controlled HTTPS origin before Microsoft 365 admin-managed deployment or a
  controlled sideload.
- The Word taskpane requires `ReadDocument`; it is document review, not send-time
  enforcement.
- No script in this repo renders Word manifests yet. Treat the manifest URL rewrite as
  an explicit packaging step and review the XML diff before distribution.
- The backend launcher does not host `taskpane.html` or install the Word add-in.

Release checks:

```sh
PYTHONPATH=src python3 -m pytest test/test_adapter_smoke.py -q
```

## Handoff Checklist

- Record artifact path, SHA-256 digest, source commit, profile, and target tenant/group.
- Record backend endpoint, local daemon endpoint, or hosted server mode used by the
  packaged artifact.
- Verify no browser or Office artifact stores raw prompt, email, document text,
  reversible mappings, or auth headers in local storage, extension storage, logs, or
  telemetry.
- Keep adapter rollback separate from backend rollback: extension policy, Microsoft 365
  assignment, sideload location, and hosted static assets each need their own rollback
  path.
- Use `docs/deployment-rollback.md` for server, local daemon, Outlook, browser, and
  Word uninstall steps.
