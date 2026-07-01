# Audit Export UI Requirements

Status: requirements only. Do not add audit export endpoints or UI code until ADR
0005 is revisited or a dedicated implementation task approves them.

## Purpose

The audit export UI lets authorized users request, verify, and retrieve review-session
audit packs using the existing audit tooling:

- `scripts/export_audit_pack.py`
- `scripts/verify_audit_pack.py`
- `scripts/verify_journal.py`

The UI must not become a parallel audit format. It should surface job state,
verification results, retention metadata, and download controls while preserving the
backend journal and audit-pack scripts as the source of truth.

## Roles

| Role | Access |
|---|---|
| `admin` | Request exports, view status, download packs, retry failed verification, and view audit events. |
| `auditor` | Request exports, view status, download packs, and view audit events. |
| `checker` | View export status and verification result when tenant policy allows review-session reads. |
| `reviewer` / `maker` | No audit export access by default. |

Production access must reject local-dev-only reviewer headers, local daemon pairing
tokens, caller-supplied tenant ids, and any role inferred from request body fields.

## Export Request

Required request fields:

| Field | Requirement |
|---|---|
| `review_id` | Required. Must be tenant-scoped from authenticated credentials. |
| `reason_code` | Required. Enum such as `regulator_request`, `customer_audit`, `internal_review`, or `support_case`. |
| `include_defensibility` | Optional boolean matching `--include-defensibility`. Default false. |
| `retention_class` | Required. Must map to the retention manifest. |
| `destination` | Required. Server-controlled export target or object-store bucket id, not a caller-supplied file path. |

The implementation must not shell-interpolate `review_id`, output paths, or user input.
If the UI wraps CLI scripts, it must pass arguments as argv values and use a
server-chosen output path.

## Job States

Required states:

- `queued`
- `running_export`
- `running_pack_verification`
- `running_journal_verification`
- `exported`
- `verification_failed`
- `failed`
- `expired`
- `deleted`

The status view may show `review_id`, request id, export job id, requested by, created
time, completed time, retention class, pack object id, manifest hash, pack HMAC
presence, journal chain status, findings count, decisions count, and verification
errors. It must not show raw prompt text, email body text, document text, matched
spans, reviewer rationale, recipient addresses, filenames, auth headers, reversible
mappings, local pairing tokens, or raw pack contents.

## Verification Flow

For each successful export job:

1. Run `scripts/export_audit_pack.py <review_id> --output <server-chosen-path>`.
2. Run `scripts/verify_audit_pack.py <server-chosen-path>`.
3. Run `scripts/verify_journal.py` for the tenant journal context.
4. Store verification status, verification timestamp, manifest hash, pack object id,
   pack size, and verification errors.
5. Mark the job `exported` only when pack verification succeeds and journal
   verification returns valid or the deployment explicitly records a documented
   warning state.

The UI must distinguish `pack_hmac mismatch`, `journal chain inconsistent`, missing
pack files, missing `review_started`, and authorization failures.

## Pack Sensitivity

Audit packs are sensitive artifacts. `findings.json` may include finding details from
the review journal, and deployments must treat the full ZIP as controlled evidence, not
as a raw-free metrics export. The UI list and status views should expose only manifest
metadata, counts, hashes, and verification result. Download controls must require
audit/admin role checks and should show a sensitive evidence warning before retrieval.

## Audit Events

Required event names:

- `audit_export_requested`
- `audit_export_started`
- `audit_export_completed`
- `audit_export_verification_failed`
- `audit_pack_downloaded`
- `audit_export_expired`
- `audit_export_deleted`

Each event must include tenant id, actor id, actor role, request id, review id, export
job id, reason code, retention class, status, pack object id when available, manifest
hash, pack HMAC presence, journal verification status, timestamp, and error code when
applicable. Events must not include raw reviewed content, matched text, raw reviewer
rationale, recipients, filenames, auth headers, mapping values, local pairing tokens,
or raw ZIP bytes.

## Required UI States

- Export request form with review id, reason code, retention class, and
  `include_defensibility`.
- Export job list with status, requester, timestamps, verification state, and expiry.
- Verification detail view showing `verify_audit_pack.py` and `verify_journal.py`
  results.
- Download view gated by audit/admin role and sensitive evidence acknowledgement.
- Retry action for failed verification that does not create a second completed export
  without linking both job ids.
- Expiry/deletion state tied to `docs/security/data-retention.md`.

## Non-Goals

- No new audit pack format before the script format changes.
- No raw-content preview in the admin console.
- No export path chosen by the browser client.
- No download for `reviewer` or `maker` roles.
- No SIEM event containing raw pack payloads, matched text, rationale text, recipients,
  filenames, mappings, or auth tokens.

## Related Documents

- `docs/adr/0005-admin-console-docs-only-until-validation.md`
- `docs/admin-console/requirements.md`
- `docs/admin-console/review-session-list-endpoint.md`
- `docs/security/data-retention.md`
- `docs/policy/journal-replay.md`
- `scripts/export_audit_pack.py`
- `scripts/verify_audit_pack.py`
- `scripts/verify_journal.py`
