# Adapter Compatibility Matrix

Status: normative for adapter support claims. This matrix describes current adapter behavior, not every capability exposed by the backend API.

Use with `docs/integrations/maturity-matrix.md`, `docs/integrations/adapter-protocol.md`, and `docs/integrations/document-context.md`.

## Legend

| Status | Meaning |
|---|---|
| `yes` | Supported by the current adapter contract and docs. |
| `limited` | Supported only in the stated workflow or with reduced behavior. |
| `backend-only` | The backend API supports it, but this adapter has no dedicated UX/enforcement path. |
| `conditional` | Requires tenant/runtime configuration such as OCR or a production hook. |
| `no` | Not supported by the current adapter. |

## Capability Matrix

| Adapter | Inline text | DOCX | PDF | Images | Attachments | Metadata scrub | Reidentify | Approvals |
|---|---|---|---|---|---|---|---|---|
| Direct API | `yes` via `text` | `yes` via `document_base64` | `yes` via `document_base64` | `conditional` OCR/image review | `limited` caller-owned payload or `attachment_count` | `yes` via `/documents/scrub` | `yes` via `/reidentify` | `yes` via `/request-approval` |
| Outlook Smart Alerts | `yes` body plus subject | `no` attachment contents are not read | `no` attachment contents are not read | `no` attachment contents are not read | `limited` count only, no names/bytes | `no` | `no` | `limited` route/soft-block on approval-required decisions |
| Browser GenAI extension | `yes` selected text, paste, prompt submit | `no` upload widgets are out of scope | `no` upload widgets are out of scope | `no` multimodal uploads are out of scope | `no` | `no` | `no` | `no` |
| DMS hook/scanner | `yes` extracted text or manifest text | `conditional` production hook with payload | `conditional` production hook with payload | `conditional` OCR-enabled backend and hook payload | `limited` batch/count metadata | `backend-only` hook must call `/documents/scrub` | `backend-only` direct API only unless hook implements it | `yes` hold check-in pending reviewer approval |
| Word taskpane | `yes` selection or body text | `no` taskpane reads text, not raw DOCX | `no` | `no` | `no` | `no` | `no` | `no` document review only |
| Desktop watcher | `yes` text-like files and clipboard | `no` default suffix list excludes DOCX | `no` default suffix list excludes PDF | `no` | `no` | `no` | `no` | `no` local fallback only |

## Notes

- `Attachments` means adapter handling beyond `attachment_count`. Outlook sends only counts; filenames and bytes are intentionally excluded.
- `Images` means reviewing image content, not only metadata. Image review requires OCR/image-scan configuration and is not claimed by browser, Outlook, Word, or desktop adapters.
- `Metadata scrub` refers to `POST /documents/scrub`, not review-time metadata leakage findings.
- `Reidentify` requires an authorized caller plus a supplied mapping or persisted document hash; UI adapters do not expose it by default.
- `Approvals` require backend journal persistence and authorized reviewer decision handling. Adapters can request or route approvals, but adapters are not approval authorities.
- A `backend-only` entry must not be marketed as adapter support until that adapter has UX, auth, privacy, telemetry, and QA evidence for the flow.

## Promotion Rule

Before changing any `no`, `limited`, `conditional`, or `backend-only` cell to `yes`, add evidence in the adapter doc covering:

- request payload shape and surface/workflow fields
- auth and tenant boundary
- privacy storage/log behavior
- failure semantics
- idempotency behavior
- manual or automated QA
