# India (IN) Defensibility Report

> Generated 2026-10-30 from `src/junas/review/jurisdictions_data/IN.toml`. Internal detector research artifact only; not legal advice.

## Statutory Coverage

Companion coverage source: `docs/statutory-coverage.md`. Runtime statutory references:

- Digital Personal Data Protection Act 2023 (DPDPA) sections 2(t), 9, 10, 16
- DPDP Rules 2025
- SEBI (Prohibition of Insider Trading) Regulations 2015

Runtime PII rule families:

- IN_DPDPA_PERSONAL_DATA
- IN_DPDPA_SENSITIVE_CONTEXT

Runtime MNPI rule families:

- IN_SEBI_PIT

Jurisdiction-local recognizers:

| Rule | Severity | Defensible basis |
| --- | --- | --- |
| `in_aadhaar` | high | India Aadhaar number — Verhoeff-validated 12-digit identifier |
| `in_pan` | high | India PAN — taxpayer identifier (CBDT Income Tax Department) |
| `in_gstin` | medium | India GSTIN — GST identification number |
| `in_voter_id` | medium | India Voter ID (EPIC) — Election Commission photo identity |

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

- Jurisdiction code: `IN`
- Label: India
- Recognizer count: 4
- PII family count: 2
- MNPI family count: 1
