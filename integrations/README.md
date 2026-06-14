# Kaypoh Integrations

Adapters are optional activation surfaces. The FastAPI backend remains the trust boundary for validation, tenant auth, deterministic review, policy decisions, rewrite actions, audit evidence, and SIEM-safe observability. Direct HTTP/OpenAPI integration is the baseline path and does not require any UI adapter.

This directory is an integration index until the ADR 0004 follow-up move lands. Current adapter source still lives in `packaging/`, `src/kaypoh/desktop/`, and `src/kaypoh/integrations/`.

No `CODEOWNERS` file exists in this repo, so owner labels below are functional owners.

| Surface | Maturity | Owner | Runtime target | Security model | Current source |
|---|---|---|---|---|---|
| Direct API and Python client | `core` | Backend/API | FastAPI service, OpenAPI, `kaypoh.client` | Server-side API key/JWT auth, tenant isolation, TLS at deployment, backend audit logs; no UI runtime storage. | `src/kaypoh/backend/`, `src/kaypoh/client.py`, `docs/api/` |
| Outlook Smart Alerts | `supported-target` | Integrations/Microsoft 365 | Office.js Outlook add-in with `OnMessageSend` Smart Alerts | Microsoft 365 admin deployment, HTTPS add-in origin, backend auth or local pairing token, no message body storage in add-in storage/logs. | `packaging/office_addin/` |
| Browser GenAI extension | `supported-target` | Integrations/Browser | Chromium MV3 extension for managed Chrome/Edge pilots | Enterprise extension policy, allowed target domains, backend auth or local daemon token, no prompt persistence in extension storage/logs. | `packaging/browser_extension/` |
| Word taskpane | `experimental` | Integrations/Microsoft 365 | Office.js Word taskpane | Admin deployment or dev sideload, backend auth or local pairing token, user-triggered document review; not send-time enforcement. | `packaging/word_addin/` |
| Desktop watcher | `experimental-local-fallback` | Local desktop | macOS local watcher and packaged local daemon | Explicit user opt-in, loopback/local ACL, `X-Kaypoh-Local-Token`, scoped output directory, no enterprise enforcement claim. | `src/kaypoh/desktop/`, `packaging/kaypoh-local.spec`, `packaging/macos/` |
| DMS manifest scanner | `experimental` | Platform integrations | Neutral JSON manifest scanner for DMS exports or service-side hooks | Service account/API-key auth, tenant policy, matter/session ids, backend audit fields; no vendor SDK or repository write path in repo. | `src/kaypoh/integrations/dms.py`, `scripts/scan_dms_manifest.py` |

Maturity labels:

- `core`: stable integration baseline for backend and API clients.
- `supported-target`: primary adapter target with roadmap priority, but still subject to certification, deployment docs, and platform limitations.
- `experimental`: usable substrate or prototype that must not be marketed as production enforcement.
- `experimental-local-fallback`: local opt-in fallback for demos, offline use, or power users.

Security rule: adapters collect workflow context, call `/review` or follow-on action endpoints, display policy decisions, and avoid retaining raw prompts, email bodies, document text, reversible mappings, or auth headers outside documented runtime boundaries.
