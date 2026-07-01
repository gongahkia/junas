# Junas Integrations

Direct API integration is the baseline. UI adapters are optional activation surfaces that collect workflow context, call the backend review contract, display policy decisions, and avoid retaining raw content outside documented runtime boundaries.

| Surface | Maturity | Start here | Source / contract | Notes |
|---|---|---|---|---|
| Direct API | `core` | [`docs/integrations/direct-api.md`](./docs/integrations/direct-api.md), [`docs/api/python_client.md`](./docs/api/python_client.md) | [`src/junas/backend/`](./src/junas/backend/), [`src/junas/client.py`](./src/junas/client.py) | Use when no UI adapter is needed. |
| Outlook Smart Alerts | `supported-target` | [`docs/integrations/outlook.md`](./docs/integrations/outlook.md) | [`integrations/outlook_addin/`](./integrations/outlook_addin/) | Pre-send email review with Smart Alerts limits. |
| Browser GenAI extension | `supported-target` | [`docs/integrations/genai-browser.md`](./docs/integrations/genai-browser.md), [`docs/integrations/browser-extension.md`](./docs/integrations/browser-extension.md) | [`integrations/browser_extension/`](./integrations/browser_extension/) | Managed Chrome/Edge pilot target for GenAI prompt review. |
| Word taskpane | `experimental` | [`docs/integrations/word.md`](./docs/integrations/word.md) | [`integrations/word_addin/`](./integrations/word_addin/) | User-triggered document review, not send-time enforcement. |
| Desktop watcher | `experimental-local-fallback` | [`docs/integrations/desktop-watcher.md`](./docs/integrations/desktop-watcher.md) | [`integrations/desktop/`](./integrations/desktop/), [`packaging/`](./packaging/) | Opt-in local fallback for demos, offline review, and power users. |
| DMS hooks | `experimental` | [`docs/integrations/dms.md`](./docs/integrations/dms.md) | [`src/junas/integrations/dms.py`](./src/junas/integrations/dms.py), [`scripts/scan_dms_manifest.py`](./scripts/scan_dms_manifest.py) | Service-side upload/check-in review; no vendor SDK is shipped here. |
| Future Slack | `planned` | [`docs/integrations/future-slack-google-workspace.md`](./docs/integrations/future-slack-google-workspace.md) | No adapter source yet. | Research-only; no Slack support claim exists yet. |
| Future Google Workspace | `planned` | [`docs/integrations/future-slack-google-workspace.md`](./docs/integrations/future-slack-google-workspace.md) | No adapter source yet. | Research-only; no Google Workspace support claim exists yet. |

Maturity definitions live in [`docs/integrations/maturity-matrix.md`](./docs/integrations/maturity-matrix.md). Current source ownership and security-model notes live in [`integrations/README.md`](./integrations/README.md).
