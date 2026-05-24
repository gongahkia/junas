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

- SG-first recognizers for NRIC/FIN, UEN (ACRA), passport-like identifiers, postal-address signals, phone, email, named-person markers, and bank/account references.
- Legal-contract defined-term suppression so tokens like `Purchaser`, `Vendor`, `Schedule 1`, and `the Company` do not false-positive as named persons. The suppression list is parsed from the contract's own defined-terms block per document.
- Fuzzy entity linking so `ACME Pte. Ltd.`, `Acme`, and `the Company` resolve to the same anonymisation key within a document, and `Dr Jane Tan` / `Jane Tan` / `Tan` collapse to one `[PERSON_1]`.
- Deterministic placeholders such as `[PERSON_1]`, `[NRIC_FIN_1]`, and `[EMAIL_1]`.
- Exact-span replacement from end to start so offsets remain stable.
- Local mapping table returned to the caller for auditable re-identification, with a first-class `POST /reidentify` to close the round-trip.
- Human-review fields preserved through `findings`, `suggestions`, scores, and offsets.
- Per-document-type severity overrides: `named_person` is `low` in casual prose but `high` for counterparty principals in a definitive agreement.

MNPI is reviewed differently because materiality and public status are contextual. Broad MNPI passages should be flagged and scored, but not automatically rewritten as if they were exact entities. Kaypoh may anonymize exact MNPI scalars, such as monetary amounts and percentages, while keeping material-event passages as review findings.

## LLM and Retrieval Policy

Local/open-weight LLMs can improve MNPI adjudication, but they should not replace deterministic evidence. Cloud LLM and cloud retrieval are allowed when they materially improve specificity or accuracy, and only when the privacy guard permits the outbound call and the privacy ledger records the decision. Offline-default is the desktop SKU stance, not a hard ceiling on the platform. The defensible pattern is structured adjudication:

- The review engine emits findings and sanitized public-evidence summaries.
- External retrieval providers may receive only sanitized entity/ticker/event/date queries, never private document text, exact offending spans, emails, phone numbers, NRIC/FIN/UEN values, or exact private financial values.
- Tinyfish is a first-class public-source retrieval target alongside Exa; the runtime ships a real adapter rather than the current stub at `layer7_public_evidence/inference.py`. Both providers go through the same `PrivacyGuard.check_external_query` gate.
- Local LLMs may receive private document text when served on loopback/private infrastructure. Remote LLM endpoints are allowed when explicitly opted in via `allow_remote_base_url`, with the same sanitisation discipline and ledger entry.
- The API exposes chain-of-evidence: findings, legal basis, suggestions, public evidence, matched sources, unverified claims, confidence, and privacy ledger.
- The API must not expose raw chain-of-thought. If a model is used, it returns short structured rationale fields.

## Target Runtime

Active runtime:

- `POST /anonymize`: primary pre-processing endpoint for documents leaving the customer environment.
- `POST /review`: same evidence stack without text rewriting.
- `POST /reidentify`: deterministic inverse of `/anonymize` using a caller-supplied mapping, so the round-trip (`anonymise → external LLM → re-identify`) closes inside the runtime instead of in client code.
- `POST /review/{review_id}/decision`: per-finding `accept | reject | rewrite` review-state mutations, persisted to the append-only HMAC-chained journal at `${KAYPOH_JOURNAL_DIR:-./kaypoh-journal}/journal.jsonl`. Gated by `KAYPOH_REVIEW_PERSIST=1`; the request UUID returned from `/review` is the `review_id`.
- `GET /review/{review_id}`: replay the journal for a session and return findings merged with their latest decision; surfaces `decisions_recorded` and audit-export references.
- Audit packs ship through `scripts/export_audit_pack.py` (HMAC-sealed ZIP) and are verified via `scripts/verify_audit_pack.py` + `scripts/verify_journal.py`.
- `POST /classify` and `POST /classify/batch`: legacy classifier compatibility.
- `GET /health`, `/ready`, `/diagnostics`, `/metrics`: operational surfaces.

Distribution shape (shipped 2026-05-24):

- `kaypoh-local` (`pip install kaypoh[local]`): offline-default desktop SKU. Deterministic engine + Presidio + spaCy + extractors only. No `torch`, `transformers`, `sentence-transformers`, `redis`, `xgboost`, `scikit-learn`, `pandas`, or `accelerate`. Bundles `en_core_web_sm` via the PyInstaller spec at `packaging/kaypoh-local.spec`. The entrypoint at `packaging/kaypoh_local_entrypoint.py` binds 127.0.0.1:8765 by default. Browser extensions, mail plugins, and Slack/Outlook hooks are thin clients of the local daemon on `127.0.0.1`.
- `kaypoh-server` (`pip install kaypoh[server]`): full stack including model layers, mosaic aggregation, public-evidence retrieval (Exa, Tinyfish), and local/remote LLM adjudication. Cloud opt-in flows live here.
- Both SKUs share `src/kaypoh/` and the same wire contracts. Splitting is a packaging concern, not a fork. `test/test_local_sku_runtime.py` blocks every server-only module via `sys.modules[name] = None` and proves the local SKU still boots and round-trips through anonymize+reidentify.

Deprecated product assumptions:

- Archived HTML demo frontends are not active runtime surfaces.
- The old classifier-only framing is not the product architecture.
- Model confidence alone is not sufficient for a defensible MNPI decision.
- "Strict offline, full stop" is not the platform stance. Offline-default applies to the desktop SKU; cloud is allowed elsewhere when it improves specificity or accuracy and the privacy guard permits it.

## Expansion Sequence

1. Harden SG PII recall and precision with adversarial fixture coverage. Land UEN regex (legacy `\d{8,9}[A-Z]` and new-format `T\d{2}[A-Z]{2}\d{4}[A-Z]`), legal-contract defined-term suppression parsed from the document's own definitions block, and a curated legal-contract fixture corpus (~50 SPAs/NDAs/SHAs/term sheets with hand-labelled spans). Recall is gated in CI; PRs that drop recall fail.
2. ~~Add mandatory review-state APIs so users can approve, reject, or add findings before write-out. Persist decisions to a local append-only journal, HMAC-chained from a customer-held key, exportable as a signed audit pack for internal audit and MAS-style inspection.~~ **Shipped 2026-05-24:** `POST /review/{id}/decision`, `GET /review/{id}`, HMAC-chained journal under `KAYPOH_JOURNAL_DIR`, audit-pack export+verify scripts. Next: extend audit pack to include reviewer identity claims and per-organisation key rotation.
3. Add fuzzy entity linking for variants such as `Dr Jane Tan`, `Jane Tan`, `Tan`, and for corporate forms (`ACME Pte. Ltd.` ↔ `Acme` ↔ `the Company` ↔ defined-term references).
4. Ship `POST /reidentify` and persist per-document `{document_hash: mapping}` locally so the round-trip survives client restarts.
5. ~~Split packaging into `kaypoh-local` (offline-default desktop SKU) and `kaypoh-server` (full ML + retrieval + LLM stack). Same source tree, different extras and dep manifests.~~ **Shipped 2026-05-24:** `[project.optional-dependencies]` carries `local`, `server`, `dev`, `packaging`. Heavy deps moved to `server`. PyInstaller spec under `packaging/`. `test_local_sku_runtime.py` enforces the contract.
6. Expand jurisdiction packs from SG to SEA (MY/ID/TH/PH/VN), then US/UK/EU. Move `jurisdictions.py` from a hardcoded dict to a `jurisdictions/*.toml` plugin directory so customers can bring their own packs.
7. Local LLM adjudication for MNPI materiality and public-status review returns structured JSON evidence. Remote LLM endpoints are allowed when explicitly opted in via `allow_remote_base_url`, gated by `_is_private_or_local_base_url` and the privacy guard. **Tested 2026-05-24** via `test/test_tinyfish_and_remote_llm.py::RemoteLLMOptInTests`.
8. ~~Complete the Tinyfish public-source retrieval adapter (currently stubbed) and keep Exa in parity, both behind `PrivacyGuard.check_external_query`. Cloud retrieval is allowed when it materially improves specificity or accuracy.~~ **Shipped 2026-05-24:** real Tinyfish adapter against `GET https://api.search.tinyfish.ai/` with `X-API-Key`. Endpoint and API-key env (`TINYFISH_API_KEY`) auto-resolved per provider in `configs/runtime.py`.
9. Consider a Rust or Go span engine only after profiling shows deterministic extraction/replacement is the bottleneck. The current bottleneck is more likely model inference and document extraction than string replacement.
