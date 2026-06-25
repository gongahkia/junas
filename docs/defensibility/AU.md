# Australia (AU) Defensibility Report

> Generated 2026-06-06 from `src/junas/review/jurisdictions_data/AU.toml`. Internal benchmarking and procurement-support artifact only; not legal advice.

## Statutory Coverage

Companion coverage source: `docs/statutory-coverage.md`. Runtime statutory references:

- Privacy Act 1988 (Cth) Australian Privacy Principles
- Corporations Act 2001 (Cth) sections 1042A-1043O

Runtime PII rule families:

- AU_PRIVACY_ACT_PERSONAL_INFORMATION

Runtime MNPI rule families:

- AU_CORPORATIONS_ACT_INSIDE_INFORMATION

Jurisdiction-local recognizers:

| Rule | Severity | Defensible basis |
| --- | --- | --- |
| `au_tfn` | high | Australian Tax File Number |
| `au_abn` | medium | Australian Business Number |
| `au_acn` | medium | Australian Company Number |
| `au_postal_address` | medium | Australian state + 4-digit postcode |

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

- Jurisdiction code: `AU`
- Label: Australia
- Recognizer count: 4
- PII family count: 1
- MNPI family count: 1
