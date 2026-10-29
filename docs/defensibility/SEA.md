# Southeast Asia baseline (SEA) Defensibility Report

> Generated 2026-10-30 from `src/junas/review/jurisdictions_data/SEA.toml`. Internal detector research artifact only; not legal advice.

SEA is the regional baseline pack: it gives Southeast Asia routing a statutory baseline when a more specific local pack is not selected.

## Statutory Coverage

Companion coverage source: `docs/statutory-coverage.md`. Runtime statutory references:

- ASEAN-oriented cross-border privacy and market-abuse baseline

Runtime PII rule families:

- SEA_PERSONAL_DATA_BASELINE

Runtime MNPI rule families:

- SEA_MARKET_ABUSE_BASELINE

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

- Jurisdiction code: `SEA`
- Label: Southeast Asia baseline
- Recognizer count: 0
- PII family count: 1
- MNPI family count: 1
