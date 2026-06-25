# Indonesia (ID) Defensibility Report

> Generated 2026-06-06 from `src/kaypoh/review/jurisdictions_data/ID.toml`. Internal benchmarking and procurement-support artifact only; not legal advice.

## Statutory Coverage

Companion coverage source: `docs/statutory-coverage.md`. Runtime statutory references:

- Undang-Undang Perlindungan Data Pribadi (UU PDP) No. 27/2022
- OJK Regulation on Capital Market Disclosure and Insider Trading

Runtime PII rule families:

- ID_UU_PDP_PERSONAL_DATA

Runtime MNPI rule families:

- ID_OJK_MARKET_ABUSE

Jurisdiction-local recognizers:

| Rule | Severity | Defensible basis |
| --- | --- | --- |
| `id_nik` | high | Indonesia NIK (Nomor Induk Kependudukan) civil-registry identifier |

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

- Jurisdiction code: `ID`
- Label: Indonesia
- Recognizer count: 1
- PII family count: 1
- MNPI family count: 1
