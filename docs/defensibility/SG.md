# Singapore (SG) Defensibility Report

> Generated 2026-06-06 from `src/kaypoh/review/jurisdictions_data/SG.toml`. Internal benchmarking and procurement-support artifact only; not legal advice.

## Statutory Coverage

Companion coverage source: `docs/statutory-coverage.md`. Runtime statutory references:

- Personal Data Protection Act 2012
- Securities and Futures Act 2001 sections 215, 218, 219

Runtime PII rule families:

- SG_PDPA_PERSONAL_DATA
- SG_PDPA_SENSITIVE_CONTEXT

Runtime MNPI rule families:

- SG_SFA_INSIDE_INFORMATION
- SG_SFA_GENERALLY_AVAILABLE

Jurisdiction-local recognizers:

| Rule | Severity | Defensible basis |
| --- | --- | --- |
| `sg_court_citation` | medium | Singapore court neutral citation identifies a matter and counterparty |
| `sg_paynow` | high | Singapore PayNow identifier (UEN / NRIC / mobile) |
| `sg_mas_licence` | medium | Singapore MAS capital markets services / financial adviser licence number |
| `sg_sgx_counter` | low | SGX counter / cashtag identifier |
| `sg_ipos_tm_number` | medium | Singapore IPOS trade mark application / registration number |
| `sg_acra_transaction_number` | medium | Singapore ACRA / Bizfile transaction or filing reference |
| `sg_hdb_reference` | medium | Singapore HDB flat-purchase / resale matter reference |
| `sg_sla_lot_number` | medium | Singapore SLA MK/TS land, strata, or accessory lot number |
| `sg_sla_title_plan_number` | medium | Singapore SLA title-plan / strata-title plan reference |
| `sg_ura_planning_reference` | medium | Singapore URA planning submission / decision reference |

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

- Jurisdiction code: `SG`
- Label: Singapore
- Recognizer count: 10
- PII family count: 2
- MNPI family count: 2
