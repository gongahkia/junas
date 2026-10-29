# Korea (KR) Defensibility Report

> Generated 2026-10-30 from `src/junas/review/jurisdictions_data/KR.toml`. Internal detector research artifact only; not legal advice.

## Statutory Coverage

Companion coverage source: `docs/statutory-coverage.md`. Runtime statutory references:

- Personal Information Protection Act Article 2 and Article 24-2
- Financial Investment Services and Capital Markets Act Articles 174-179

Runtime PII rule families:

- KR_PIPA_PERSONAL_INFORMATION
- KR_PIPA_RRN_RESTRICTED

Runtime MNPI rule families:

- KR_FSCMA_INSIDER_TRADING

Jurisdiction-local recognizers:

| Rule | Severity | Defensible basis |
| --- | --- | --- |
| `kr_rrn` | high | Korean resident registration number |
| `kr_business_registration` | medium | Korean business registration number |

## Known Gaps

- Deterministic strict-mode reports are detector evidence, not a legal conclusion.
- `audit_grade` public-source retrieval and LLM adjudication may be required for public-status, materiality, safe-harbour, and domain-inference questions.
- Candidate `.bucket.json` sidecars are internal benchmarking review artifacts, not procurement-grade legal truth.
- Customer citation overrides can change the cited internal policy without changing detector recall.

## Reproducibility

- Engine results expose per-finding `source_verification` and detector `metadata` where applicable.
- Corpus locks, label provenance and measured reports provide reproducible detection evidence.
- Internal fixture agreement does not establish generalization to unseen documents.

## Pack Manifest

- Jurisdiction code: `KR`
- Label: Korea
- Recognizer count: 2
- PII family count: 2
- MNPI family count: 1
