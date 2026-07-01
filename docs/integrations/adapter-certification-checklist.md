# Adapter Certification Checklist

Status: normative for promoting adapter support claims. Passing this checklist does not make an adapter a new trust boundary; the FastAPI backend remains the policy and audit source of truth.

Use with `docs/integrations/maturity-matrix.md`, `docs/integrations/adapter-protocol.md`, `docs/integrations/auth.md`, `docs/integrations/privacy.md`, `docs/integrations/telemetry.md`, and `docs/integrations/failure-semantics.md`.

## Evidence Header

Every certification record must capture:

- adapter name, source path, runtime target, and maturity label
- backend commit, adapter commit, policy id, and policy version
- tenant auth mode and deployment mode
- tester, date, environment, OS/browser/client version, and exact manifest/config version
- links to screenshots, logs, fixture output, and test command output

Do not include raw prompts, email bodies, document text, matched text, recipient addresses, filenames, auth headers, local tokens, JWTs, API keys, reversible mappings, or reviewer free text in certification artifacts.

## Required Checklist

| Gate | Required evidence | Fails certification when |
|---|---|---|
| Install | Documented install path, package or manifest hash, versioned config, admin assignment scope, and rollback path. | Install requires undocumented manual edits, broad unscoped permissions, or unsupported client/runtime versions. |
| Auth | Backend auth mode works with tenant identity derived from credentials; local pairing or API/JWT secrets are not logged. | Adapter trusts caller-supplied tenant ids, stores auth headers, or silently falls back to unauthenticated review. |
| Review | Adapter calls `POST /review` with correct `surface`, `workflow`, `actor_role`, destination context, document context, and idempotency behavior. | Review omits required workflow context, sends raw content outside the HTTPS/body boundary, or reuses reviews after content/context changes. |
| Policy decision | Adapter treats `policy_decision` as source of truth and maps allow, warn, block, `approval_required`, and `rewrite_required` to documented UI/completion behavior. | Adapter reads only top-level `send_allowed`, ignores required actions, or allows completion after malformed/missing policy decisions. |
| Rewrite | Adapter offers only actions present in `action_catalog`, preserves original review ids/finding ids, and never rewrites spans outside allowed policy actions. | Adapter applies local rewrites that bypass backend policy or persists reversible mappings without explicit pseudonymization. |
| Approval | Adapter can request approval with `/request-approval`, stops completion while pending, and retries only after authorized backend reviewer decision satisfies policy. | Adapter treats itself as an approval authority or completes after stale approval, changed content, changed recipient, changed matter, or changed policy version. |
| Telemetry | Adapter emits privacy-safe started, decision, user-action, timeout/failure, and completion events using the correct schema/version. | Telemetry contains raw content, recipient addresses, attachment filenames, auth material, raw idempotency keys, or endpoint URLs with secrets. |
| Privacy | Storage, logs, console output, screenshots, local storage, extension storage, Office runtime storage, and SIEM output are checked for prohibited fields. | Raw prompt/email/document text, matched text, rewritten text, replacement text, mapping values, or sensitive reviewer rationale persists outside documented boundaries. |
| Failure | Timeout, backend unavailable, auth failure, malformed response, degraded review, selector/context failure, and platform bypass paths match failure semantics. | Adapter silently allows completion when no trustworthy backend policy decision was evaluated. |
| Uninstall | Removal path disables runtime hooks, revokes tokens/secrets, clears adapter storage, removes scheduled/background processes, and documents residual backend audit records. | Uninstall leaves active send/submit hooks, valid stale tokens, unmanaged background agents, or undocumented user data. |

## Minimum Command Evidence

Each adapter certification should include equivalent output for:

- package or manifest validation
- backend `/ready` and `/review` smoke checks
- auth failure path
- privacy storage/log check
- failure-mode smoke check
- telemetry capture or sanitized event fixture
- uninstall or rollback command

Examples by surface:

| Adapter | Required extra evidence |
|---|---|
| Outlook Smart Alerts | Rendered manifest validation, Microsoft 365 assignment scope, supported client/version matrix, Smart Alert allow/warn/block/approval-required fixtures. |
| Browser GenAI extension | Managed Chrome/Edge policy evidence, target selector tests, domain policy behavior, MV3 worker restart behavior, extension storage privacy check. |
| DMS hook/scanner | Manifest scanner or hook payload fixture, matter id mapping proof, check-in hold/block behavior, DMS audit metadata privacy check. |
| Word taskpane | ReadDocument permission review, selected/body text review fixture, explicit non-enforcement evidence for save/share/export. |
| Desktop watcher | Explicit opt-in source, local token behavior, watched-folder/clipboard privacy review, LaunchAgent install/uninstall proof when packaged. |
| Direct API | OpenAPI example validation, client auth, idempotency behavior, SIEM/audit export privacy check. |

## Exit Criteria

An adapter may be promoted only when:

- every required checklist gate has passing evidence
- failures have explicit owner/date remediation or are documented as non-goals
- privacy checks prove no prohibited raw content is persisted
- the compatibility matrix and maturity matrix are updated
- release checklist links the adapter's smoke tests

## Recertification Triggers

Recertify after:

- backend policy schema or `/review` contract changes
- adapter auth, storage, telemetry, or failure semantics change
- SaaS client/runtime version changes
- manifest permissions or install scope changes
- new content types, attachment handling, rewrite, approval, or uninstall behavior ships
- a production incident, privacy bug, or vendor platform change affects the adapter
