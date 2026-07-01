# Document Context

Status: normative for adapters. Document context is policy input and review correlation metadata; it is not adapter storage for raw file paths, user comments, or customer matter names.

Use with `docs/integrations/adapter-protocol.md`, `docs/integrations/recipient-context.md`, `docs/integrations/privacy.md`, and `docs/api/idempotency.md`.

## Canonical Fields

| Field | Shape | Adapter rule |
|---|---|---|
| `document_base64` | base64 text, DOCX, PDF, supported office/container file, or image payload when OCR is configured | Send only when the backend must extract or inspect the document. Do not duplicate the same content in `text`. |
| `document_filename` | optional string, max 256 chars | Use the leaf filename only. Strip paths, UNC shares, user home directories, and temporary directory names before calling `/review`. |
| `document_mime_type` | optional string, max 128 chars | Send the adapter-observed MIME type when known. Backend extraction normalizes it to lower-case and may infer from filename when omitted. |
| `attachment_count` | optional integer, 0-1000 | Send a count of attachments or associated uploaded files. Do not send attachment names unless that attachment is the document payload being reviewed. |
| `session_id` | optional `[A-Za-z0-9_-]{1,128}` | Adapter-scoped review session for related documents that share defined terms. Not auth, tenant selection, or user identity. |
| `matter_id` | optional `[A-Za-z0-9_-:]{1,128}` | Tenant-scoped matter/workspace id above `session_id`. Colon is allowed for `{dms_vendor}:{matter_id}` composite ids. |

Policy semantics:

- Provide exactly one content source: `text` or `document_base64`.
- `document_filename` and `document_mime_type` are extraction hints, not authorization signals.
- `attachment_count` changes are material context changes and require a new review and idempotency key.
- `session_id` accumulates defined terms for a short-lived review session.
- `matter_id` accumulates defined terms across sessions for the same matter.
- Unknown fields should be omitted/null, not fabricated.

## Filename Behavior

Adapters must strip filenames to the basename before sending:

```json
{
  "document_filename": "draft-spa.pdf",
  "document_mime_type": "application/pdf"
}
```

Rules:

- Strip paths; do not send local paths, SharePoint paths, DMS folder paths, download URLs, user home directories, or temp paths.
- Do not put filenames in telemetry, SIEM details, idempotency keys, support logs, or persistent adapter state.
- Use filename only for display and MIME inference. A filename extension must not override backend content validation.
- If the adapter has no filename, omit it or use a neutral local value such as `inline.txt` only inside the adapter process.
- User edits, renames, or replaces the file after review require a fresh `/review` when the payload or workflow context changes.

## MIME Type Behavior

`document_mime_type` should reflect the adapter's best available MIME observation:

| Content | Preferred MIME |
|---|---|
| Plain text | `text/plain` |
| Markdown | `text/markdown` |
| JSON | `application/json` |
| PDF | `application/pdf` |
| DOCX | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| XLSX | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| PPTX | `application/vnd.openxmlformats-officedocument.presentationml.presentation` |
| Email | `message/rfc822` |
| PNG/JPEG image | `image/png` or `image/jpeg` |

Rules:

- Omit `document_mime_type` when unknown; backend extraction can infer from filename for common formats.
- Treat caller-provided MIME as a hint. Backend magic-byte and parser checks remain authoritative.
- Unsupported or empty extraction can return degraded review or fail closed according to tenant ingestion policy.
- Do not log raw parser errors when they include file paths or document text.

## Attachment Count

`attachment_count` is the number of files attached to or associated with the workflow, not the number of files Junas extracted.

Surface rules:

- Outlook: count visible email attachments; do not send attachment names or bytes unless a selected attachment is sent as `document_base64`.
- Browser GenAI: normally omit or set `0`; do not inspect page uploads unless the adapter has explicit upload-review support.
- DMS: count associated files in the upload/check-in batch when the hook exposes them.
- Desktop watcher: use `1` for a single watched file review unless a bundled folder/archive review is explicit.
- Direct API: caller owns the count and must rotate idempotency when it changes.

## Session ID Behavior

`session_id` groups related documents that share definitions, for example a SPA and disclosure schedule reviewed in one work session.

Rules:

- Use a non-sensitive adapter-generated id such as `compose-7f3a`, `tab-91b`, or `upload-2026-07-01-01`.
- Do not use emails, user names, document names, matter names, tenant names, prompt text, or raw file ids.
- Session scope is below matter scope. A document with both `session_id` and `matter_id` inherits both session and matter defined terms.
- Rotate `session_id` when the user starts an unrelated compose, prompt, upload, or document review.
- Treat `session_id` as tenant-scoped when tenancy is enabled; it must not cross tenants.

## Matter ID Behavior

`matter_id` is an opaque tenant-scoped identifier for long-running document sets. It sits above `session_id`.

Rules:

- DMS matter id values should use stable ids from the DMS/workspace layer, preferably namespaced as `{dms}:{matter_id}`, for example `imanage:M123`.
- Do not use raw matter names, client names, deal names, workspace display names, folder names, or free-text descriptions.
- Matter-defined terms persist across reviewers, weeks, and sessions for the same tenant matter.
- A new or changed matter id is a material context change and requires a new review and idempotency key.
- Matter ids are not authorization grants. Tenant and role identity come from validated credentials.
- Store telemetry as `matter_id_hash` only when correlation is required.

## DMS Matter ID

DMS adapters should distinguish:

| Field | Meaning | Storage rule |
|---|---|---|
| `matter_id` | Matter/workspace id sent to `/review` for defined-term inheritance. | Hash in telemetry; store raw only in tenant-controlled DMS audit metadata when policy allows. |
| `document_id` | DMS document id or pre-check-in draft id. | Adapter audit metadata, not a `/review` schema field. |
| `dms` | Repository family such as `imanage` or `netdocuments`. | Adapter metadata only; no vendor SDK dependency is required by the backend contract. |

Do not concatenate matter names or folder names into `matter_id`. Use stable ids already governed by the customer DMS.

## Surface Defaults

| Surface | Document context |
|---|---|
| Outlook | `document_type="email"`, body as `text`, attachment count only by default, no attachment filenames. |
| Browser GenAI | `document_type="prompt"`, prompt as `text`, no document filename, usually no attachment count. |
| DMS | `document_type="dms_document"`, extracted text or `document_base64`, `document_filename`, `document_mime_type`, namespaced `matter_id`, document id in adapter audit metadata. |
| Word | `document_type="document_review"`, selected document text or payload, stable `session_id` for current taskpane review. |
| Desktop watcher | watched file as `document_base64`, basename-only `document_filename`, inferred MIME, `attachment_count=1`. |
| Direct API | caller-selected text or document payload plus caller-owned `session_id`/`matter_id` when needed. |

## Privacy QA

Before support claims, test:

- Filenames are basename-only and absent from telemetry, SIEM, logs, and idempotency keys.
- MIME type is lower-case or omitted and backend validation handles mismatches.
- Attachment count changes rotate idempotency keys.
- `session_id` rejects spaces, path separators, and raw user/document names.
- `matter_id` accepts namespaced DMS ids such as `imanage:M123` and rejects raw matter names with spaces.
- DMS audit metadata uses ids/counts/hashes and does not store raw document text, matched text, auth material, or matter display names.
