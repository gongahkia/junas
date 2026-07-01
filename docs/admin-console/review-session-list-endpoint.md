# Review Session List Endpoint Requirements

Status: requirements only. Do not implement the endpoint until ADR 0005 is
revisited or an explicit admin-console endpoint task approves code changes.

## Proposed Route

`GET /admin/review-sessions`

Purpose: return a tenant-scoped, read-only list of review-session metadata for the
admin console. The response must support workflow triage, audit lookup, and tenant
health checks without exposing raw reviewed content.

## Authorization

- Auth group: audit/admin access.
- Allowed production roles: `admin`, `auditor`, and `checker`.
- Denied roles: unauthenticated callers, `reviewer`, `maker`, local-daemon pairing
  tokens, and local-dev-only reviewer headers.
- Tenant scope must come from the authenticated credential. The request must not
  accept `tenant_id`, `tenant`, or equivalent caller-supplied tenant selectors.
- The route must not accept `tenant_id` as a query parameter or path parameter.
- Every query, cursor, and row fetch must be bound to the credential-derived tenant.
  A cursor from another tenant must fail with a generic invalid-cursor response that
  does not reveal whether sessions exist.

## Query Parameters

| Parameter | Required | Requirement |
|---|---:|---|
| `limit` | no | Default 50, maximum 100, minimum 1. Invalid values fail fast with 422. |
| `cursor` | no | opaque server-generated cursor. It must be bound to tenant, role, filters, and sort order. |
| `surface` | no | Enum filter matching review workflow context, such as `outlook`, `browser`, `dms`, or `api`. |
| `workflow` | no | Enum filter matching review workflow context, such as `email_send`, `genai_prompt`, or `document_upload`. |
| `adapter` | no | Enum or normalized adapter id from accepted adapter telemetry. |
| `decision` | no | One policy decision: `allow`, `warn`, `block`, `approval_required`, or `rewrite_required`. |
| `required_action` | no | One action from the policy action catalog. |
| `policy_id` | no | Exact policy id. |
| `policy_version` | no | Exact policy version. |
| `created_after` | no | Inclusive UTC timestamp. |
| `created_before` | no | Exclusive UTC timestamp. |
| `approval_status` | no | `none`, `pending`, `approved`, `rejected`, or `expired`. |

Do not add full-text search, raw-recipient search, raw-filename search, or matched-text
search to this endpoint.

## Pagination

- Sort order: `created_at` descending, then `review_id` descending for deterministic
  pagination.
- Cursor form: opaque string, not JSON exposed to clients.
- Cursor contents: may include signed or encrypted pagination state, but must not
  contain raw prompt text, email bodies, document text, matched spans, recipient
  addresses, filenames, auth headers, or reversible mappings.
- Cursor reuse with changed filters must fail with a generic invalid-cursor response.
- Empty result sets return `items: []` and `next_cursor: null`.

## Response Shape

Return only metadata needed for review-session listing:

```json
{
  "items": [
    {
      "review_id": "b7f1faad-1d2b-4c35-9f60-6b7f08d6fbfb",
      "request_id": "b7f1faad-1d2b-4c35-9f60-6b7f08d6fbfb",
      "created_at": "2026-07-01T09:30:00Z",
      "review_expires_at": "2026-07-01T09:35:00Z",
      "surface": "outlook",
      "workflow": "email_send",
      "adapter": "outlook_smart_alerts",
      "document_type": "email",
      "document_hash": "sha256:...",
      "document_char_count": 120,
      "recipient_count": 3,
      "recipient_domain_count": 2,
      "attachment_count": 1,
      "policy_decision": "approval_required",
      "send_allowed": false,
      "required_actions": ["request_approval"],
      "recommended_actions": [],
      "blocking_finding_count": 2,
      "finding_counts": {"PII": 1, "MNPI": 1},
      "severity_counts": {"high": 2},
      "policy_id": "default",
      "policy_version": "2026-06-14",
      "approval_status": "pending",
      "journal_seq": 3,
      "journal_hmac_present": true
    }
  ],
  "next_cursor": null,
  "page_size": 1
}
```

Field requirements:

- `document_hash` must be a digest or stored hash reference, not body text.
- `recipient_count` and `recipient_domain_count` may be counts only. Raw recipients
  and recipient domains must not appear in list rows.
- `finding_counts`, `severity_counts`, and `blocking_finding_count` may expose counts.
  They must not expose `matched_text`, source snippets, or replacement originals.
- `policy_decision`, `required_actions`, `recommended_actions`, `policy_id`, and
  `policy_version` must mirror backend policy output, not UI-derived logic.
- `journal_hmac_present` may expose whether integrity metadata exists, but not keys or
  raw HMAC material beyond existing audit-pack verification outputs.

## Privacy And Security Gates

- No raw body exposure by default: the list endpoint must never return prompt text,
  email body text, document text, matched spans, reversible mappings, auth headers,
  local pairing tokens, raw reviewer rationale, recipient addresses, or filenames.
- Object-level authorization must be tested even though the endpoint is a list: every
  row must be filtered by credential-derived tenant before pagination is applied.
- Role checks must be tested for `auditor`, `checker`, `admin`, `reviewer`, `maker`,
  unauthenticated, and local-dev-only header cases.
- Cross-tenant cursor use must fail without disclosing whether the cursor or tenant
  exists.
- The endpoint must emit a privacy-safe audit event such as
  `admin_review_sessions_listed` with tenant id, actor id, filters used, item count,
  and request id, but no raw content or matched text.
- SIEM export for this event may include counts, decision names, policy id/version,
  surface, workflow, and status code only.

## Implementation Gates

Before code ships:

- Add the route to `docs/security/api-inventory.md` from the live route table after
  implementation.
- Add OpenAPI examples for the list response.
- Add endpoint tests proving pagination stability, tenant isolation, role checks, and
  no raw body exposure by default.
- Add a regression test that a cursor minted for one tenant cannot list another
  tenant's sessions.
- Add a regression test that response JSON does not include raw `text`,
  `matched_text`, `original_text`, `recipient`, `filename`, mapping values, or auth
  tokens.

## Related Documents

- `docs/adr/0005-admin-console-docs-only-until-validation.md`
- `docs/admin-console/requirements.md`
- `docs/security/api-inventory.md`
- `docs/security/adapter-threat-model.md`
- `docs/policy/decision-contract.md`
