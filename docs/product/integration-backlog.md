# User-Requested Integration Backlog

This backlog is for integrations requested by target users during interviews, pilots,
support intake, or procurement demos. No validated user-requested integration rows are
recorded in this repo yet. Do not add a request unless it has a source, date, user
segment, workflow, and evidence link that can be checked without exposing raw customer
content.

## Required Categories

Each request must use exactly one category:

| Category | Use when |
|---|---|
| `direct API` | The customer owns a service, gateway, DMS hook, workflow engine, or backend path that can call `/review` directly. |
| `Outlook` | The request is specifically for Outlook email send, compose, Smart Alerts, or taskpane behavior. |
| `browser` | The request is for managed browser prompt/page review, usually GenAI prompt submit or paste review. |
| `DMS` | The request is for document upload, check-in, matter metadata, repository review, or DMS-side audit fields. |
| `Slack` | The request is for Slack message, file, canvas, list, Discovery API, or DLP interop behavior. |
| `Google Workspace` | The request is for Gmail, Google Chat, Drive, Docs, Sheets, Slides, Calendar, Chrome, or Workspace DLP interop behavior. |
| `unsupported` | The request is outside Junas scope, lacks an implementable workflow hook, would overclaim DLP coverage, or conflicts with privacy/security boundaries. |

## Validated Request Ledger

No validated user-requested integration rows are recorded yet.

When validation exists, add rows in this shape:

| Request id | Date | Source | User segment | Workflow requested | Category | Status | Evidence |
|---|---|---|---|---|---|---|---|
| `REQ-YYYY-NNN` | `YYYY-MM-DD` | interview, pilot, support, or procurement demo | legal, compliance, security, end user, or platform integrator | one sentence | one required category | new, researching, planned, rejected, or shipped | link to sanitized notes, issue, or PR |

## Status Rules

- `new`: request captured but not evaluated.
- `researching`: discovery work is active; no support claim exists.
- `planned`: implementation path, owner, and exit criteria are accepted.
- `rejected`: request is out of scope, unsafe, unmeasurable, or better served by direct API/existing controls.
- `shipped`: code, docs, tests, packaging, privacy checks, support path, and rollback path are complete.

## Review Rules

- Do not treat roadmap research as a user request.
- Do not add raw customer text, screenshots, prompts, emails, documents, recipient
  addresses, channel names, or auth material to the ledger.
- Use `unsupported` instead of stretching a supported category when the requested
  workflow has no reliable pre-send, pre-submit, upload, or review hook.
- Link Slack and Google Workspace requests to `docs/integrations/future-slack-google-workspace.md`
  until implemented source, auth, privacy, telemetry, packaging, uninstall, and smoke
  tests exist.
- Revisit the backlog after every five validated interviews or after a pilot support
  review.
