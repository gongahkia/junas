# Security Policy

Report security-sensitive issues by email: angryapplegravy@gmail.com.

Do not open a public GitHub issue for vulnerabilities, exposed secrets, tenant-isolation failures, auth bypasses, raw-content logging, adapter storage leaks, package-signing problems, or dependency-chain concerns.

## Scope

In scope:

- Backend auth, tenant isolation, policy bypass, audit/journal integrity, and unsafe default configuration.
- Raw prompt, email, document, matched text, mapping, auth token, or secret exposure through logs, telemetry, SIEM events, adapter storage, screenshots, support artifacts, or demo fixtures.
- Browser, Office, desktop watcher, DMS, direct API, packaging, dependency, or deployment docs that could cause unsafe handling of sensitive data.
- Public demo behavior that persists input, requires secrets, enables remote providers unexpectedly, or exceeds documented deterministic-only limits.

Out of scope:

- Legal advice, legal-accuracy disputes, procurement claims, or general compliance opinions.
- Detector false positives/false negatives without a security impact; use ordinary issues and synthetic examples.
- Feature requests, install support, performance tuning, or docs wording that does not affect sensitive-data handling.
- Reports requiring real customer data, live credentials, or third-party accounts you do not control.

## Reporting

Include:

- Affected commit, version, route, adapter, deployment mode, or artifact.
- Minimal reproduction steps using synthetic data only.
- Expected impact, affected data class, and whether the issue is already public.
- Any safe patch or mitigation notes.

Do not include real customer text, live personal data, production secrets, tokens, private keys, or exploit code beyond what is needed to demonstrate impact.

## Response Expectations

This is a FOSS project without a paid security desk, bug bounty, or guaranteed SLA. Reports are reviewed best-effort. I will prioritize issues that expose sensitive data, bypass auth or tenant boundaries, weaken deterministic review controls, or make documented safe deployment guidance materially wrong.

Please allow time for triage and a fix before public disclosure. If the report is accepted, the public fix should describe impact and mitigation without publishing sensitive reporter data or live exploit material.
