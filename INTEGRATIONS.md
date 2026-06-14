# Kaypoh Integrations

Direct API integration is the baseline. UI adapters are optional activation surfaces that collect workflow context, call the backend review contract, display policy decisions, and avoid retaining raw content outside documented runtime boundaries.

| Surface | Maturity | Start here | Source / contract | Notes |
|---|---|---|---|---|
| Direct API | `core` | [`docs/api/README.md`](./docs/api/README.md), [`docs/api/python_client.md`](./docs/api/python_client.md) | [`src/kaypoh/backend/`](./src/kaypoh/backend/), [`src/kaypoh/client.py`](./src/kaypoh/client.py) | Use when no UI adapter is needed. |
| Outlook Smart Alerts | `supported-target` | [`docs/integrations/outlook.md`](./docs/integrations/outlook.md) | [`integrations/outlook_addin/`](./integrations/outlook_addin/) | Pre-send email review with Smart Alerts limits. |
| Browser GenAI extension | `supported-target` | [`docs/integrations/browser-extension.md`](./docs/integrations/browser-extension.md) | [`integrations/browser_extension/`](./integrations/browser_extension/) | Managed Chrome/Edge pilot target for GenAI prompt review. |
| Word taskpane | `experimental` | [`docs/integrations/word.md`](./docs/integrations/word.md) | [`integrations/word_addin/`](./integrations/word_addin/) | User-triggered document review, not send-time enforcement. |
| Desktop watcher | `experimental-local-fallback` | [`docs/integrations/desktop-watcher.md`](./docs/integrations/desktop-watcher.md) | [`integrations/desktop/`](./integrations/desktop/), [`packaging/`](./packaging/) | Opt-in local fallback for demos, offline review, and power users. |
| DMS hooks | `experimental` | [`docs/product/workflows.md#dms-upload`](./docs/product/workflows.md#dms-upload) | [`src/kaypoh/integrations/dms.py`](./src/kaypoh/integrations/dms.py), [`scripts/scan_dms_manifest.py`](./scripts/scan_dms_manifest.py) | Service-side upload/check-in review; no vendor SDK is shipped here. |
| Future Slack | `planned` | Use direct API contract first. | No adapter source yet. | Future note: capture message text, channel/workspace context, actor role, and destination policy without storing raw chat content. |
| Future Google Workspace | `planned` | Use direct API contract first. | No adapter source yet. | Future note: separate Gmail send review, Drive upload/check-in review, and Docs editor review; no coverage claim exists yet. |

Maturity definitions live in [`docs/integrations/maturity-matrix.md`](./docs/integrations/maturity-matrix.md). Current source ownership and security-model notes live in [`integrations/README.md`](./integrations/README.md).
