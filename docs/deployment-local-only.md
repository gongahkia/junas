# Local-Only Deployment Boundary

Local-only deployment means `junas-local` runs on the user's machine and accepts
loopback or Unix-socket requests from local clients. It is for offline fallback, demos,
single-user review, and power users. It is not a hosted backend, tenant control plane,
enterprise endpoint agent, or SIEM-managed service.

The packaged entrypoint sets these local defaults unless the operator overrides them:

```sh
JUNAS_HOST=127.0.0.1
JUNAS_PORT=8765
PIPELINE_LAYERS=""
JUNAS_PUBLIC_EVIDENCE_ENABLED=0
JUNAS_LLM_ENABLED=0
JUNAS_REVIEW_PERSIST=1
JUNAS_LOCAL_DAEMON_ACL_ENABLED=1
```

See [local daemon security](security/local-daemon.md) for pairing, token storage,
origin checks, and uninstall commands.

## What Works Locally

| Capability | Local-only behavior |
|---|---|
| Deterministic `/review` | Runs the local deterministic engine and returns findings, policy decision fields, actions, scores, and degraded-mode state. |
| Safe rewrite/redaction | `/safe-rewrite`, `/redact`, `/redact-pii`, `/anonymize`, and `/documents/scrub` work without server-side optional providers. |
| Pseudonymization and reidentify | Works only when local persistence secrets are configured; otherwise use inline mapping responses or treat round-trip reidentify as unavailable. |
| Browser, Word, Outlook taskpane, desktop watcher | Can call `http://127.0.0.1:8765` from the same machine when the adapter supports local daemon mode and has a valid local token. |
| Local audit evidence | Local journal/audit files exist only on that machine and only when persistence keys are configured. |

Minimum local persistence setup:

```sh
export JUNAS_JOURNAL_KEY='local-hmac-key'
export JUNAS_MAPPING_STORE_KEY='local-fernet-key'
export JUNAS_SUBJECT_INDEX_KEY='local-subject-index-key'
export JUNAS_ALLOW_PLAINTEXT_MAPPINGS=0
```

Use FileVault, BitLocker, LUKS, or equivalent host encryption for the local state
directory. Use `JUNAS_ALLOW_PLAINTEXT_MAPPINGS=1` only for disposable development.

## Unavailable Without Server-Side Optional Layers

| Server-side or managed layer | Local-only result |
|---|---|
| Public evidence retrieval | Unavailable in local-only posture. `PIPELINE_LAYERS=""` and `JUNAS_PUBLIC_EVIDENCE_ENABLED=0` mean no external public-source lookup or privacy-ledger evidence for public evidence. |
| Remote LLM adjudication | Unavailable in local-only posture. `JUNAS_LLM_ENABLED=0` means no LLM adjudicator, LLM helper, defined-term helper, or LLM coverage-audit layer. |
| Tenant auth and RBAC | No shared tenant identity plane, JWT/JWKS validation, API-key registry, mTLS principal mapping, or cross-user role enforcement. Local daemon ACL uses same-user local tokens only. |
| Central review queue | No shared reviewer queue, approval SLA, or cross-user approval workflow. Request-approval events can only be local evidence unless a hosted backend owns the workflow. |
| SIEM and central telemetry | No tenant-wide SIEM export, Prometheus alerting, product-value dashboard, or adapter telemetry collection unless the operator separately ships local metrics/events. |
| Tenant-wide audit export | No central audit-pack source, retention manifest enforcement, legal-hold workflow, or cross-device journal replay. Local audit exports are machine-local. |
| DMS/server-side hooks | No remote DMS check-in hook or service-to-service direct API endpoint for other systems; the daemon binds loopback by default. |
| Fleet policy and enforcement | No MDM, EDR, endpoint DLP, browser policy, or proof that every local app workflow was reviewed. |

If an operator enables public evidence, remote LLMs, tenant auth, central SIEM, or
server-side workflow hooks, the deployment is no longer local-only. Follow
[deployment hardening](deployment-hardening.md) and
[managed LLM deployment](deployment-managed-llm.md) for those modes.

## Adapter Boundary

Local-only adapters activate review on that machine only:

- Browser extension: local daemon mode can review configured GenAI pages, but browser
  profiles without the extension, denied site access, mobile apps, and unrecognized web
  UIs are out of scope.
- Outlook add-in: a local endpoint can support dev or tightly scoped local pilots, but
  Microsoft 365 admin deployment, Smart Alerts QA, and centralized telemetry belong to a
  hosted or customer-managed rollout.
- Word taskpane: local review is author-side proofing; it does not block save, print,
  export, email-send, DMS upload, or repository check-in.
- Desktop watcher: file/folder/clipboard review is explicit opt-in and not enterprise
  endpoint enforcement.

## Decision Rule

Use local-only when the user needs offline deterministic review or a same-machine
adapter bridge. Use hosted or customer-managed server deployment when the requirement
includes tenant-wide auth, reviewers, SIEM, retention evidence, DMS/server hooks,
public evidence, remote LLM adjudication, or measured pilot telemetry.
