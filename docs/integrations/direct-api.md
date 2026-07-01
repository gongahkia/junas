# Direct API Integration

Source: `src/junas/backend/`, `src/junas/client.py`, `docs/api/`

Maturity: `core`

Direct HTTP/OpenAPI integration is the baseline path for customers that do not want a UI adapter. The caller owns its workflow UI or service logic; Junas owns review validation, policy decisions, deterministic findings, rewrite actions, approval journaling, and audit-safe response metadata.

## When To Use

- API gateway, proxy, or service-side pre-send checks.
- DMS, workflow engine, or collaboration platform hooks before a dedicated adapter exists.
- Backend jobs that need deterministic review, rewrite, approval, or audit evidence without browser, Office, or desktop runtime code.

## Request Contract

Start the backend:

```sh
./scripts/launch/run_backend_only.sh
```

Call `POST /review` first. Provide either `text` or `document_base64`, then include workflow context when known:

```json
{
  "text": "Please send the draft deck to Tan S1234567D.",
  "source_jurisdiction": "SG",
  "destination_jurisdiction": "US",
  "document_type": "email",
  "surface": "api",
  "workflow": "api_review",
  "actor_role": "service_account",
  "recipient_domains": ["example.com"],
  "external_destination": true,
  "requested_action": "send"
}
```

Use `surface="api"` for direct service calls. Use a more specific surface only when the caller is acting on behalf of that workflow, for example `surface="dms"` with `workflow="document_upload"`.

## Auth And Tenant Scope

Production callers should authenticate with the configured API key registry or JWT mode. Tenant identity comes from validated credentials; caller-supplied tenant headers are ignored. See [`docs/admin-security.md`](../admin-security.md).

Do not log raw request bodies, matched text, auth headers, or reversible mapping values. Use `request_id`, `policy_id`, `policy_version`, surface, workflow, decision, and timing fields for support and SIEM correlation.

## Decision Handling

Treat `policy_decision` as the source of truth:

- `allow`: complete the workflow.
- `warn`: show or record warning behavior per tenant policy.
- `block`: stop completion.
- `approval_required`: preserve `review_id` and call `/request-approval` when the caller can route review.
- `rewrite_required`: offer only actions in `action_catalog` and prioritize `required_actions`.

`send_allowed` remains a compatibility shortcut, but new integrations should read `policy_decision.send_allowed`, `required_actions`, `recommended_actions`, and `review_expires_at`.

## Follow-On Actions

- `/safe-rewrite`: deterministic policy-approved rewrite.
- `/redact-pii`: irreversible PII replacement while MNPI remains visible and flagged.
- `/pseudonymize`: reversible placeholders with mapping support.
- `/anonymize`: irreversible placeholders with no retained mapping.
- `/request-approval`: pending reviewer approval journal entry for a prior `review_id`.
- `/documents/scrub`: metadata scrub for supported document payloads.

## Idempotency And Retry

Use an adapter-defined `Idempotency-Key` for retries. Junas v0.1 returns `request_id` and `X-Request-ID`, but repeated `POST /review` calls are not deduplicated server-side. Build keys without raw content; use a keyed content HMAC plus surface, workflow, destination, attachment fingerprint, and attempt epoch. See [`docs/api/idempotency.md`](../api/idempotency.md).

Retry transport timeouts only when user intent and content are unchanged. Do not automatically retry validation, auth, or policy-version failures.

## References

- [`docs/api/README.md`](../api/README.md)
- [`docs/api/python_client.md`](../api/python_client.md)
- [`docs/policy/decision-contract.md`](../policy/decision-contract.md)
- [`docs/api/versioning.md`](../api/versioning.md)
