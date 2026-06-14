# Browser Extension

Source: `integrations/browser_extension/`

Compatibility path: `packaging/browser_extension/`

Maturity: `supported-target`

Runtime target: Chromium MV3 extension for managed Chrome/Edge pilots.

Current files:

- `manifest.json`: extension manifest, target host permissions, content-script matches, options page, service worker.
- `content.js`: optional paste interception and review/rewrite result panel.
- `service_worker.js`: backend call bridge.
- `options.html`, `options.js`: endpoint, operation, paste interception, and token settings.

Package:

```sh
./scripts/package_browser_extension.sh
```

Current behavior:

- Targets `https://chatgpt.com/*`, `https://claude.ai/*`, and `https://gemini.google.com/*`.
- Calls the local Kaypoh daemon at `http://127.0.0.1:8765` by default.
- Supports `review` plus replacement flows selected in options.
- Paste interception is opt-in through extension settings.

Security model:

- Production rollout should use Chrome Web Store, Edge Add-ons, or enterprise extension policy.
- Local daemon calls require the configured endpoint plus local token when ACLs are enabled.
- Prompt text must not be persisted in extension storage or console logs.
- DOM capture is best-effort and target-specific; this adapter is not universal browser DLP.
