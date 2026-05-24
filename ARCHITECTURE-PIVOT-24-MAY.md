# Kaypoh Architecture Pivot - 24 May 2026

## Decision

Kaypoh should be treated as a pre-send document safety layer first, not as a raw MNPI classifier. The core workflow is:

1. Extract inline text or text/DOCX/PDF content locally.
2. Detect PII and MNPI evidence with deterministic rules, jurisdiction packs, and optional LLM reasoning.
3. Return review findings, remediation suggestions, and scores.
4. For safe downstream analysis, produce deterministic placeholders and a local mapping table through `POST /anonymize`.

`POST /review` and `POST /anonymize` are the primary product surfaces. `POST /classify` is retained as a compatibility shim; the legacy `lexicon → embedding → clustering → model1 → model2 → mosaic → regression` pipeline is no longer the product wedge and the team does not invest in further training of that classifier stack. Investment goes into the deterministic engine, LLM-assisted reasoning, and — for accuracy recovery on the LLM tier — targeted distillation and preference-tuning (expansion-sequence items 29–32).

## Accuracy-First Shape

PII is the first product wedge because it is span-local and more measurable than MNPI. The system optimises recall before automation convenience:

- SG-first recognizers for NRIC/FIN, UEN (ACRA), passport-like identifiers, postal-address signals, phone, email, named-person markers, and bank/account references.
- Legal-contract defined-term suppression so tokens like `Purchaser`, `Vendor`, `Schedule 1`, and `the Company` do not false-positive as named persons. The suppression list is parsed from the contract's own defined-terms block per document. Defined-term inheritance across linked documents within a review session is wired: pass `session_id` to `/review` or `/anonymize` and the SPA's `the "Purchaser"` definition is automatically inherited by a paired disclosure schedule reviewed in the same session.
- Fuzzy entity linking so `ACME Pte. Ltd.`, `Acme`, and `the Company` resolve to the same anonymisation key within a document, and `Dr Jane Tan` / `Jane Tan` / `Tan` collapse to one `[PERSON_1]`.
- Deterministic placeholders such as `[PERSON_1]`, `[NRIC_FIN_1]`, and `[EMAIL_1]`.
- Exact-span replacement from end to start so offsets remain stable.
- Local mapping table returned to the caller for auditable re-identification, with a first-class `POST /reidentify` and a persistent per-document mapping store keyed by SHA-256 of the extracted text.
- Human-review fields preserved through `findings`, `suggestions`, scores, and offsets.
- Per-document-type severity overrides: `named_person` is `low` in casual prose but `high` for counterparty principals in a definitive agreement. The same per-doc-type lens applies to MNPI rules — a `transaction_codename` is `medium` in casual prose, `high` in an external memo or research note.

MNPI is reviewed differently because materiality and public status are contextual. Broad MNPI passages are flagged and scored, not automatically rewritten. Kaypoh anonymises exact MNPI scalars (monetary amounts, percentages) while keeping material-event passages as review findings.

Legal-contract MNPI surface is distinct from finance-comms MNPI and is detected separately:

- `transaction_codename` — `Project <CapitalizedName>` patterns, the canonical "before announcement" tell in deal memos. Intra-line regex so a stray newline does not pull adjacent paragraphs into the matched_text.
- `definitive_agreement` — Share Purchase Agreement / SPA / Shareholders Agreement / SHA / APA / MOU / LOI / Term Sheet. Existence of a binding deal document is itself MNPI pre-announcement.
- `material_adverse_change` — MAC clauses, MAE, "material adverse change". Price-sensitive.
- `embargo_marker` — Signing Date / Closing Date / Effective Date / Embargoed / Press Hold.

Defined-term suppression extends to MNPI for abbreviation-style rules (`definitive_agreement`, `material_adverse_change`) so a contract abbreviating itself as `"SPA"` or `"MAC"` does not trip its own meta-reference. `transaction_codename` and `embargo_marker` are not suppressed because the defined term is the substantive risk.

### Evaluation corpus posture

Synthetic data is a first-class artefact. `test/fixtures/legal-corpus/` is the hand-labelled gold set (hard-fail recall gate). `test/fixtures/legal-corpus-adversarial/` (planned) holds OpenAI-generated obfuscated PII / negative-prose / multilingual variants and gates precision separately. Adversarial and multilingual coverage matter because SG contracts mix English with Mandarin, Bahasa Melayu, and Tamil names, and PDF inputs come with OCR ligature artefacts and broken DOCX runs. The generation tooling at `scripts/generate_legal_fixture.py` (planned) wraps the OpenAI API; hand-review remains mandatory before any lock-baseline refresh.

### Statute citations

Suggestion rationales are statute-cited and lead with the matched text in quotes — for example, `"S1234567D" detected → PDPA s13 and PDPC NRIC Advisory (effective 31 Dec 2026): NRIC/FIN must not be ...`. Reviewers can forward the rationale verbatim to internal audit. Customers needing internal policy citations instead of the built-in PDPA/SFA/GDPR/MAR/Reg-FD references use the `KAYPOH_CITATIONS_OVERRIDE` hook, keyed by `(rule, jurisdiction)`, consulted before the built-in lookup.

## LLM and Retrieval Policy

Local/open-weight LLMs improve MNPI adjudication; cloud LLMs and cloud retrieval are allowed when they materially improve specificity or accuracy. The desktop SKU's offline-default applies only to the runtime path. Two scopes are intentionally separate:

**Build-time scope** (no privacy concerns; used aggressively): synthetic legal-contract corpus generation, adversarial PII fixtures, negative-prose fixtures, multilingual SG fixtures, deal-codename diversity. The OpenAI API is used here against synthetic / public inputs only; no customer data involved. As a corollary, LLM-discovered defined-term patterns are baked into the deterministic regex so the runtime stays offline-capable even when the build pipeline uses cloud reasoning.

**Runtime scope** (privacy-gated; opt-in per tenant on the server SKU): cloud LLM calls go through the same `PrivacyGuard.check_external_query` gate and every decision is recorded in the privacy ledger. The desktop SKU is untouched by any of this.

The defensible runtime pattern is structured adjudication:

- The review engine emits findings and sanitized public-evidence summaries.
- External retrieval providers receive only sanitized entity/ticker/event/date queries, never private document text, exact offending spans, emails, phone numbers, NRIC/FIN/UEN values, or exact private financial values.
- Tinyfish and Exa are first-class public-source retrieval targets behind the same gate. Provider switching is via `KAYPOH_PUBLIC_EVIDENCE_PROVIDER`; the API key env (`TINYFISH_API_KEY` or `EXA_API_KEY`) and default endpoint resolve per provider in `configs/runtime.py`.
- Local LLMs may receive private document text when served on loopback/private infrastructure. Remote LLM endpoints (including OpenAI) are allowed when explicitly opted in via `allow_remote_base_url`, with the same sanitisation discipline and ledger entry. OpenAI is a first-class provider alongside vLLM / Ollama; provider selection is via `KAYPOH_LLM_PROVIDER` and the same `LocalLLMAdjudicator` interface.
- The API exposes chain-of-evidence: findings, legal basis, suggestions, public evidence, matched sources, unverified claims, confidence, and privacy ledger.
- The API must not expose raw chain-of-thought. If a model is used, it returns short structured rationale fields.

### Runtime LLM reasoning surfaces

When the server SKU has a remote-LLM provider configured and the tenant has opted in, the following LLM-assisted steps are available. Each step is optional, gated, and never overrides a deterministic high finding (the engine caps any LLM-driven label change at `max(pii_score, mnpi_score) < 85.0`):

- **MNPI materiality adjudication** via the cloud-LLM provider in `layer8_llm_adjudicator`. The adjudicator returns structured JSON (`risk_label`, `public_status`, `materiality_reason`, `matched_public_sources`, `unverified_claims`). LLM verdicts can downgrade deterministic medium findings when public evidence supports public status; they cannot suppress a deterministic high.
- **LLM-assisted defined-term extraction.** Preamble-only pre-pass (first ~500 tokens) catches `Acme (hereinafter referred to as "the Seller")`, `we will use "X" to refer to Y`, and other looser patterns the regex misses. Output is the defined-term list; raw doc body is not sent. Cached by document hash.
- **Severity calibration on ambiguous findings.** The matched span ± 200 char window is shipped for a structured severity adjustment. LLM can only soften severity; it cannot tighten beyond the deterministic floor.
- **"What did we miss?" inverse audit.** Sends deterministic findings + a hash of the rest. Output journaled as `coverage_warning` events. Advisory only; never auto-acted-on.
- **Rationale composition.** Optional LLM-generated rationale on accepted findings, quoting the matched span and the surrounding clause. Bounded by the post-review path.
- **Two-tier engine.** Deterministic engine is the hot path and source of truth. The LLM tier runs only on documents in an ambiguous score band (PII findings present but MNPI score between thresholds). Keeps p95 latency bounded for the 90% case.

### Review profiles

Two profiles ship:

- `strict` (default; offline-desktop and server alike): deterministic engine only, no outbound LLM calls.
- `audit_grade` (server SKU, opt-in): engages the LLM adjudicator, LLM-assisted defined-term extraction, and LLM rationale composition. Cost is per-audit-grade call; recorded in the privacy ledger.

### Privacy hardening for regulated tenants

A **structured-tokens-in/out** runtime LLM mode is offered: instead of sending raw text fragments to the LLM, the server sends `{entity_id, context_window_hash, sanitised_query}` over a constrained vocabulary the server has already validated. Stronger privacy guarantee than redact-then-send; engineering cost depends on the specific tenant requirement.

### Distillation and feedback training

Two training tracks are admitted as accuracy-recovery levers on top of the deterministic + LLM stack. Both preserve the deterministic-high invariant — training can move medium / low / SAFE labels but cannot teach the LLM tier to suppress a deterministic-high finding.

- **Cloud-adjudicator distillation → local student.** Trains a small (1–3B param) model from cloud-LLM verdicts over the synthetic + adversarial legal corpora (build-time scope; no customer text). Goal: ship `audit_grade` on the offline-default `kaypoh-local` SKU without a cloud round-trip. Drops in as a new `KAYPOH_LLM_PROVIDER` value behind the existing `LocalLLMAdjudicator` interface.
- **Journal-driven preference tuning.** The HMAC-chained decision journal already pairs each finding with a reviewer action ∈ `{accept, reject, rewrite}`. Treat `accept` vs `reject` as a DPO/IPO preference signal over the LLM tier's verdicts. Hard prerequisite: per-tenant sanitisation of rationales before any journal export, gated by the `PrivacyGuard` ledger.

Expansion-sequence items 29–32 break these into shippable units. The recall + precision gates (`scripts/recall_gate.py`) and the adversarial corpus are the evaluation harness for both tracks: a trained artefact ships only when it meets or beats the locked baselines.

## Target Runtime

Active endpoints:

- `POST /anonymize`: primary pre-processing endpoint for documents leaving the customer environment. Returns `document_hash` and a `mapping_persisted` flag when `KAYPOH_REVIEW_PERSIST=1`.
- `POST /review`: same evidence stack without text rewriting.
- `POST /reidentify`: deterministic inverse of `/anonymize` using either a caller-supplied `mapping` or a `document_hash` referencing the local persistent store.
- `POST /review/{review_id}/decision`: per-finding `accept | reject | rewrite` review-state mutations, persisted to the append-only HMAC-chained journal at `${KAYPOH_JOURNAL_DIR:-./kaypoh-journal}/journal.jsonl`. Gated by `KAYPOH_REVIEW_PERSIST=1`. Decisions carry `reviewer_id` sourced from the `X-Reviewer-ID` header (header takes precedence over body).
- `GET /review/{review_id}`: replay the journal for a session and return findings merged with their latest decision; surfaces `decisions_recorded`, `decision_reviewer_id` per finding, and audit-export references.
- `POST /classify` and `POST /classify/batch`: legacy classifier compatibility. Investment frozen.
- `GET /health`, `/ready`, `/diagnostics`, `/metrics`: operational surfaces.

Audit-pack tooling: `scripts/export_audit_pack.py` produces HMAC-sealed ZIPs; verification via `scripts/verify_audit_pack.py` and whole-journal integrity via `scripts/verify_journal.py`. Shipped extensions: reviewer roll-up in the manifest (decisions by reviewer X: accept N, reject M, rewrite K — surfaces maker-checker violations), the optional `KAYPOH_AUDIT_MIN_WAIT_SECONDS` gate that surfaces batch-approval red flags (exit code `2` on violation, pack still HMAC-sealed), and per-organisation `KAYPOH_JOURNAL_KEYS_FILE` rotation: each entry serialises with its `key_version`, `verify_chain` resolves keys per-entry, and `rotate_journal_key(to_version, reason)` writes a `journal_key_rolled` sentinel sealed under the new active key. Recall-baseline changes (`recall.lock.json`) are similarly attributable: actor + commit SHA + diff summary committed alongside the lock so an auditor can reconstruct *why* recall expectations changed.

### Distribution shape

- `kaypoh-local` (`pip install kaypoh[local]`): offline-default desktop SKU. Deterministic engine + Presidio + spaCy + extractors only. No `torch`, `transformers`, `sentence-transformers`, `redis`, `xgboost`, `scikit-learn`, `pandas`, or `accelerate`. Bundles `en_core_web_sm` via the PyInstaller spec at `packaging/kaypoh-local.spec`. The entrypoint at `packaging/kaypoh_local_entrypoint.py` binds 127.0.0.1:8765 by default. Browser extensions, mail plugins, and Slack/Outlook hooks are thin clients of the local daemon on `127.0.0.1`.
- `kaypoh-server` (`pip install kaypoh[server]`): full stack including the legacy classifier (compatibility only), mosaic aggregation, public-evidence retrieval (Exa, Tinyfish), and local/remote LLM adjudication (vLLM, Ollama, OpenAI). Cloud opt-in flows live here.
- Both SKUs share `src/kaypoh/` and the same wire contracts. Splitting is a packaging concern, not a fork. `test/test_local_sku_runtime.py` blocks every server-only module via `sys.modules[name] = None` and proves the local SKU still boots and round-trips through `anonymize → reidentify`.

The browser-extension thin client (planned) is an MV3 service worker hooking `paste` / `beforesend` events on chatgpt.com, claude.ai, gemini.google.com. Rewrites the textarea via `POST http://127.0.0.1:8765/anonymize`. Document hash retained client-side so the paired in-place re-identify after the LLM round-trip is one click.

### Deprecated product assumptions

- Archived HTML demo frontends are not active runtime surfaces.
- The old classifier-only framing is not the product architecture. `/classify` and `/classify/batch` are compatibility-only; investment goes into the deterministic engine, LLM-assisted reasoning, and LLM-tier distillation / preference-tuning.
- Model confidence alone is not sufficient for a defensible MNPI decision.
- "Strict offline, full stop" is not the platform stance. Offline-default applies to the desktop SKU; cloud is allowed elsewhere when it improves specificity or accuracy and the privacy guard permits it.

## Jurisdiction Coverage

Snapshot of detection capabilities by jurisdiction as of 2026-05-24. ✓ = available today; ✗ = not yet implemented. Universal rules fire regardless of jurisdiction pack; jurisdiction-specific rules and statute citations require a curated pack.

| Capability | SG | SEA | MY | ID | TH | PH | VN | US | UK | EU |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Curated jurisdiction pack registered | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Statute-cited suggestion rationales | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Local national-ID detector (NRIC / MyKad / NIK / etc.) | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Local company-ID detector (UEN / SSM / EIN / etc.) | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Local postal-address format | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **Universal PII rules** | | | | | | | | | | |
| `passport_number` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `email_address` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `phone_number` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `bank_account` / IBAN | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `named_person` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Universal MNPI rules** | | | | | | | | | | |
| `material_event` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `nonpublic_marker` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `transaction_codename` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `definitive_agreement` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `material_adverse_change` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `embargo_marker` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `financial_amount` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `financial_percentage` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `large_number` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

When a customer specifies a jurisdiction without a curated pack, the runtime falls through to a synthesised baseline pack named `{CODE}_PERSONAL_DATA_BASELINE` and `{CODE}_MNPI_BASELINE`. Universal rules still fire; jurisdiction-specific local-ID detection and statute-cited rationales do not. As of 2026-05-24, every SEA jurisdiction (SG / MY / ID / TH / PH / VN) and the Western set (US / UK / EU) ship a curated pack via items 19–20; the fall-through case now mostly applies to customers' bespoke codes.

## Expansion Sequence

Open work organised by theme. Shipped items are struck through and retained for traceability.

### Accuracy substrate

1. Grow the legal-contract fixture corpus from 6 → 30 docs using the OpenAI-backed `scripts/generate_legal_fixture.py`. Hand-validate before lock-baseline refresh. Push to 50 with adversarial + multilingual coverage as the second pass. *(Generator script shipped 2026-05-24; corpus growth still requires hand-review per generated doc.)*
2. ~~Land `test/fixtures/legal-corpus-adversarial/` plus `recall_adversarial.lock.json` so precision is a regression metric, not just recall. Adversarial fixtures cover NRIC in URLs, tables, ZWJ chars, OCR ligature artefacts, broken DOCX runs.~~ Shipped 2026-05-24 (seed: NRIC-in-URL, SG-multilingual, negative-prose). `scripts/recall_gate.py --corpus test/fixtures/legal-corpus-adversarial` enforces both `baseline_recall` and `baseline_precision` from `recall_adversarial.lock.json`. The two known precision gaps were closed the same day: `MAC_CLAUSE_RE` dropped its bare `MAC|MAE` alternation (consumer-product false positives), a 20-char `_is_negated_context` window suppresses "no MAC clause" / "without any MAC" / "not subject to MAE" patterns, and a `_suppress_redundant_phone_findings` post-pass drops `phone_number` findings whose span is fully covered by a higher-priority national-/company-ID detector (NRIC, UEN, MyKad, NIK, Thai national ID, PhilSys, TIN, CCCD, passport, bank account). Precision baselines now sit at 1.0 across all rules; 11 regression guards in `test_precision_guards.py` keep them there. Corpus growth to ZWJ / OCR-ligature / broken-DOCX variants is a follow-up.
3. ~~Per-document-type MNPI severity overrides mirroring `NAMED_PERSON_HIGH_SEVERITY_DOC_TYPES`. The `document_type` signal is already plumbed through `engine.review(...)`.~~ Shipped 2026-05-24. `MNPI_DOC_TYPE_SEVERITY_OVERRIDES` in `engine.py` softens `transaction_codename` / `definitive_agreement` / `material_adverse_change` to medium in casual prose, keeps high in `memo` / `research_note` / `external_memo`.
4. ~~UEN regex (legacy + T-format), legal-contract defined-term suppression, MNPI legal lexicon (`transaction_codename`, `definitive_agreement`, `material_adverse_change`, `embargo_marker`), 6-doc corpus seed, recall.lock baseline at 1.0 across 13 rules.~~ Shipped 2026-05-24.

### LLM-assisted runtime (server SKU, opt-in)

5. ~~OpenAI provider in `layer8_llm_adjudicator` behind `allow_remote_base_url=True`. Same `LocalLLMAdjudicator` interface; same privacy-guard discipline. Tenant-level opt-in flag.~~ Shipped 2026-05-24. Two distinct gates protect `provider=openai`: `allow_remote_base_url` is the deployer-level gate (remote URLs are permitted in general); `tenant_opt_in_openai` (env `KAYPOH_LLM_TENANT_OPT_IN_OPENAI`) is the tenant-level gate (this specific tenant has signed off on OpenAI). Both must be true. Checked twice — once at config-load (fail-fast `ConfigError`) and once at `adjudicate()` time (per-request defence so a hot-reload or harness mutation can't bypass). `provider` allowlist extended to `{vllm, ollama, openai, none}`. `vllm`/`ollama` paths are unaffected.
6. ~~LLM-assisted defined-term extraction at runtime — preamble-only pre-pass cached by document hash.~~ Shipped 2026-05-24. `src/kaypoh/review/llm_defined_terms.py` ships `extract_with_cache(text, extractor)` with PREAMBLE_CHAR_CAP=2000 and an on-disk cache at `${KAYPOH_JOURNAL_DIR}/llm_defined_terms/{doc_hash}.json`. Engine calls it only under `audit_grade`; extractor failures are swallowed.
7. ~~Two-tier engine: LLM advisory tier runs only on documents in the ambiguous score band. Never overrides a deterministic high.~~ Shipped 2026-05-24. `_llm_tier_engaged(review_profile, mnpi_score)` enforces three gates: profile=audit_grade, score in [LLM_TIER_MNPI_LOWER=25, LLM_TIER_MNPI_UPPER=70), and at least one of (public_evidence_retriever, llm_adjudicator, llm_coverage_auditor) wired. Documents outside the band skip the LLM call entirely.
8. ~~"What did we miss?" inverse audit emitting `coverage_warning` journal events.~~ Shipped 2026-05-24. `src/kaypoh/review/llm_coverage_audit.py` provides `run_coverage_audit()`; auditor receives only the privacy-safe summary (rule/severity/jurisdiction/reason) plus a SHA-256(body) reference — never `matched_text` or span offsets. Output surfaces on `ReviewResult.coverage_warnings` and journals one `coverage_warning` event per warning under the review session. Engine never acts on these.
9. ~~`audit_grade` review profile engaging all LLM steps; `strict` stays deterministic. Per-call billing.~~ Shipped 2026-05-24. `ReviewRequest.review_profile` validated against `^(strict|audit_grade)$`; engine raises ValueError on unknown profile. `strict` (default) short-circuits the entire LLM tier. `audit_grade` engages items 5 / 6 / 7 / 8 + public-evidence retrieval together.
10. ~~Local LLM adjudication and remote-LLM opt-in tested via `test/test_tinyfish_and_remote_llm.py::RemoteLLMOptInTests`.~~ Shipped 2026-05-24.
11. ~~Tinyfish public-source retrieval adapter against `GET https://api.search.tinyfish.ai/` with `X-API-Key`.~~ Shipped 2026-05-24.

### Round-trip + persistence

12. ~~Fuzzy entity linking for non-anchored variants — extend the linker to recognise bare surname references when an anchored honorific form is present elsewhere in the same document.~~ Shipped 2026-05-24. Pass 3 in `_named_person_findings`: trailing surname tokens from anchored multi-word names fire as `named_person` variants, suppressed if the surname matches a contract defined term.
13. ~~`POST /reidentify` + persistent per-document mapping store keyed by SHA-256 of the extracted text.~~ Shipped 2026-05-24.

### Audit-grade compliance

14. ~~Per-organisation `KAYPOH_JOURNAL_KEY` rotation with a versioned tenant-id → key mapping and a forward-compatible chain header (`prev_hmac`, `key_version`). Rotation events written as `journal_key_rolled` sentinels.~~ Shipped 2026-05-24. TOML keystore at `KAYPOH_JOURNAL_KEYS_FILE` carries `{active, keys.{version}.secret}`; each journal entry serialises with its `key_version` field; `verify_chain` resolves the HMAC key per-entry and reports `key resolution failed` when the version is missing. `rotate_journal_key(to_version, reason)` writes a `journal_key_rolled` sentinel sealed under the new active key. Legacy `KAYPOH_JOURNAL_KEY` flow stays byte-identical when no keystore is configured.
15. ~~Audit-pack reviewer roll-up: manifest summarises "decisions by reviewer X: accept N, reject M, rewrite K." Surfaces maker-checker violations where one reviewer approves their own decision.~~ Shipped 2026-05-24. `_build_reviewer_rollup` in `scripts/export_audit_pack.py` writes `reviewer_rollup` to the manifest and feeds it into `pack_hmac`.
16. ~~Reviewer attribution for `recall.lock.json` updates: actor + commit SHA + diff summary committed alongside lock changes so auditors can reconstruct *why* recall expectations changed.~~ Shipped 2026-05-24. `scripts/recall_gate.py --update` now requires `--reason` and appends `{ts, actor, commit_sha, reason, diff}` to `test/fixtures/legal-corpus/recall.lock.history.jsonl`. Actor resolves from `KAYPOH_RECALL_ACTOR` → `git config user.email` → `$USER`; commit SHA from `git rev-parse HEAD`.
17. ~~Reviewer-mandated wait period: optional `KAYPOH_AUDIT_MIN_WAIT_SECONDS` gate on `scripts/export_audit_pack.py` to surface batch-approval red flags.~~ Shipped 2026-05-24. The exporter emits `min_wait_status` / `min_wait_warning` in the manifest and exits `2` when the bound is violated; the pack itself remains HMAC-sealed.
18. ~~`POST /review/{id}/decision`, `GET /review/{id}`, HMAC-chained journal under `KAYPOH_JOURNAL_DIR`, audit-pack export+verify scripts. Reviewer identity threaded through schemas + endpoint + session view.~~ Shipped 2026-05-24.

### Jurisdiction breadth

19. ~~Migrate `src/kaypoh/review/jurisdictions.py` from a hardcoded dict to a `jurisdictions/*.toml` plugin directory so customers can bring their own packs.~~ Shipped 2026-05-24. Built-ins live in `src/kaypoh/review/jurisdictions_data/*.toml`; customers point `KAYPOH_JURISDICTION_PACKS_DIR` at an extra dir whose `*.toml` files override built-ins by `code`.
20. ~~Curated SEA packs: MyKad (MY), KTP/NIK (ID), Thai national ID (TH), PhilSys/TIN (PH), CCCD (VN). Each pack ships a local-ID recognizer, statute citations, and rule-level suggestion rationales. Driven by the same fixture-corpus + recall-gate discipline used for SG.~~ Shipped 2026-05-24 (seed). TOML schema extended with `[[recognizers]]` entries (compiled with case-insensitive regex by default; optional `capture_group` for prefix-anchored detectors); engine iterates `pack.recognizers` after the hardcoded SG block and dedup-on-span keeps overlapping packs clean. New rules: `my_mykad`, `id_nik`, `th_national_id`, `ph_philsys`, `ph_tin`, `vn_cccd`. Each pack adds a jurisdiction suffix to PII and MNPI rationale chains. Seed corpus at `test/fixtures/legal-corpus-sea/` (one fixture per jurisdiction) baselined at 1.0 recall + 1.0 precision in `legal-corpus-sea.lock.json`. Corpus growth to 30+ docs per jurisdiction and bare-digit (non-dashed) recognizer variants are follow-ups under item 1's discipline.
21. ~~Statute-citation override hook (`citations_override.toml`) so customers can substitute internal compliance policy citations without forking the engine. Keyed by `(rule, jurisdiction)`, consulted before the built-in dict.~~ Shipped 2026-05-24. `KAYPOH_CITATIONS_OVERRIDE` points at a TOML with `[pii.<rule>]` / `[mnpi.<rule>]` tables keyed by jurisdiction code (`SG`, `US`, …) or `default`; consulted before the built-in lookup and honours the low-severity softener.

### Distribution surface

22. Browser-extension MV3 thin client (chatgpt.com / claude.ai / gemini.google.com). Calls `127.0.0.1:8765/anonymize` on paste; retains `document_hash` client-side; one-click in-place re-identify after the LLM round-trip.
23. macOS code-signing + notarisation pipeline for the PyInstaller `kaypoh-local` binary.
24. Windows desktop build.
25. ~~Defined-term inheritance across linked documents within a review session: session-scoped suppression set carries SPA definitions into related-doc reviews.~~ Shipped 2026-05-24. `POST /review` and `POST /anonymize` accept `session_id`; engine merges previously-extracted terms for that session into the current document's defined-term set and persists the union to `${KAYPOH_JOURNAL_DIR}/sessions/{session_id}.json`. Module: `src/kaypoh/review/session_store.py`.
26. ~~`kaypoh-local` / `kaypoh-server` packaging split with `[project.optional-dependencies]`. Heavy deps moved to `server`. PyInstaller spec under `packaging/`. `test_local_sku_runtime.py` enforces the contract.~~ Shipped 2026-05-24.

### Privacy hardening

27. Structured-tokens-in/out runtime LLM mode for regulated tenants: send `{entity_id, context_window_hash, sanitised_query}` instead of raw text fragments. Stronger guarantee than redact-then-send.

### Continuous accuracy substrate (training)

These items target overall accuracy improvement on the LLM tier without changing the deterministic-engine contract. Every item gates on the existing recall + precision baselines in `test/fixtures/legal-corpus/recall.lock.json` and `test/fixtures/legal-corpus-adversarial/recall_adversarial.lock.json` — a trained artefact ships only when it meets or beats both.

29. **Cloud-adjudicator distillation → local student model.** Teacher: the cloud LLM wired in `layer8_llm_adjudicator` (OpenAI provider behind `allow_remote_base_url=True`). Student: a 1–3B param base (Qwen-1.5B / Phi-3-mini / Gemma-2B) LoRA-tuned on teacher verdicts. New directory `training/distillation/` carries (a) `teacher_collector.py` that runs the cloud adjudicator over `test/fixtures/legal-corpus/` + `legal-corpus-adversarial/` + generator-produced synthetic fixtures and writes a JSONL of `{text, deterministic_findings, teacher_verdict}`; (b) `distill_train.py` that LoRA-fine-tunes the chosen base on that JSONL with structured-JSON output supervision; (c) `eval_against_corpus.py` that gates on the existing precision/recall baselines. Drop-in deployment: register the student as `KAYPOH_LLM_PROVIDER=local_distilled` reusing the existing `LocalLLMAdjudicator` interface — no runtime contract changes. Eventual goal: bundle the student into the `kaypoh-local` PyInstaller spec so `audit_grade` works offline.

30. **Journal-driven preference tuning (DPO).** New module `training/journal_preference_export.py` reads the HMAC-chained journal (`KAYPOH_JOURNAL_DIR/journal.jsonl`), filters to `decision_recorded` events with an associated LLM verdict, and produces a sanitised JSONL of preference pairs (`accept` = chosen, `reject` = rejected). Sanitisation is the gating step: a `PrivacyGuard.sanitise_for_training()` pass strips matched-text spans, named-person tokens, and email/phone/NRIC values from rationales before export; every export emits a privacy-ledger entry. Trainer: standard DPO on the local student from item 29 (or directly on a local-only base if 29 hasn't shipped). Per-tenant fine-tunes are out of scope for v1 — the first release pools accepted/rejected pairs across all consenting tenants and produces a single shared-tenant model.

31. **Journal-trained severity calibrator.** Replace the hard-coded `MNPI_DOC_TYPE_SEVERITY_OVERRIDES` table with a small gradient-boosted-trees model (LightGBM or `sklearn.ensemble.GradientBoostingClassifier`) trained on `(rule, jurisdiction, document_type, context-feature-bag)` → reviewer-accepted severity, taken from `decision_recorded` events on findings whose decision was `accept` or `rewrite`. Scope is narrow: only medium ↔ low borderline; `high`-severity findings are not subject to ML adjustment (preserves deterministic-floor invariant). Lives under `training/severity_calibrator/` with `train.py` + `serve.py`; ships in `kaypoh-server` (adds `scikit-learn` to `[server]`); desktop SKU keeps the deterministic table. Activated per request via `review_profile=audit_grade` only.

32. ~~Escalation-threshold calibration for the two-tier engine~~ Shipped 2026-05-24. `scripts/calibrate_escalation_threshold.py` searches over `(LLM_TIER_MNPI_LOWER, LLM_TIER_MNPI_UPPER)` pairs, scoring each candidate on a weighted mix of precision, recall, escalation-rate (LLM cost proxy), and latency-score against any corpus directory. Includes shipped defaults as a baseline candidate so the report shows whether the recommendation actually improves over status quo. `--apply` writes the recommendation to `configs/runtime_calibrated.toml` for explicit opt-in by `configs/runtime.py` (engine continues to use compile-time defaults unless the file is wired). Default 50 iterations of random sampling over the 2-D band space; objective weights tunable via `--w-precision`, `--w-recall`, `--w-latency`, `--w-cost`. Lightweight — no model training, just hyperparameter search — and serves as the eval scaffolding that items 29–31 will plug into.

### Deferred

28. Rust or Go span engine — only after profiling shows deterministic extraction/replacement is the bottleneck. The current bottleneck is more likely model inference and document extraction than string replacement.
