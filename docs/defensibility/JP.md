# Japan (JP) Defensibility Report

> Generated 2026-10-30 from `src/junas/review/jurisdictions_data/JP.toml`. Internal detector research artifact only; not legal advice.

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

## Reproducibility

- Engine results expose per-finding `source_verification` and detector `metadata` where applicable.
- Corpus locks, label provenance and measured reports provide reproducible detection evidence.
- Internal fixture agreement does not establish generalization to unseen documents.

## Pack Manifest

- Jurisdiction code: `JP`
- Label: Japan
- Recognizer count: 3
- PII family count: 2
- MNPI family count: 1
