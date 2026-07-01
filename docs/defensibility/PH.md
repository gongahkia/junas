# Philippines (PH) Defensibility Report

> Generated 2026-06-06 from `src/junas/review/jurisdictions_data/PH.toml`. Internal benchmarking and procurement-support artifact only; not legal advice.

## Statutory Coverage

Companion coverage source: `docs/statutory-coverage.md`. Runtime statutory references:

- Philippines Data Privacy Act of 2012 (Republic Act 10173)
- Philippines Securities Regulation Code (Republic Act 8799) section 27

Runtime PII rule families:

- PH_DPA_PERSONAL_DATA

Runtime MNPI rule families:

- PH_SRC_INSIDER_TRADING

Jurisdiction-local recognizers:

| Rule | Severity | Defensible basis |
| --- | --- | --- |
| `ph_philsys` | high | Philippines PhilSys System Number (PSN) |
| `ph_tin` | medium | Philippines Tax Identification Number (TIN) |

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

- Jurisdiction code: `PH`
- Label: Philippines
- Recognizer count: 2
- PII family count: 1
- MNPI family count: 1
