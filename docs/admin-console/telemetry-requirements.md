# Admin Console Telemetry Requirements

Status: requirements only. Do not add telemetry code for admin console routes until
ADR 0005 is revisited or a dedicated implementation task approves it.

## Purpose

Admin console telemetry must provide privacy-safe evidence for policy changes,
approval decisions, audit export events, and failed access attempts. It must reuse the
existing SIEM shape where possible: `schema_version="junas.siem.v1"` with audit or
security categories, hashes, counts, ids, and status fields instead of raw content.

## Common Event Fields

Every admin telemetry event must include:

| Field | Requirement |
|---|---|
| `schema_version` | `junas.siem.v1` until a documented schema revision exists. |
| `event_name` | Stable admin event name. |
| `category` | `audit` for admin actions, `security` for auth failures. |
| `outcome` | `started`, `succeeded`, `failed`, `denied`, `expired`, or `deleted`. |
| `tenant_id` | Credential-derived tenant id when authenticated. |
| `actor_id` | Authenticated subject or a hash of it when exported to SIEM. |
| `actor_roles` | Role names from validated API-key/JWT auth. |
| `auth_mode` | `api_key`, `jwt`, or trusted proxy mode that produced the JWT. |
| `request_id` | Backend request id. |
| `route_id` | Stable logical route or UI action id. |
| `ts` | UTC event timestamp. |

Never include raw prompt text, email body text, document text, matched spans, raw
reviewer rationale, recipient addresses, filenames, auth header values, API keys, JWTs,
local pairing tokens, reversible mappings, or raw audit ZIP bytes.

## Policy Change Events

Required event names:

- `policy_config_draft_created`
- `policy_config_draft_updated`
- `policy_config_validated`
- `policy_config_validation_failed`
- `policy_config_published`
- `policy_config_rolled_back`

Required details:

- draft id
- old policy id/version
- new policy id/version
- config hash
- validation status
- changed field names
- reason code when supplied
- error code and error count for validation failures

Policy telemetry must not include full TOML, secrets, internal domains beyond counts
or hashes, raw test input, or raw validation preview text.

## Approval Decision Events

Required event names:

- `approval_requested`
- `approval_assigned`
- `approval_reassigned`
- `approval_sla_breached`
- `approval_decision_recorded`
- `decision_recorded`

Required details:

- review id
- approval id when present
- finding id hashes or finding counts
- required reviewer roles
- required policy actor roles
- decision action
- reason code
- policy id/version
- surface and workflow
- SLA status and elapsed seconds

Approval telemetry must not include matched text, raw user content, raw reviewer
rationale, recipient addresses, filenames, or replacement originals.

## Audit Export Events

Required event names:

- `audit_export_requested`
- `audit_export_started`
- `audit_export_completed`
- `audit_export_verification_failed`
- `audit_pack_downloaded`
- `audit_export_expired`
- `audit_export_deleted`

Required details:

- review id
- export job id
- reason code
- retention class
- pack object id
- manifest hash
- pack HMAC presence
- journal verification status
- pack verification status
- failure reason code when applicable

Export telemetry must not include ZIP bytes, raw `findings.json`, raw `decisions.json`,
pack download URL secrets, matched text, raw rationale, recipients, filenames, or auth
tokens.

## Failed Access Events

Required event names:

- `admin_auth_missing`
- `admin_auth_invalid`
- `admin_role_denied`
- `admin_cross_tenant_denied`
- `admin_dev_header_rejected`
- `admin_local_token_rejected`

Required details:

- route id
- attempted method
- status code
- denial reason code
- auth mode when known
- role set when authenticated
- tenant id only when authenticated
- object type such as `review_id`, `approval_id`, policy draft id, cursor, or export
  job id, with the object value hashed before SIEM export

Failed access telemetry must hash or drop nested sensitive values using the same
sanitization rules as `test/test_siem_export.py`.

## Aggregations

The admin console may aggregate:

- policy publishes, rollbacks, and validation failures by tenant and policy version
- approval queue assignments, SLA breaches, decision actions, and completion latency
- audit exports requested, completed, verified, downloaded, expired, and failed
- failed access attempts by route id, role, auth mode, status code, and reason code

Aggregations must use counts, hashes, policy ids/versions, route ids, role names,
surface names, workflow names, and timestamps only.

## Required Tests Before Implementation

- Policy change telemetry omits full config, secrets, internal domains, and raw preview
  text.
- Approval telemetry omits matched text, raw reviewer rationale, and replacement
  originals.
- Audit export telemetry omits ZIP bytes, raw pack members, and download URL secrets.
- Failed access telemetry emits `admin_dev_header_rejected` for production
  `X-Reviewer-ID` attempts.
- Failed access telemetry emits `admin_local_token_rejected` for local daemon token
  attempts.
- Cross-tenant denials hash object ids before SIEM export.

## Related Documents

- `docs/adr/0005-admin-console-docs-only-until-validation.md`
- `docs/admin-console/requirements.md`
- `docs/admin-console/auth-requirements.md`
- `docs/admin-console/policy-config-ui.md`
- `docs/admin-console/reviewer-queue.md`
- `docs/admin-console/audit-export-ui.md`
- `docs/product/value-metrics.md`
- `docs/deployment-hardening.md#tenant-auth-and-rbac`
- `test/test_siem_export.py`
