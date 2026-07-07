# Adapter Threat Model

Adapters are activation surfaces. They collect workflow context, call the backend, and display policy decisions. They are not alternate trust boundaries and must not make final tenant, role, policy, audit, or retention decisions outside the backend contract.

## Common Boundary

| Area | Boundary |
|---|---|
| Tenant identity | Resolved from backend API key/JWT or local pairing token, not from adapter-supplied tenant fields. |
| Policy decision | Returned by `/review` and follow-on endpoints. Adapter UI can explain or route the decision but must not soften it. |
| Raw content | Sent only in the intended review request. Do not store raw prompts, email bodies, document text, matched spans, reversible mappings, or auth headers in adapter storage, telemetry, console logs, or DMS-visible audit fields. |
| Idempotency | Adapter retry keys must not contain raw content. Use keyed hashes plus workflow metadata. |
| Failure handling | No silent completion after a failed or skipped review unless tenant policy explicitly allows that degraded behavior for the surface. |
| Telemetry | Emit counts, hashes, ids, durations, decision names, and error categories only. |

## Surface Matrix

| Surface | Sensitive input | Main threats | Required controls | Residual limits |
|---|---|---|---|---|
| Outlook Smart Alerts | Message body, subject, recipient domains/count, attachment count, endpoint, local token. | Unsupported Outlook client, add-in unavailable before event runs, backend timeout, auth failure, local storage leakage, console logging, broad Microsoft 365 assignment. | Microsoft 365 admin deployment, HTTPS add-in origin, manifest validation, CORS/well-known checks, backend auth or local pairing token, short send-hook timeout, no body/subject/recipient/token persistence, per-client QA before rollout. | `SoftBlock` is not fail-closed when Outlook cannot run the add-in; current adapter does not inspect attachment content, sensitivity labels, or mobile send-time paths. |
| Browser GenAI extension | Selected text, pasted prompt text, target URL, endpoint, local or bearer token. | DOM selector drift, shadow DOM/canvas editors, target CSP changes, MV3 worker restart, unrecognized GenAI UI, prompt persistence in extension storage, overbroad host permissions. | Managed Chrome/Edge deployment, minimal host permissions, explicit target adapters, visible failure UI, local daemon origin/token checks or hosted bearer auth, no prompt logging/storage, selector smoke tests before expanding claims. | Not universal browser DLP; cannot cover mobile apps, native apps, arbitrary websites, file uploads, or future target UI changes without tests. |
| Word taskpane | Selected text or body text, endpoint, local token or bearer token. | User assumes review is enforcement, raw document persistence, stale review after edits, broad `ReadDocument` permission misuse, dev sideload leakage. | Admin deployment or controlled sideload, configured backend/local daemon only, no raw document/auth persistence, clear taskpane failure display, fresh review after edits, route enforced completion to Outlook, DMS, or direct API. | User-triggered review only; does not block save, export, print, email send, DMS upload, or repository check-in. |
| Desktop watcher/local daemon | File text, clipboard text, paths, anonymized output path, local token, local daemon secret. | Clipboard over-collection, auth failure leaking clipboard/file content, output outside configured directory, same-user local token access, notification path exposure, broad recursive folder scans, accidental large-file scans, LaunchAgent installed by default without admin decision. | Explicit file/folder/clipboard opt-in, clipboard off by default, `X-Junas-Local-Token` when ACL enabled, scoped output directory, no raw content on auth failures, count/path-only notifications, dedicated watched folder, optional LaunchAgent install, local daemon security controls in `docs/security/local-daemon.md`. | Local fallback only; does not block paste, save, send, upload, browser submit, or email send. Loopback is still reachable by local processes. |
| DMS hook/scanner | Document payload/text, matter id, document id, filename/MIME type, actor id, DMS version, audit fields. | Vendor SDK credential leakage, wrong matter/session binding, raw text in DMS audit fields, check-in allowed after degraded review, replayed retries, tenant cross-read by guessed ids. | Service-account backend auth, namespaced matter ids, `surface="dms"` and `workflow="document_upload"`, idempotency key, no raw text/matched spans in DMS-visible audit, hold/block behavior for controlled repositories, tenant-scoped review/session access. | Current repo ships a `mockdms` pre-check-in hook and neutral JSON manifest scanner, not a real vendor SDK write-back integration or customer repository enforcement agent. |
| Direct API | Inline text or document payload, workflow metadata, auth credential, review id, document hash, mapping ids. | Caller logs raw request/response, caller-supplied tenant trusted by mistake, replay without idempotency, reidentify misuse, unbounded payloads, weak service auth. | TLS/reverse proxy, API-key registry or JWT tenant auth, backend role checks, request body caps, no-body logs, idempotency guidance, object-level authorization tests for ids, SIEM-safe events. | Caller owns workflow UI and completion behavior; backend cannot prove a caller actually blocked its own downstream action. |

## Adapter Rules

- Do not accept adapter-supplied tenant id, actor role, or reviewer identity as authoritative when backend auth is enabled.
- Do not cache policy decisions beyond `review_expires_at`; edited content needs a fresh review.
- Do not retry validation, auth, or policy-version failures as if they were transport timeouts.
- Do not add adapter telemetry fields until the field is classified as allowed, hashed, or prohibited.
- Do not market an adapter as supported unless its maturity label, docs, smoke tests, privacy checks, and failure behavior agree.

## References

- [`docs/integrations/outlook.md`](../integrations/outlook.md)
- [`docs/integrations/genai-browser.md`](../integrations/genai-browser.md)
- [`docs/integrations/browser-extension.md`](../integrations/browser-extension.md)
- [`docs/integrations/word.md`](../integrations/word.md)
- [`docs/integrations/desktop-watcher.md`](../integrations/desktop-watcher.md)
- [`docs/integrations/dms.md`](../integrations/dms.md)
- [`docs/integrations/direct-api.md`](../integrations/direct-api.md)
- [`docs/security/local-daemon.md`](./local-daemon.md)
- [`docs/policy/decision-contract.md`](../policy/decision-contract.md)
- [`docs/api/idempotency.md`](../api/idempotency.md)
