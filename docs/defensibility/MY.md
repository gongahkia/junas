# Malaysia (MY) Defensibility Report

> Generated 2026-10-30 from `src/junas/review/jurisdictions_data/MY.toml`. Internal detector research artifact only; not legal advice.

## Statutory Coverage

Companion coverage source: `docs/statutory-coverage.md`. Runtime statutory references:

- Malaysia Personal Data Protection Act 2010
- Capital Markets and Services Act 2007 (CMSA) sections 188-189 (insider trading)

Runtime PII rule families:

- MY_PDPA_PERSONAL_DATA

Runtime MNPI rule families:

- MY_CMSA_INSIDER_TRADING

Jurisdiction-local recognizers:

| Rule | Severity | Defensible basis |
| --- | --- | --- |
| `my_mykad` | high | Malaysia MyKad national identifier |

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

- Jurisdiction code: `MY`
- Label: Malaysia
- Recognizer count: 1
- PII family count: 1
- MNPI family count: 1
