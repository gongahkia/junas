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

## Residual Risk

Junas is a pre-send review aid. It is not legal advice, external counsel review, or a procurement-grade legal evaluation. Operators remain responsible for deployment controls, identity policy, retention, backups, legal hold, and user training.
