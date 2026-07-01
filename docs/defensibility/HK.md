# Hong Kong (HK) Defensibility Report

> Generated 2026-06-06 from `src/junas/review/jurisdictions_data/HK.toml`. Internal benchmarking and procurement-support artifact only; not legal advice.

## Statutory Coverage

Companion coverage source: `docs/statutory-coverage.md`. Runtime statutory references:

- Personal Data (Privacy) Ordinance (Cap. 486) section 2
- Securities and Futures Ordinance (Cap. 571) Part XIV sections 270-281

Runtime PII rule families:

- HK_PDPO_PERSONAL_DATA

Runtime MNPI rule families:

- HK_SFO_INSIDE_INFORMATION

Jurisdiction-local recognizers:

| Rule | Severity | Defensible basis |
| --- | --- | --- |
| `hk_hkid` | high | Hong Kong Identity Card number |
| `hk_cr_no` | medium | Hong Kong company / business registration identifier |

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

- Jurisdiction code: `HK`
- Label: Hong Kong
- Recognizer count: 2
- PII family count: 1
- MNPI family count: 1
