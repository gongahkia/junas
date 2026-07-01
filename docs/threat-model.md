# Data Flow And Threat Model

This threat model is an operator-facing summary, not a substitute for a formal security review.

## Data Flow

1. Client sends inline text or a base64 document to the API.
2. Document ingest extracts supported text, metadata findings, document structure, and optional image candidates.
3. The deterministic review engine creates PII/MNPI findings.
4. Rewrite endpoints produce pseudonymized, anonymized, or redacted text.
5. Optional persistence writes tenant-scoped journals, mappings, subject index, sessions, and matter terms.
6. Optional public evidence or LLM layers run only when tenant/deployer opt-ins pass privacy gates.
7. SIEM export emits redacted JSON events with hashes/counts, not raw document payloads.

## Trust Boundaries

- Local desktop daemon: loopback or Unix socket, local ACL, origin allowlist, signed client tokens.
- Server API: reverse proxy/TLS, API key or JWT tenant auth, role checks.
- Persistence: service-account owned state directory, encrypted mappings, HMAC journal chain.
- External providers: PrivacyGuard, tenant opt-in, structured-token mode by default.
- Admin tooling: secret-manager injected keys, preflight, retention manifest, journal verification.

## Primary Threats And Controls

| Threat | Control |
|---|---|
| Browser page calls local daemon without consent | Origin allowlist plus `X-Junas-Local-Token`; first-connect pairing issues signed expiring tokens |
| Raw PII in logs/SIEM | Backend logs omit body; SIEM sanitizer hashes or drops sensitive fields |
| Tenant cross-read | Tenant context comes from validated credential/JWT only; storage path is tenant-scoped |
| Mapping compromise | Optional Fernet encryption; service-account permissions; subject-index HMAC |
| Journal tampering | HMAC chain, key versions, `verify_journal.py`, rotation sentinel |
| Unsafe document container | ZIP/TAR caps, path traversal detection, macro/`.msg`/`.7z` degraded fail-open by default; `JUNAS_DOCUMENT_FAIL_CLOSED=1` rejects |
| PDF hidden semantics missed | AcroForm, XFA, signatures, annotations, embedded files, URI actions are surfaced or degraded fail-open |
| External provider leakage | Disabled by default; PrivacyGuard sanitization; tenant and deployer opt-ins |
| Model over-suppression | Deterministic-high findings cannot be removed by LLM adjudication |
| Lost KMS/customer key | Encrypted mappings are unrecoverable; recovery requires retained key material |

## OWASP API Top 10 Mapping

This mapping uses the [OWASP API Security Top 10 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/) as the external reference set. It maps Junas controls and known gaps for the backend API and local daemon; adapter-specific threats belong in `docs/security/adapter-threat-model.md`.

| OWASP risk | Junas exposure | Current control | Required evidence |
|---|---|---|---|
| [API1 Broken Object Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/) | `review_id`, `document_hash`, mapping ids, tenant-scoped session ids, matter ids, and subject-erasure targets address persisted objects. | Tenant context is derived from API key/JWT credentials; tenant storage paths use the resolved tenant id; review-session reads and decisions route through tenant-scoped journal access. | Object-level authorization tests for every endpoint that accepts object identifiers, including guessed cross-tenant ids. |
| [API2 Broken Authentication](https://owasp.org/API-Security/editions/2023/en/0xa2-broken-authentication/) | Hosted API, local daemon, adapter calls, and reviewer decisions depend on credentials or signed local tokens. | Production tenant auth supports API-key registry and JWT; local daemon pairing issues expiring signed client tokens; auth denials emit security events. | Startup preflight must reject missing production auth; rate limits and token expiry tests must cover review, batch classify, local pairing, reidentify, and decision routes. |
| [API3 Broken Object Property Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa3-broken-object-property-level-authorization/) | Review/session responses can expose findings, matched spans, policy metadata, reviewer decisions, and audit exports. | Response models are explicit Pydantic schemas; SIEM sanitizer drops sensitive keys; audit exports are intended to emit hashes/counts instead of raw bodies. | Tests must prove role-specific responses omit raw body, matched text, reversible mappings, auth headers, and audit-only fields for non-auditors. |
| [API4 Unrestricted Resource Consumption](https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/) | Inline text, base64 documents, batch classify, document extraction, public demo, public evidence, and optional LLM calls consume CPU, memory, network, and provider quota. | Request body guard enforces `max_request_bytes`; document extraction uses container caps; public demo has a dedicated rate limit; optional providers are disabled unless configured. | Endpoint-specific rate limits, oversized JSON/base64 tests, document bomb tests, and provider timeout tests must run in CI. |
| [API5 Broken Function Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa5-broken-function-level-authorization/) | Reviewer decisions, audit reads, reidentify, approval, erasure, and admin-style future routes are higher-risk than ordinary review. | Route dependencies require review, decision, or audit roles; decision attribution comes from authenticated principal except explicit dev mode. | Route inventory must list auth and role requirements; tests must prove maker/reviewer/auditor/admin boundaries and reject method/path guessing. |
| [API6 Unrestricted Access to Sensitive Business Flows](https://owasp.org/API-Security/editions/2023/en/0xa6-unrestricted-access-to-sensitive-business-flows/) | Automated review, approval request creation, reidentify, public evidence lookup, and export flows can be abused for quota exhaustion or workflow spam. | Public demo is capped and persistence-free; production rollout docs require one controlled adapter plus direct API; sensitive flows are behind tenant auth. | Abuse controls need per-tenant quotas, approval-spam limits, export throttles, and telemetry alerts for abnormal flow volume. |
| [API7 Server Side Request Forgery](https://owasp.org/API-Security/editions/2023/en/0xa7-server-side-request-forgery/) | Public evidence and any future URL-taking endpoint can fetch attacker-controlled URLs. | External providers are optional and disabled by default; docs require tenant/deployer opt-in and PrivacyGuard. | URL validation tests must block localhost, link-local, metadata, private, reserved ranges, unsafe schemes, redirects to blocked ranges, and raw upstream response passthrough. |
| [API8 Security Misconfiguration](https://owasp.org/API-Security/editions/2023/en/0xa8-security-misconfiguration/) | CORS, local daemon ACL, default secrets, persistence keys, reverse proxy logging, body caps, and optional providers are deployment-sensitive. | Runtime config validates many settings; deployment hardening docs cover TLS proxy, secrets, tenancy, filesystem, retention, and logs; local daemon can enforce origin/token checks. | Production preflight must fail closed for missing auth, journal keys, mapping keys when persistence is enabled, unsafe CORS, missing body caps, and enabled external providers without consent. |
| [API9 Improper Inventory Management](https://owasp.org/API-Security/editions/2023/en/0xa9-improper-inventory-management/) | Root endpoints, public demo routes, local pairing routes, `/classify` compatibility, `/review`, document scrub, metrics, and future `/v1` aliases need explicit ownership. | OpenAPI exposes current routes; docs define compatibility and deprecation expectations for `/classify`; demo routes are gated by environment. | API inventory docs must list every route, auth, role, tenant-scope behavior, payload cap, rate limit, maturity, and deprecation status. |
| [API10 Unsafe Consumption of APIs](https://owasp.org/API-Security/editions/2023/en/0xaa-unsafe-consumption-of-apis/) | Public evidence providers, LLM adjudication, SIEM/syslog, identity/JWKS, extension update URLs, and future vendor integrations are third-party API boundaries. | Optional providers are privacy-gated; SIEM sanitizer drops sensitive fields; JWT validation supports configured issuer/audience/JWKS. | Provider clients need timeouts, schema validation, response size caps, no raw-text logging, SSRF checks, and failure isolation tests. |

## Residual Risk

Junas is a pre-send review aid. It is not legal advice, external counsel review, or a procurement-grade legal evaluation. Operators remain responsible for deployment controls, identity policy, retention, backups, legal hold, and user training.
