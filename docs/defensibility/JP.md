# Japan (JP) Defensibility Report

> Generated 2026-06-06 from `src/kaypoh/review/jurisdictions_data/JP.toml`. Internal benchmarking and procurement-support artifact only; not legal advice.

## Statutory Coverage

Companion coverage source: `docs/statutory-coverage.md`. Runtime statutory references:

- Act on the Protection of Personal Information Article 2
- Act on the Use of Numbers to Identify a Specific Individual in Administrative Procedures
- Financial Instruments and Exchange Act Articles 166-167

Runtime PII rule families:

- JP_APPI_PERSONAL_INFORMATION
- JP_MY_NUMBER_RESTRICTED_IDENTIFIER

Runtime MNPI rule families:

- JP_FIEA_INSIDER_TRADING

Jurisdiction-local recognizers:

| Rule | Severity | Defensible basis |
| --- | --- | --- |
| `jp_my_number` | high | Japan My Number / Individual Number |
| `jp_corporate_number` | medium | Japan Corporate Number |
| `jp_postal_code` | medium | Japan postal code |

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

- Jurisdiction code: `JP`
- Label: Japan
- Recognizer count: 3
- PII family count: 2
- MNPI family count: 1
