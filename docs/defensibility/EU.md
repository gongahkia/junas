# European Union (EU) Defensibility Report

> Generated 2026-10-30 from `src/junas/review/jurisdictions_data/EU.toml`. Internal detector research artifact only; not legal advice.

## Statutory Coverage

Companion coverage source: `docs/statutory-coverage.md`. Runtime statutory references:

- GDPR Article 4
- EU Market Abuse Regulation

Runtime PII rule families:

- EU_GDPR_PERSONAL_DATA

Runtime MNPI rule families:

- EU_MAR_INSIDE_INFORMATION

Jurisdiction-local recognizers:

| Rule | Severity | Defensible basis |
| --- | --- | --- |
| None | n/a | Baseline pack relies on universal detectors. |

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

- Jurisdiction code: `EU`
- Label: European Union
- Recognizer count: 0
- PII family count: 1
- MNPI family count: 1
