# Developer FAQ

Use the live OpenAPI schema as the contract source, then use this page for endpoint choice.

## Which Endpoint Should New Integrations Call First?

Call `POST /review` first for new adapters, gateways, DMS hooks, and backend integrations.

`/review` returns deterministic findings, risk scores, `policy_decision`, `action_catalog`, `request_id`, `review_id`, `review_expires_at`, degraded-mode context, and timing fields without rewriting the input text.

Use `/review` when the caller needs to decide whether to allow, warn, block, request approval, safe rewrite, redact, hold, or cite a public source before a workflow completes.

## When Should I Use `/pseudonymize`?

Use `POST /pseudonymize` when the caller needs deterministic placeholders plus a mapping that can restore the original text later through `POST /reidentify`.

Mappings are sensitive. Persist them only when the deployment has tenant auth, mapping-store key management, retention, subject-erasure, and backup controls configured.

## When Should I Use `/anonymize`?

Use `POST /anonymize` when the caller wants irreversible placeholder-only output with no returned or persisted mapping.

`/anonymize` is not proof of statistical anonymization. It is a deterministic placeholder transformation over detected spans; residual context risk remains the caller's responsibility.

## When Should I Use `/redact`?

Use `POST /redact` when the caller wants opaque markers and no original matched text in the redaction response.

Use `POST /redact-pii` instead when policy says to remove PII while keeping MNPI passages visible and flagged for later review.

Use `POST /safe-rewrite` when policy allows deterministic span replacements and the adapter needs replacement audit fields such as `rewritten_text`, `replacements`, `skipped_findings`, and `rewrite_policy`.

## When Should I Use `/reidentify`?

Use `POST /reidentify` only after `/pseudonymize`, with either a caller-supplied mapping or a persisted pseudonymization `document_hash`.

`/reidentify` is tenant/auth scoped when persisted mappings are used. Do not treat `/anonymize`, `/redact`, `/redact-pii`, or `/safe-rewrite` output as reidentifiable.

## When Should I Use `/documents/scrub`?

Use `POST /documents/scrub` to remove supported metadata from DOCX, PDF, JPEG, and PNG payloads before sharing or storing documents.

`/documents/scrub` is not a replacement for `/review`: it handles container metadata, while `/review` handles text/content findings and policy decisions. For document-sharing workflows, run `/review` for policy, then `/documents/scrub` when metadata removal is required.

## When Should I Use `/classify`?

Use `POST /classify` or `POST /classify/batch` only for legacy clients that still consume the old classifier shape.

New integrations should use `/review`, because `/review` returns policy decisions, action catalog, review expiry, workflow context handling, degraded modes, and audit-ready ids. `/classify` remains a compatibility shim over the deterministic review engine.

## Endpoint Choice Table

| Need | Endpoint |
|---|---|
| Pre-send or pre-share decision without rewriting | `POST /review` |
| Reversible placeholders and later restore | `POST /pseudonymize` then `POST /reidentify` |
| Irreversible placeholder output | `POST /anonymize` |
| Opaque text markers with no matched text in response | `POST /redact` |
| PII-only replacement while MNPI remains visible | `POST /redact-pii` |
| Policy-approved deterministic replacements | `POST /safe-rewrite` |
| High-severity MNPI hold text | `POST /hold-until-public` |
| Audit-grade public-source citation | `POST /cite-public-source` |
| Reviewer approval workflow | `POST /request-approval` then `POST /review/{review_id}/decision` |
| Supported document/image metadata removal | `POST /documents/scrub` |
| Legacy classifier compatibility | `POST /classify` or `POST /classify/batch` |

## References

- [`docs/schema.md`](../schema.md)
- [`docs/api/versioning.md`](../api/versioning.md)
- [`docs/policy/decision-contract.md`](../policy/decision-contract.md)
- [`docs/api/python_client.md`](../api/python_client.md)
