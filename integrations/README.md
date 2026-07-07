# Junas Integrations

Adapters are optional activation surfaces. The FastAPI backend remains the trust boundary for validation, tenant auth, deterministic review, policy decisions, rewrite actions, audit evidence, and SIEM-safe observability. Direct HTTP/OpenAPI integration is the baseline path and does not require any UI adapter.

This directory contains adapter source after ADR 0004. Old `packaging/*_addin`, `packaging/browser_extension`, and `src/junas/desktop` paths remain as compatibility symlinks for existing local workflows.

No `CODEOWNERS` file exists in this repo, so owner labels below are functional owners.

| Surface | Maturity | Owner | Runtime target | Security model | Current source |
|---|---|---|---|---|---|
| Direct API and Python client | `core` | Backend/API | FastAPI service, OpenAPI, `junas.client` | Server-side API key/JWT auth, tenant isolation, TLS at deployment, backend audit logs; no UI runtime storage. | `src/junas/backend/`, `src/junas/client.py`, `docs/api/` |
| Outlook Smart Alerts | `supported-target` | Integrations/Microsoft 365 | Office.js Outlook add-in with `OnMessageSend` Smart Alerts | Microsoft 365 admin deployment, HTTPS add-in origin, backend auth or local pairing token, no message body storage in add-in storage/logs. | `integrations/outlook_addin/` |
| Browser GenAI extension | `supported-target` | Integrations/Browser | Chromium MV3 extension for managed Chrome/Edge pilots | Enterprise extension policy, allowed target domains, backend auth or local daemon token, no prompt persistence in extension storage/logs. | `integrations/browser_extension/` |
| Word taskpane | `experimental` | Integrations/Microsoft 365 | Office.js Word taskpane | Parking path: admin deployment or dev sideload, backend auth or local pairing token, user-triggered document review; not save, export, print, share, email-send, DMS-upload, or repository check-in enforcement. | `integrations/word_addin/` |
| Desktop watcher | `experimental-local-fallback` | Local desktop | macOS local watcher and packaged local daemon | Explicit user opt-in, loopback/local ACL, `X-Junas-Local-Token`, scoped output directory, no enterprise enforcement claim. | `integrations/desktop/`, `packaging/junas-local.spec`, `packaging/macos/` |
| DMS mock check-in hook and manifest scanner | `experimental` | Platform integrations | Concrete `mockdms` pre-check-in hook plus neutral JSON manifest scanner for DMS exports. | Service account/API-key auth, tenant policy, matter/session ids, idempotency key hash, backend audit fields; no real vendor SDK or customer repository write path in repo. | `src/junas/integrations/dms.py`, `scripts/mock_dms_checkin.py`, `scripts/scan_dms_manifest.py` |

Maturity labels:

- `core`: stable integration baseline for backend and API clients.
- `supported-target`: primary adapter target with roadmap priority, but still subject to certification, deployment docs, and platform limitations.
- `experimental`: usable substrate or prototype that must not be marketed as production enforcement.
- `experimental-local-fallback`: local opt-in fallback for demos, offline use, or power users.

Security rule: adapters collect workflow context, call `/review` or follow-on action endpoints, display policy decisions, and avoid retaining raw prompts, email bodies, document text, reversible mappings, or auth headers outside documented runtime boundaries.

Final enforced completion should run through Outlook Smart Alerts, DMS hooks, direct API, or another controlled workflow unless a Word enforcement path is implemented and promoted.
