# API Versioning

Kaypoh v0.1 exposes root endpoints such as `/review`, `/pseudonymize`, `/anonymize`, `/redact`, `/redact-pii`, `/reidentify`, `/documents/scrub`, and `/classify`. The OpenAPI schema is the contract source for generated clients.

## `/v1` Compatibility Rules

- `/v1` routes are not exposed yet.
- Until `/v1` aliases exist, adapter clients must pin to the root endpoint set and the generated OpenAPI artifact used during certification.
- A future `/v1/review` alias must preserve the same response semantics as `/review` for a full compatibility window before any root endpoint removal is considered.
- Additive response fields are allowed when existing fields keep their type and meaning.
- Removing fields, changing enum values, changing default policy semantics, or changing auth headers requires a versioned route or explicit migration note.

## `/classify` Deprecation Policy

`/classify` and `/classify/batch` are compatibility wrappers over the deterministic review engine. They remain available for existing classifier consumers, but new integrations should use `/review` so they receive findings, policy decisions, action catalog, degraded-mode context, and audit-ready review ids.

Deprecation stages:

1. `supported`: `/classify` stays in OpenAPI and tests.
2. `migration-noted`: docs and generated examples mark `/review` as preferred.
3. `warning`: responses or headers may include a deprecation warning while behavior remains compatible.
4. `removal-candidate`: only after a versioned route exists and old clients have a documented migration path.

## Adapter Schema Pinning

Adapters should pin:

- OpenAPI snapshot or generated client version.
- Endpoint path and method.
- Required request fields.
- Expected `policy_decision.decision` enum values.
- `action_catalog` values they know how to display.
- Tenant policy id/version when policy behavior is part of certification.

Adapters should reject or degrade safely when:

- The backend omits `policy_decision`.
- The decision enum is unknown.
- Required actions contain an unsupported action.
- The pinned policy id/version is not accepted by tenant deployment rules.
- The response lacks `review_id` for a flow that needs retry, approval, or audit.
