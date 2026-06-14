# Policy Examples

These examples are starting profiles. Operators must version and validate tenant policy before production rollout.

## Law Firm Strict

```toml
[policy]
policy_id = "law-firm-strict"
policy_version = "2026-06-14-law-firm-strict"
internal_domains = ["firm.example"]
warn_on_low_risk_findings = true
high_pii_required_actions = ["redact_pii", "request_approval", "safe_rewrite"]
high_mnpi_external_actions = ["hold_until_public", "request_approval"]
public_mnpi_recommended_actions = ["cite_public_source", "request_approval"]
reviewer_override_roles = ["legal_reviewer", "compliance_admin"]
medium_risk_recommended_actions = ["proceed_with_warning", "request_approval"]
low_risk_recommended_actions = ["proceed_with_warning"]
```

## Enterprise Soft-warning

```toml
[policy]
policy_id = "enterprise-soft-warning"
policy_version = "2026-06-14-enterprise-soft"
internal_domains = ["corp.example"]
warn_on_low_risk_findings = true
high_pii_required_actions = ["safe_rewrite", "request_approval"]
high_mnpi_external_actions = ["hold_until_public", "request_approval"]
public_mnpi_recommended_actions = ["cite_public_source", "proceed_with_warning"]
reviewer_override_roles = ["compliance_admin"]
medium_risk_recommended_actions = ["proceed_with_warning"]
low_risk_recommended_actions = ["proceed_with_warning"]
```

## Offline Local-only

```toml
[policy]
policy_id = "offline-local-only"
policy_version = "2026-06-14-offline-local"
internal_domains = []
warn_on_low_risk_findings = true
degraded_block_action = "retry_review"
high_pii_required_actions = ["redact_pii", "safe_rewrite"]
high_mnpi_external_actions = ["hold_until_public"]
public_mnpi_recommended_actions = ["proceed_with_warning"]
reviewer_override_roles = ["legal_reviewer"]
medium_risk_recommended_actions = ["proceed_with_warning"]
low_risk_recommended_actions = ["proceed_with_warning"]
```

## Audit-grade MNPI

```toml
[policy]
policy_id = "audit-grade-mnpi"
policy_version = "2026-06-14-audit-mnpi"
internal_domains = ["bank.example"]
warn_on_low_risk_findings = true
high_pii_required_actions = ["redact_pii", "request_approval", "safe_rewrite"]
high_mnpi_external_actions = ["hold_until_public", "request_approval"]
public_mnpi_recommended_actions = ["cite_public_source", "request_approval"]
reviewer_override_roles = ["legal_reviewer", "compliance_admin"]
medium_risk_recommended_actions = ["proceed_with_warning", "request_approval"]
low_risk_recommended_actions = ["proceed_with_warning"]
```

## GenAI Prompt Review

```toml
[policy]
policy_id = "genai-prompt-review"
policy_version = "2026-06-14-genai"
internal_domains = ["corp.example"]
warn_on_low_risk_findings = true
high_pii_required_actions = ["redact_pii", "safe_rewrite", "request_approval"]
high_mnpi_external_actions = ["hold_until_public", "request_approval"]
public_mnpi_recommended_actions = ["cite_public_source", "proceed_with_warning"]
reviewer_override_roles = ["compliance_admin"]
medium_risk_recommended_actions = ["safe_rewrite", "proceed_with_warning"]
low_risk_recommended_actions = ["proceed_with_warning"]
```
