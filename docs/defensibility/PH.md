# Philippines (PH) Defensibility Report

> Generated 2026-10-30 from `src/junas/review/jurisdictions_data/PH.toml`. Internal detector research artifact only; not legal advice.

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

## Reproducibility

- Engine results expose per-finding `source_verification` and detector `metadata` where applicable.
- Corpus locks, label provenance and measured reports provide reproducible detection evidence.
- Internal fixture agreement does not establish generalization to unseen documents.

## Pack Manifest

- Jurisdiction code: `PH`
- Label: Philippines
- Recognizer count: 2
- PII family count: 1
- MNPI family count: 1
