# Policy Config UI Requirements

Status: requirements only. Do not add policy admin endpoints or UI code until ADR
0005 is revisited or a dedicated implementation task approves them.

## Purpose

The policy config UI lets a tenant compliance admin manage versioned Junas policy
profiles without editing production TOML by hand. It must preserve backend ownership
of policy validation, policy decisions, tenant isolation, and audit evidence.

Scope: versioned Junas policy profiles. UI actions: Create drafts, validate drafts,
publish validated drafts, and rollback to prior versions.

## Roles

| Role | Access |
|---|---|
| Compliance admin / `admin` | Create drafts, validate drafts, publish validated drafts, rollback to prior versions, and view history. |
| Auditor / `auditor` | Read active policy metadata, history, validation results, and audit events. No edits. |
| Checker / `checker` | Read active policy metadata and validation results when assigned to review policy changes. No publish unless tenant policy grants it. |
| Legal reviewer / `reviewer` | No policy config UI access by default. |
| Maker / `maker` | No policy config UI access by default. |

Production access must reject local-dev-only reviewer headers, caller-supplied tenant
ids, local daemon pairing tokens, and any role inferred from request body fields.
Production access must reject caller-supplied tenant ids.

## Draft Flow

- Create a draft from the active tenant policy, a prior version, or a documented
  example from `docs/policy/examples.md`.
- Draft state must be tenant-scoped from authenticated credentials.
- Drafts must carry `draft_id`, `base_policy_id`, `base_policy_version`,
  `candidate_policy_id`, `candidate_policy_version`, `status`, `created_by`,
  `created_at`, `updated_at`, `config_hash`, and `etag`.
- Draft edits must use structured fields matching `docs/policy/schema.md`; raw TOML
  upload may exist only as an import path that immediately parses into structured
  fields and rejects unknown keys.
- Required fields must include `policy_id`, `policy_version`, `internal_domains`,
  `high_pii_required_actions`, `high_mnpi_external_actions`,
  `public_mnpi_recommended_actions`, `medium_risk_recommended_actions`, and
  `low_risk_recommended_actions`.
- Draft save must be optimistic-concurrency guarded by `etag`.
- Draft storage must not include raw reviewed text, matched spans, reversible
  mappings, auth headers, local pairing tokens, or reviewer rationale.

## Validate Flow

- Validation must call the same backend rules as `junas.policy.load_policy_profile`
  with production validation enabled for production tenants.
- Validation must fail fast on invalid TOML shape, unknown keys, unsupported actions,
  empty required action arrays, invalid domains, missing production `policy_version`,
  and missing tenant override `policy_version`.
- Validation output must include `validation_status`, `errors`, `warnings`,
  `policy_id`, `policy_version`, `config_hash`, `validated_at`, and `validated_by`.
- Validation must not activate the policy.
- The UI may show a policy decision preview only with synthetic examples or explicit
  operator-supplied test text that is handled as a normal `/review` request. It must
  not persist preview raw text in the policy draft, policy history, logs, telemetry,
  or SIEM events.
- A failed validation must preserve the draft for correction and record a
  `policy_config_validation_failed` audit event without raw config secrets.

## Publish Flow

- Only a validated draft may be published.
- Publish must require a human reason, the current draft `etag`, and the expected
  active `policy_id` plus `policy_version`.
- Publish requires the expected active `policy_id` plus `policy_version`.
- Publish must atomically promote the candidate policy for the credential-derived
  tenant and make the new `policy_id` and `policy_version` visible to `/review`
  policy decisions.
- Publish must preserve the previous active version for rollback and audit lookup.
- Publish must not delete draft history or validation results.
- The UI must show that adapters may need to refresh cached policy metadata, but the
  backend remains the source of truth for active policy behavior.

## Rollback Flow

- Rollback must select a prior published version by immutable version id or
  `policy_id` plus `policy_version`.
- Rollback must require a human reason and record the source version and target prior
  version.
- Rollback creates a new active policy event pointing to the prior config; it must not
  rewrite, delete, or reorder existing history.
- Rollback must be blocked if the target version fails current production validation.
- Rollback must emit the same adapter-visible active `policy_id` and `policy_version`
  semantics as publish.

## Audit Journal Events

Required event names:

- `policy_config_draft_created`
- `policy_config_draft_updated`
- `policy_config_validated`
- `policy_config_validation_failed`
- `policy_config_published`
- `policy_config_rolled_back`

Each event must include tenant id, actor id, actor role, request id, event timestamp,
draft id when applicable, old policy id/version, new policy id/version, config hash,
status, reason when supplied, and a diff summary with changed field names. Events must
not include raw reviewed content, matched text, reversible mappings, auth headers,
local pairing tokens, or unredacted secrets.

SIEM export may include event name, tenant id, actor id, status, policy id/version,
config hash, changed field names, and request id. Full draft config export belongs in
an admin audit pack only when explicitly requested and scrubbed for secrets.

## Required UI States

- Active policy summary with `policy_id`, `policy_version`, config hash, published
  time, publisher, and last validation status.
- Draft list with status: `draft`, `validation_failed`, `validated`, `published`,
  `rolled_back`, or `abandoned`.
- Field-level validation errors tied to schema fields.
- Publish confirmation that names the tenant, old version, new version, and reason.
- Rollback confirmation that names the tenant, current version, target prior version,
  and reason.
- Read-only audit history with event filters and no raw config secrets.

## Non-Goals

- No policy engine in frontend code.
- No production policy activation from unvalidated config.
- No caller-supplied tenant selector.
- No local-dev-only headers in production.
- No raw reviewed content or matched spans in drafts, validation output, audit events,
  telemetry, local storage, or SIEM export.

## Related Documents

- `docs/adr/0005-admin-console-docs-only-until-validation.md`
- `docs/admin-console/requirements.md`
- `docs/policy/schema.md`
- `docs/policy/examples.md`
- `docs/security/api-inventory.md`
