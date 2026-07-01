# Reviewer Queue Requirements

Status: requirements only. Do not add reviewer queue endpoints or UI code until ADR
0005 is revisited or a dedicated implementation task approves them.

## Purpose

The reviewer queue routes `approval_required` decisions and explicit
`request_approval` actions to authorized reviewers. It must help reviewers assign,
prioritize, decide, and explain approval work while preserving tenant isolation and an
immutable audit trail requirement.

Current implementation note: Junas provides HMAC-chained tamper-evidence only when
`JUNAS_JOURNAL_KEY` or `JUNAS_JOURNAL_KEYS_FILE` is configured, and it does not provide
OS-level append-only storage by itself. The queue requirements below define the
product audit trail target; deployment controls must supply storage immutability where
required.

## Queue Items

Each queue item should represent one approval request for one review session:

| Field | Requirement |
|---|---|
| `approval_id` | Stable id for the approval request. |
| `review_id` | Backend review id from the blocking review response. |
| `request_id` | HTTP request id for support and SIEM correlation. |
| `requested_at` | UTC timestamp for the approval request. |
| `sla_due_at` | UTC timestamp when reviewer action is due. |
| `sla_status` | `within_sla`, `due_soon`, `overdue`, or `breached`. |
| `assigned_to` | Reviewer principal id or null. |
| `assignment_status` | `unassigned`, `assigned`, `claimed`, `reassigned`, or `released`. |
| `required_reviewer_roles` | Roles returned by `/request-approval`. |
| `required_policy_actor_roles` | Policy actor roles required by the decision contract. |
| `surface` and `workflow` | Workflow context from the review. |
| `policy_id` and `policy_version` | Policy metadata from the blocking decision. |
| `decision` | Original policy decision, normally `approval_required`. |
| `required_actions` | Must include `request_approval` for queue entry. |
| `blocking_finding_ids` | Finding ids only, not matched text. |
| `finding_counts` and `severity_counts` | Counts only. |
| `document_hash` | Digest or stored hash reference, not raw text. |

Do not include raw prompt text, email body text, document text, matched spans,
recipient addresses, filenames, reversible mappings, auth headers, local pairing
tokens, or raw reviewer rationale in the queue list.

## Assignment

- Authorized roles: `admin`, `checker`, and configured legal reviewer roles that
  satisfy `required_reviewer_roles`.
- Unauthorized roles: unauthenticated callers, `reviewer` without assignment rights,
  `maker`, local daemon pairing tokens, and local-dev-only reviewer headers in
  production.
- Assignment operations: `assign`, `claim`, `release`, and `reassign`.
- Assignment must be tenant-scoped from authenticated credentials and must not accept
  caller-supplied tenant ids.
- Assignment must use optimistic concurrency with queue item `etag` or latest journal
  sequence.
- Reassignment must require a reason code and preserve prior assignee history.
- A reviewer should not approve their own requested approval unless tenant policy
  explicitly allows self-approval; the UI must show a conflict flag when requester and
  reviewer resolve to the same principal.

Required assignment events:

- `approval_assigned`
- `approval_claimed`
- `approval_released`
- `approval_reassigned`

## Rationale

- A reviewer decision must require `action`, `reason_code`, and reviewer identity.
- Optional free-text rationale must be length-limited, treated as sensitive, and
  excluded from SIEM by default.
- Rationale must not include raw prompt text, email body text, document text, matched
  spans, recipient addresses, filenames, reversible mappings, auth headers, or local
  pairing tokens.
- Allowed decision actions must follow `docs/policy/journal-replay.md`: `approve`,
  `policy_exception`, `accept_risk`, `request_changes`, `hold`, `reject`, and legacy
  `accept` or `rewrite` where compatibility requires them.
- Approval decisions must be recorded through the backend decision path, not by the UI
  mutating queue state directly.

Required decision events:

- `approval_decision_recorded`
- `decision_recorded`

## SLA

- SLA timers start at `requested_at`.
- `sla_due_at` must be stored as UTC and computed from tenant policy, workflow,
  severity, and required action.
- Queue filters must include `sla_status`, `assigned_to`, `surface`, `workflow`,
  `policy_id`, `policy_version`, and `decision`.
- The UI must show overdue and breached approvals without exposing raw reviewed
  content.
- SLA breach events must be privacy-safe and include ids, roles, policy metadata,
  counts, and timestamps only.

Required SLA events:

- `approval_sla_due_soon`
- `approval_sla_breached`

## Audit Trail

The immutable audit trail requirement means queue actions must be reconstructable from
event history, not from mutable UI state alone. Each event must include tenant id,
actor id, actor role, request id, approval id, review id, event timestamp, journal
sequence, prior state, new state, reason code when supplied, policy id/version, and
hashes or counts for reviewed content. Events must not include raw reviewed content or
matched text.

Journal verification must use `scripts/verify_journal.py`. Audit export must preserve
queue events in the same review-session evidence set as `approval_requested` and
`decision_recorded`.

## Required UI States

- Unassigned queue, assigned-to-me queue, overdue queue, and completed decisions.
- Assignment history with assignee, assigner, timestamp, reason code, and event id.
- Decision form with action, reason code, optional sensitive rationale, and policy
  context.
- SLA indicator with due time, status, and escalation state.
- Read-only event history linked to journal verification status.

## Non-Goals

- No broad raw document viewer.
- No queue assignment from caller-supplied tenant ids.
- No reviewer decision that bypasses `/review/{review_id}/decision`.
- No SIEM event containing raw rationale, raw content, matched text, recipients,
  filenames, mappings, auth headers, or local pairing tokens.
- No claim that Junas alone provides storage-level immutability without deployment
  controls.

## Related Documents

- `docs/adr/0005-admin-console-docs-only-until-validation.md`
- `docs/admin-console/requirements.md`
- `docs/policy/decision-contract.md`
- `docs/policy/journal-replay.md`
- `docs/integrations/sequence-diagrams.md`
- `docs/security/api-inventory.md`
