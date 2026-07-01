# Browser Extension

Source: `integrations/browser_extension/`

Compatibility path: `packaging/browser_extension/`

Maturity: `supported-target`

Runtime target: Chromium MV3 extension for managed Chrome/Edge pilots.

Current files:

- `manifest.json`: extension manifest, target host permissions, content-script matches, options page, service worker.
- `adapters.js`: target selector registry for ChatGPT, Claude, Gemini, and generic editable fallback.
- `content.js`: optional paste interception and review/rewrite result panel.
- `service_worker.js`: backend call bridge.
- `options.html`, `options.js`: backend URL, backend mode, auth mode, operation, paste interception, and token settings.

Package:

```sh
./scripts/package_browser_extension.sh
```

Enterprise deployment: `docs/integrations/browser-enterprise-deployment.md`.

Current behavior:

- Targets `https://chatgpt.com/*`, `https://claude.ai/*`, and `https://gemini.google.com/*`.
- Product copy must describe this adapter as pre-send review for GenAI prompts on managed browser surfaces.
- Target adapters define explicit prompt selectors for ChatGPT, Claude, Gemini, and a generic `textarea`/`input`/`contenteditable` fallback.
- Calls the local Junas daemon at `http://127.0.0.1:8765` by default.
- Backend mode can be `local_daemon` or `hosted_server`.
- Tenant auth mode can be `local_token`, `bearer_token`, or `none`.
- Local daemon token pairing stores the returned token as a `local_token`; hosted server mode sends configured tokens as `Authorization: Bearer ...`.
- Options include a connection-health check that reports `local daemon unavailable`, `auth failed`, `server healthy`, or `policy blocked`.
- Supports `review` plus replacement flows selected in options.
- Paste interception is opt-in through extension settings.
- Prompt review before submit is opt-in through extension settings. For warn decisions, the content script blocks the submit event and asks the user to confirm before re-clicking the detected submit control.
- Adapter domain policy supports `allowedInspectionHosts` and `blockedInspectionHosts`; blocked hosts win and runtime policy cannot expand beyond manifest host coverage, browser site access, or managed runtime host policy.

## Manifest Permission Review

Default MV3 permissions are intentionally narrow:

| Manifest field | Value | Why it is needed |
|---|---|---|
| `permissions` | `storage` | Stores endpoint, backend mode, auth mode, local pairing token, operation, and opt-in toggles. Prompt text must not be stored. |
| `permissions` | `contextMenus` | Adds the explicit "Review selection with Junas" context-menu action. |
| `host_permissions` | `http://127.0.0.1:8765/*` | Allows the service worker to call the local Junas daemon. |
| `content_scripts.matches` | `https://chatgpt.com/*`, `https://claude.ai/*`, `https://gemini.google.com/*` | Loads the content script only on documented GenAI pilot targets. |

Permissions deliberately not requested: `activeTab`, `tabs`, `scripting`, `webRequest`,
`cookies`, `history`, `downloads`, `identity`, and `<all_urls>`.

Hosted-server deployments must build or publish a tenant-specific manifest that adds
only the exact HTTPS backend origin to `host_permissions`, for example
`https://junas.example.com/*`. Do not use `<all_urls>` to make hosted mode work.

## MV3 Service Worker Lifecycle

The background script is an MV3 service worker and must be treated as ephemeral. Do not
store pending review state, raw prompts, policy decisions, auth headers, or endpoint
configuration in service-worker globals. Each `junas-process-text` message loads current
settings with `chrome.storage.sync.get`, performs one backend request, returns the
result, and lets the content script hold any UI state needed for the current page.

Manual QA before release:

- Open the extension details page in `chrome://extensions` or `edge://extensions`.
- Run one context-menu review and one prompt-submit review.
- Stop or let the service worker go inactive, then repeat both reviews.
- Confirm the worker rereads endpoint/auth settings and no in-memory pending review is
  required for retry.

Security model:

- Production rollout should use Chrome Web Store, Edge Add-ons, or enterprise extension policy.
- Local daemon calls require the configured endpoint plus local token when ACLs are enabled.
- Prompt text must not be persisted in extension storage or console logs.
- DOM capture is best-effort and target-specific; this adapter is not universal browser DLP.
- Do not describe this adapter as universal DLP, full-browser DLP, or coverage for arbitrary web apps.
