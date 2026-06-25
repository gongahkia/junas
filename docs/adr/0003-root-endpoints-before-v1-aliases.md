# ADR 0003: Root Endpoints Before `/v1` Aliases

Status: Accepted

Date: 2026-06-14

## Context

Kaypoh v0.1 already exposes root endpoints such as `/review`, `/pseudonymize`, `/anonymize`, `/redact`, `/reidentify`, `/documents/scrub`, and `/classify`. The policy decision contract is still being completed, and adapters are not yet certified against a frozen versioned route.

Adding `/v1/review` before the policy contract, idempotency behavior, review expiry, OpenAPI examples, and adapter certification are complete would create two public paths with the same immature semantics.

## Decision

Keep root endpoints for v0.1 and do not add `/v1/review` aliases yet. `/v1` aliases should be added only after the P0 policy contract and adapter certification checklist are stable enough to support version pinning.

## Consequences

- Existing examples and generated clients continue using root endpoints.
- Adapter docs must pin the OpenAPI artifact and root path for v0.1.
- `/v1/review` implementation remains gated on a later ADR or explicit versioning task.
- When `/v1` is introduced, root endpoints must remain available for a compatibility window.

## Related Documents

- `docs/api/versioning.md`
- `docs/policy/decision-contract.md`
- `docs/roadmap.md`
