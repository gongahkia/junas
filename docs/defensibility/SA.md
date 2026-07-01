# Saudi Arabia (SA) Defensibility Report

> Generated 2026-06-06 from `src/junas/review/jurisdictions_data/SA.toml`. Internal benchmarking and procurement-support artifact only; not legal advice.

## Statutory Coverage

Companion coverage source: `docs/statutory-coverage.md`. Runtime statutory references:

- KSA Personal Data Protection Law 2023 (Royal Decree M/19)
- SDAIA Implementing Regulations 2024
- KSA PDPL Article 29 (cross-border transfer)
- Saudi CMA Market Conduct Regulations

Runtime PII rule families:

- SA_PDPL_PERSONAL_DATA
- SA_PDPL_SENSITIVE_CONTEXT

Runtime MNPI rule families:

- SA_CMA_INSIDER_TRADING

Jurisdiction-local recognizers:

| Rule | Severity | Defensible basis |
| --- | --- | --- |
| `sa_national_id` | high | KSA National ID — Saudi citizen/resident identifier |
| `sa_iqama` | high | KSA Iqama — residence-permit identifier |
| `sa_commercial_registration` | medium | KSA Commercial Registration number |

## Known Gaps

- Deterministic strict-mode reports are detector evidence, not a legal conclusion.
- `audit_grade` public-source retrieval and LLM adjudication may be required for public-status, materiality, safe-harbour, and domain-inference questions.
- Candidate `.bucket.json` sidecars are internal benchmarking review artifacts, not procurement-grade legal truth.
- Customer citation overrides can change the cited internal policy without changing detector recall.

## Operational Controls

- Review responses expose per-finding `source_verification` and detector `metadata` where applicable.
- With configured journal keys, the HMAC journal and audit-pack export provide tamper-evidence for reviewer decisions and pack manifests.
- `/pseudonymize` is reversible and may persist mappings when explicitly enabled; `/anonymize` is irreversible placeholder-only; `/redact` emits opaque markers without reidentification material.
- Sanitized reviewer action rates are aggregated by rule in audit packs; raw reviewer rationale and raw document text are not added to defensibility manifests.

## Pack Manifest

- Jurisdiction code: `SA`
- Label: Saudi Arabia
- Recognizer count: 3
- PII family count: 2
- MNPI family count: 1
