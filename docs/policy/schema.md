# Policy Schema

Policy config is TOML loaded through `junas.policy.load_policy_profile`. The default profile is used when no file is supplied.

## TOML Shape

```toml
[policy]
policy_id = "default"
policy_version = "2026-06-14"
internal_domains = ["example.com"]
warn_on_low_risk_findings = true
degraded_block_action = "retry_review"
high_pii_required_actions = ["redact_pii", "request_approval", "safe_rewrite"]
high_mnpi_external_actions = ["hold_until_public", "request_approval"]
public_mnpi_recommended_actions = ["cite_public_source", "proceed_with_warning"]
reviewer_override_roles = ["legal_reviewer", "compliance_admin"]
medium_risk_recommended_actions = ["proceed_with_warning"]
low_risk_recommended_actions = ["proceed_with_warning"]

[tenants.tenant-a]
policy_id = "tenant-a-strict"
policy_version = "2026-06-14-tenant-a"
internal_domains = ["tenant-a.example"]
```

Tenant tables override `[policy]` keys for the matching tenant only. In production mode, `[policy]` and each active tenant override must declare an explicit `policy_version`.

## Config Fields

| Field | Type | Meaning |
|---|---|---|
| `policy_id` | string | Stable profile id returned in `policy_decision.policy_id`. |
| `policy_version` | string | Explicit ruleset version returned in `policy_decision.policy_version`. |
| `internal_domains` | string array | Domains treated as internal for recipient-domain policy. Subdomains match. |
| `warn_on_low_risk_findings` | boolean | Converts otherwise-allow low/medium finding responses to `warn`. |
| `degraded_block_action` | action | Required action for degraded review when caller set `degraded_policy=block_send`. |
| `high_pii_required_actions` | action array | Required actions for high-severity PII without reviewer approval. |
| `high_mnpi_external_actions` | action array | Required actions for high-severity MNPI without public evidence or reviewer approval. |
| `public_mnpi_recommended_actions` | action array | Recommended actions when high-severity MNPI has public evidence. |
| `reviewer_override_roles` | string array | Roles allowed to route high-severity PII to approval instead of rewrite. |
| `medium_risk_recommended_actions` | action array | Recommended actions for medium-risk findings and external/cross-border context. |
| `low_risk_recommended_actions` | action array | Recommended actions for low-risk findings. |

Allowed actions: `retry_review`, `redact_pii`, `safe_rewrite`, `request_approval`, `hold_until_public`, `cite_public_source`, `proceed_with_warning`.

## Decision Precedence

Policy decisions are ranked:

1. `block`
2. `approval_required`
3. `rewrite_required`
4. `warn`
5. `allow`

The highest-ranked matching rule wins. Required actions, recommended actions, blocking finding ids, and policy reasons are sorted before response serialization for deterministic adapter behavior.

## Severity Thresholds

- No findings and no risky context: `allow`.
- Low or medium findings: `warn` when `warn_on_low_risk_findings=true`.
- High PII: `rewrite_required`, unless reviewer approval exists or the actor role routes the item to approval.
- High MNPI: `block`, unless public evidence or reviewer approval exists.
- Degraded coverage with `degraded_policy=block_send`: `block`.

## Recipient-domain Rules

`external_destination=true` marks the workflow external. When `external_destination` is absent, recipient domains are compared to `internal_domains`; unmatched domains trigger a `warn` reason. Empty domain lists are allowed and do not imply external delivery.

## Role Rules

Roles come from trusted adapter/API auth context, not from user-editable text. `legal_reviewer` and `compliance_admin` can route high-severity PII to `approval_required`. Role alone does not unblock high-severity MNPI; MNPI still needs public evidence or recorded reviewer approval.

## Failure Modes

- Invalid TOML raises `PolicyConfigError` before profile creation.
- Unknown sections or keys raise `PolicyConfigError`.
- Unsupported actions raise `PolicyConfigError`.
- Production config without explicit policy version raises `PolicyConfigError`.
- Production tenant override without explicit tenant policy version raises `PolicyConfigError`.
- Missing workflow context is allowed; high-risk findings still evaluate conservatively.
