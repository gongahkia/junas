# China (CN) Defensibility Report

> Generated 2026-06-06 from `src/junas/review/jurisdictions_data/CN.toml`. Internal benchmarking and procurement-support artifact only; not legal advice.

## Statutory Coverage

Companion coverage source: `docs/statutory-coverage.md`. Runtime statutory references:

- Personal Information Protection Law 2021 (PIPL) Articles 4, 28, 31, 38
- Cybersecurity Law 2016 (CSL) Articles 37-41
- Data Security Law 2021 (DSL) Article 31
- China Securities Law Articles 50-54 (insider trading)
- GB 11643-1999 (Resident Identity Card)
- GB 32100-2015 (Unified Social Credit Code)

Runtime PII rule families:

- CN_PIPL_PERSONAL_DATA
- CN_PIPL_SENSITIVE_CONTEXT

Runtime MNPI rule families:

- CN_SECURITIES_LAW_INSIDER

Jurisdiction-local recognizers:

| Rule | Severity | Defensible basis |
| --- | --- | --- |
| `cn_resident_id` | high | China Resident Identity Card number — ISO 7064 MOD 11-2 validated |
| `cn_uscc` | medium | China Unified Social Credit Code — corporate identifier (GB 32100-2015) |
| `cn_phone` | medium | China mobile phone number — personal contact identifier |
| `cn_passport` | high | China passport number — travel-document identifier |

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

- Jurisdiction code: `CN`
- Label: China
- Recognizer count: 4
- PII family count: 2
- MNPI family count: 1
