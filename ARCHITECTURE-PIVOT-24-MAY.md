# Kaypoh Architecture Pivot - 24 May 2026

## Decision

Kaypoh should be treated as a pre-send document safety layer first, not as a raw MNPI classifier. The core workflow is:

1. Extract inline text or text/DOCX/PDF content locally.
2. Detect PII and MNPI evidence with deterministic rules, jurisdiction packs, and optional local-only models.
3. Return review findings, remediation suggestions, and scores.
4. For safe downstream analysis, produce deterministic placeholders and a local mapping table through `POST /anonymize`.

`POST /classify` remains for compatibility and model experimentation. `POST /review` and `POST /anonymize` are the primary product surfaces.

## Accuracy-First Shape

PII is the first product wedge because it is span-local and more measurable than MNPI. The system should optimize recall before automation convenience:

- SG-first recognizers for NRIC/FIN, passport-like identifiers, postal-address signals, phone, email, named-person markers, and bank/account references.
- Deterministic placeholders such as `[PERSON_1]`, `[NRIC_FIN_1]`, and `[EMAIL_1]`.
- Exact-span replacement from end to start so offsets remain stable.
- Local mapping table returned to the caller for auditable re-identification.
- Human-review fields preserved through `findings`, `suggestions`, scores, and offsets.

MNPI is reviewed differently because materiality and public status are contextual. Broad MNPI passages should be flagged and scored, but not automatically rewritten as if they were exact entities. Kaypoh may anonymize exact MNPI scalars, such as monetary amounts and percentages, while keeping material-event passages as review findings.

## LLM and Retrieval Policy

Local/open-weight LLMs can improve MNPI adjudication, but they should not replace deterministic evidence. The defensible pattern is structured adjudication:

- The review engine emits findings and sanitized public-evidence summaries.
- External retrieval providers may receive only sanitized entity/ticker/event/date queries, never private document text, exact offending spans, emails, phone numbers, NRIC/FIN values, or exact private financial values.
- Local LLMs may receive private document text only when served on loopback/private infrastructure or when explicitly configured.
- The API exposes chain-of-evidence: findings, legal basis, suggestions, public evidence, matched sources, unverified claims, confidence, and privacy ledger.
- The API must not expose raw chain-of-thought. If a model is used, it returns short structured rationale fields.

## Target Runtime

Active runtime:

- `POST /anonymize`: primary pre-processing endpoint for documents leaving the customer environment.
- `POST /review`: same evidence stack without text rewriting.
- `POST /classify` and `POST /classify/batch`: legacy classifier compatibility.
- `GET /health`, `/ready`, `/diagnostics`, `/metrics`: operational surfaces.

Deprecated product assumptions:

- Archived HTML demo frontends are not active runtime surfaces.
- The old classifier-only framing is not the product architecture.
- Model confidence alone is not sufficient for a defensible MNPI decision.

## Expansion Sequence

1. Harden SG PII recall and precision with adversarial fixture coverage.
2. Add mandatory review-state APIs so users can approve, reject, or add findings before write-out.
3. Add fuzzy entity linking for variants such as `Dr Jane Tan`, `Jane Tan`, and `Tan`.
4. Expand jurisdiction packs from SG to SEA, then US/UK/EU.
5. Add local LLM adjudication for MNPI materiality and public-status review, always returning structured JSON evidence.
6. Add sanitized public-source retrieval through Exa/Tinyfish only after privacy-ledger tests prove offending information cannot be sent out.
7. Consider a Rust or Go span engine only after profiling shows deterministic extraction/replacement is the bottleneck. The current bottleneck is more likely model inference and document extraction than string replacement.
