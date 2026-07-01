# Integration Maturity Matrix

Maturity labels describe evidence, support posture, and security requirements for adapter claims. They do not change backend API compatibility.

| Label | Criteria | Allowed claim | Required evidence before promotion |
|---|---|---|---|
| `core` | Backend/API path with stable request/response contract, auth model, tests, docs, and release verification. | Baseline supported integration path. | OpenAPI schema, auth and tenant-isolation tests, policy contract tests, versioning docs, operational runbook. |
| `supported-target` | Adapter target with roadmap priority and current source, but support depends on certification for each deployed environment. | Supported target for pilots when deployment and QA checklist pass. | Install/deploy docs, security model, policy-decision mapping, failure behavior, privacy checks, smoke/manual QA, telemetry plan. |
| `experimental` | Prototype or substrate useful for demos, development, or limited internal pilots. | Experimental adapter or substrate. | Source path, known limitations, manual run steps, security caveats, explicit non-enforcement language. |
| `experimental-local-fallback` | Local opt-in surface for demos, offline use, or power users. | Experimental local fallback, not enterprise enforcement. | Source path, local ACL/auth caveats, explicit opt-in language, and no production enforcement claim. |
| `demo-only` | Demo script or fixture that illustrates a flow but lacks deployment, auth, privacy, or compatibility evidence. | Demo only. | Script or fixture docs, hard limits, no production support claim. |
| `planned` | Research or backlog surface with no shipped adapter source. | Planned or research-only surface, not support. | Discovery notes, explicit no-support claim, and no packaging/test expectation. |
| `archived` | Deprecated, moved, superseded, or intentionally unsupported adapter/source path. | Archived reference only. | Replacement path or removal rationale, no active packaging/test expectation. |

Promotion gates:

- `experimental` to `supported-target`: must prove install path, backend contract conformance, failure behavior, no raw-content storage, and target-surface QA.
- `supported-target` to `core`: must become a baseline integration path with stable versioned contracts and repeatable release verification.
- Any label to `archived`: must state the replacement or reason support stopped.

Demotion triggers:

- Adapter stores raw prompts, email bodies, document text, reversible mappings, or auth headers outside documented runtime boundaries.
- Adapter cannot survive ordinary vendor UI/runtime changes without silent failure.
- Adapter lacks a current deploy path for the claimed environment.
- Adapter duplicates a direct API workflow with worse privacy or operational evidence.
