# United Arab Emirates (AE) Defensibility Report

> Generated 2026-06-06 from `src/junas/review/jurisdictions_data/AE.toml`. Internal benchmarking and procurement-support artifact only; not legal advice.

## Statutory Coverage

Companion coverage source: `docs/statutory-coverage.md`. Runtime statutory references:

- UAE Federal Decree-Law 45/2021 (PDPL) Articles 1, 15, 22
- UAE Data Office Resolution 1/2023
- DIFC Data Protection Law 2020
- ADGM Data Protection Regulations 2021

Runtime PII rule families:

- AE_PDPL_PERSONAL_DATA
- AE_PDPL_SENSITIVE_CONTEXT

Runtime MNPI rule families:

- AE_SCA_INSIDER_TRADING

Jurisdiction-local recognizers:

| Rule | Severity | Defensible basis |
| --- | --- | --- |
| `ae_emirates_id` | high | UAE Emirates ID number — national identifier (784 country prefix) |
| `ae_trade_licence` | medium | UAE Trade / commercial licence number |
| `ae_passport` | high | UAE passport number |

## Known Gaps

- Deterministic strict-mode reports are detector evidence, not a legal conclusion.
- `audit_grade` public-source retrieval and LLM adjudication may be required for public-status, materiality, safe-harbour, and domain-inference questions.
- Candidate `.bucket.json` sidecars are internal benchmarking review artifacts, not procurement-grade legal truth.
- Customer citation overrides can change the cited internal policy without changing detector recall.

## Operational Controls

- Review responses expose per-finding `source_verification` and detector `metadata` where applicable.
- HMAC journal and audit-pack export provide tamper-evident reviewer decisions and pack manifests.
- `/pseudonymize` is reversible and may persist mappings when explicitly enabled; `/anonymize` is irreversible placeholder-only; `/redact` emits opaque markers without reidentification material.
- Sanitized reviewer action rates are aggregated by rule in audit packs; raw reviewer rationale and raw document text are not added to defensibility manifests.

## Pack Manifest

- Jurisdiction code: `AE`
- Label: United Arab Emirates
- Recognizer count: 3
- PII family count: 2
- MNPI family count: 1
