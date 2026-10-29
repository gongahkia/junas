# United States (US) Defensibility Report

> Generated 2026-10-30 from `src/junas/review/jurisdictions_data/US.toml`. Internal detector research artifact only; not legal advice.

## Statutory Coverage

Companion coverage source: `docs/statutory-coverage.md`. Runtime statutory references:

- SEC insider trading / MNPI guidance
- Regulation FD

Runtime PII rule families:

- US_PRIVACY_BASELINE

Runtime MNPI rule families:

- US_MNPI_INSIDER_TRADING
- US_REG_FD_PUBLIC_DISCLOSURE

Jurisdiction-local recognizers:

| Rule | Severity | Defensible basis |
| --- | --- | --- |
| `us_ssn` | high | US Social Security Number |
| `us_ein` | medium | US Employer Identification Number |
| `us_itin` | high | US Individual Taxpayer Identification Number |

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

- Jurisdiction code: `US`
- Label: United States
- Recognizer count: 3
- PII family count: 1
- MNPI family count: 2
