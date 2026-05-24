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

Legal-contract MNPI surface is distinct from finance-comms MNPI and is detected separately:

- `transaction_codename` — `Project <CapitalizedName>` patterns, the canonical "before announcement" tell in deal memos. Intra-line regex so a stray newline doesn't pull adjacent paragraphs into the matched_text.
- `definitive_agreement` — Share Purchase Agreement / SPA / Shareholders Agreement / SHA / APA / MOU / LOI / Term Sheet. Existence of a binding deal document is itself MNPI pre-announcement.
- `material_adverse_change` — MAC clauses, MAE, "material adverse change". Price-sensitive.
- `embargo_marker` — Signing Date / Closing Date / Effective Date / Embargoed / Press Hold.

Defined-term suppression extends to MNPI for abbreviation-style rules (`definitive_agreement`, `material_adverse_change`) so a contract abbreviating itself as `"SPA"` or `"MAC"` does not trip its own meta-reference. `transaction_codename` and `embargo_marker` are not suppressed because the defined term is the substantive risk, not a meta-reference.

## LLM and Retrieval Policy

Local/open-weight LLMs can improve MNPI adjudication, but they should not replace deterministic evidence. Cloud LLM and cloud retrieval are allowed when they materially improve specificity or accuracy, and only when the privacy guard permits the outbound call and the privacy ledger records the decision. Offline-default is the desktop SKU stance, not a hard ceiling on the platform. The defensible pattern is structured adjudication:

- The review engine emits findings and sanitized public-evidence summaries.
- External retrieval providers may receive only sanitized entity/ticker/event/date queries, never private document text, exact offending spans, emails, phone numbers, NRIC/FIN/UEN values, or exact private financial values.
- Tinyfish is a first-class public-source retrieval target alongside Exa; the runtime ships a real adapter rather than the current stub at `layer7_public_evidence/inference.py`. Both providers go through the same `PrivacyGuard.check_external_query` gate.
- Local LLMs may receive private document text when served on loopback/private infrastructure. Remote LLM endpoints are allowed when explicitly opted in via `allow_remote_base_url`, with the same sanitisation discipline and ledger entry.
- The API exposes chain-of-evidence: findings, legal basis, suggestions, public evidence, matched sources, unverified claims, confidence, and privacy ledger.
- The API must not expose raw chain-of-thought. If a model is used, it returns short structured rationale fields.
- Suggestion rationales are statute-cited and lead with the matched text in quotes — for example, `"S1234567D" detected → PDPA s13 and PDPC NRIC Advisory (effective 31 Dec 2026): NRIC/FIN must not be ...`. Reviewers can forward the rationale verbatim to internal audit.

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

1. Harden SG PII recall and precision with adversarial fixture coverage. Land UEN regex (legacy `\d{8,9}[A-Z]` and new-format `T\d{2}[A-Z]{2}\d{4}[A-Z]`), legal-contract defined-term suppression parsed from the document's own definitions block, MNPI legal lexicon (`transaction_codename`, `definitive_agreement`, `material_adverse_change`, `embargo_marker`), and a curated legal-contract fixture corpus (~50 SPAs/NDAs/SHAs/term sheets with hand-labelled spans). Recall is gated in CI; PRs that drop recall fail. **Partially shipped 2026-05-24:** UEN regex, defined-term suppression, MNPI legal lexicon, 6-doc corpus seed, recall.lock baseline at 1.0 across 13 rules. Remaining: grow corpus from 6 → 50 documents, add adversarial OCR/multilingual fixtures.
2. ~~Add mandatory review-state APIs so users can approve, reject, or add findings before write-out. Persist decisions to a local append-only journal, HMAC-chained from a customer-held key, exportable as a signed audit pack for internal audit and MAS-style inspection.~~ **Shipped 2026-05-24:** `POST /review/{id}/decision`, `GET /review/{id}`, HMAC-chained journal under `KAYPOH_JOURNAL_DIR`, audit-pack export+verify scripts. Next: extend audit pack to include reviewer identity claims and per-organisation key rotation.
3. Add fuzzy entity linking for variants such as `Dr Jane Tan`, `Jane Tan`, `Tan`, and for corporate forms (`ACME Pte. Ltd.` ↔ `Acme` ↔ `the Company` ↔ defined-term references).
4. Ship `POST /reidentify` and persist per-document `{document_hash: mapping}` locally so the round-trip survives client restarts.
5. ~~Split packaging into `kaypoh-local` (offline-default desktop SKU) and `kaypoh-server` (full ML + retrieval + LLM stack). Same source tree, different extras and dep manifests.~~ **Shipped 2026-05-24:** `[project.optional-dependencies]` carries `local`, `server`, `dev`, `packaging`. Heavy deps moved to `server`. PyInstaller spec under `packaging/`. `test_local_sku_runtime.py` enforces the contract.
6. Expand jurisdiction packs from SG to SEA (MY/ID/TH/PH/VN), then US/UK/EU. Move `jurisdictions.py` from a hardcoded dict to a `jurisdictions/*.toml` plugin directory so customers can bring their own packs.
7. Local LLM adjudication for MNPI materiality and public-status review returns structured JSON evidence. Remote LLM endpoints are allowed when explicitly opted in via `allow_remote_base_url`, gated by `_is_private_or_local_base_url` and the privacy guard. **Tested 2026-05-24** via `test/test_tinyfish_and_remote_llm.py::RemoteLLMOptInTests`.
8. ~~Complete the Tinyfish public-source retrieval adapter (currently stubbed) and keep Exa in parity, both behind `PrivacyGuard.check_external_query`. Cloud retrieval is allowed when it materially improves specificity or accuracy.~~ **Shipped 2026-05-24:** real Tinyfish adapter against `GET https://api.search.tinyfish.ai/` with `X-API-Key`. Endpoint and API-key env (`TINYFISH_API_KEY`) auto-resolved per provider in `configs/runtime.py`.
9. Consider a Rust or Go span engine only after profiling shows deterministic extraction/replacement is the bottleneck. The current bottleneck is more likely model inference and document extraction than string replacement.

## Emerging Expansion Ideas

Captured during the 2026-05-24 work sessions. These are not yet committed to the sequence above; they are candidates for the next planning gate.

- **Per-organisation journal-key rotation.** Today `KAYPOH_JOURNAL_KEY` is a single global HMAC key. For multi-tenant deployments, key it per organisation with a versioned tenant-id → key mapping and a forward-compatible chain header (`prev_hmac`, `key_version`). Rotation cuts a "key roll" sentinel event into the journal.
- **Audit-pack reviewer roll-up.** Now that `Decision.reviewer_id` is persisted, the audit-pack manifest can summarise "decisions by reviewer X: accept N, reject M, rewrite K". Useful for the maker-checker pattern (no single reviewer can approve their own decisions).
- **Reviewer attribution for `recall.lock.json` updates.** When the legal-corpus baseline is deliberately bumped, log the actor + commit SHA + diff summary so an auditor can reconstruct why recall expectations changed.
- **Defined-term inheritance across linked documents.** Today defined-term suppression is per-document. SPA + ancillary disclosure schedules are usually a single corpus; a session-scoped suppression set would carry the SPA's `Purchaser`/`Vendor` definitions into related-doc reviews.
- **Per-document-type MNPI severity overrides.** Mirror the `NAMED_PERSON_HIGH_SEVERITY_DOC_TYPES` pattern for MNPI: a transaction codename in casual prose is `medium`; in an external memo it is `high`. The doc-type signal is already plumbed through `engine.review(...)`.
- **Statute-citation override hook.** Customers will want to substitute their internal compliance policy citations for the PDPA/SFA defaults. A `citations_override.toml` consulted before the built-in dict, keyed by `(rule, jurisdiction)`, gives BYO citation without forking the engine.
- **OCR + multilingual fixtures in the legal corpus.** SG contracts mix English with Mandarin, Bahasa Melayu, or Tamil names; PDFs are sometimes OCR'd with ligature artefacts. Adversarial fixtures here would tighten claimed recall for the harder cases compliance buyers actually face.
- **Reviewer-mandated wait period before audit-pack export.** Optional gate: `KAYPOH_AUDIT_MIN_WAIT_SECONDS` so an exported pack always includes ≥N seconds of journal history, surfacing reviewers who batch-approve in seconds (a maker-checker red flag).
- **Browser-extension thin-client shape.** The local daemon is ready; the extension is not. MV3 service worker hooks `paste` / `beforesend` events on chatgpt.com, claude.ai, gemini.google.com and rewrites the textarea via `POST http://127.0.0.1:8765/anonymize`. Document-hash retained client-side so a paired in-place re-identify after the LLM round-trip is one click.

## LLM-in-the-Loop: Synthetic Data + Runtime Reasoning

The team has an OpenAI API key available for two distinct workstreams:

1. **Offline / build-time:** generate synthetic data for training corpora and evaluation fixtures. Zero customer data involved.
2. **Online / runtime:** use a cloud LLM as a reasoning step for cases where deterministic rules underperform.

These are scoped independently because their privacy postures are different. The desktop SKU's offline-default stance applies only to the runtime path; the build-time path can use any cloud model the team chooses because it runs against synthetic / public inputs.

### Build-time uses (no privacy concerns; ship aggressively)

- **Synthetic legal-contract corpus generation.** Today the recall gate runs against 6 hand-labelled docs. The goal is 50 across SPA / NDA / SHA / term sheet / employment letter / employee handbook / disclosure schedule / side letter / engagement letter. OpenAI can generate adversarial variants with structured JSON sidecars (text + must_detect + must_not_detect spans) at ~$0.01/doc; one engineer-day shifts the corpus from "credible seed" to "buyer-defensible 50-doc benchmark." This is the single highest-leverage build-time use.
- **Negative-prose fixtures.** Generate documents that *look* like MNPI but aren't (`"the project status was discussed"` vs `"Project Status was greenlit"`). Drives precision metrics that today are implicit. Pair with a `must_not_detect` block.
- **Adversarial PII fixtures.** NRIC embedded in URLs, tables, with zero-width chars, OCR artefacts, broken DOCX runs. We can prompt the LLM to produce 200 obfuscated variants of the same 10 base spans and lock the engine's recall against that adversarial set in a separate `recall_adversarial.lock.json`.
- **Multilingual SG fixtures.** Generate Bahasa Melayu / Tamil / Mandarin name variants with the romanization SG contracts actually use, so we can stop relying on Anglo-only fixtures. Same for street addresses and business names.
- **Deal codename diversity.** 200 `Project <X>` codenames spanning real-world conventions (Greek letters, constellations, animals, abstract nouns) plus negatives (`project plan`, `the project timeline`). Hardens `TRANSACTION_CODENAME_RE` against false positives and confirms it catches the long tail.
- **Synthetic training set for the legacy classifier.** `src/kaypoh/workflow/layer4_classification/` still trains FinBERT-style risk + severity classifiers. `docs/json/batch*.json` is small. Synthetic batches with controlled label distribution would give the classifier head a much bigger surface to learn on. **Cost-benefit caveat:** the deterministic engine is now the primary product wedge; investing months in the classifier's accuracy is only worth it if a clear use-case (e.g. ambiguous-MNPI auto-triage) gets prioritised.
- **`generate_fixture.py` tooling.** A repo script that wraps the OpenAI call, validates the produced JSON against the corpus schema, and lands the result in `test/fixtures/legal-corpus/` (or `legal-corpus-adversarial/`). Hand-review remains mandatory before lock-baseline refresh.

### Runtime uses (privacy-gated; pick selectively)

The privacy stance is unchanged: private document text leaves the customer environment only when explicitly opted in. The existing `PrivacyGuard.check_external_query` + ledger discipline applies to every outbound LLM call. With that in place, the following are candidates:

- **MNPI materiality adjudication via OpenAI.** Today `layer8_llm_adjudicator` is local-only by default (loopback / private base URL). Adding OpenAI as a remote provider behind `allow_remote_base_url=True` is a one-day change. The adjudicator already returns structured JSON (`risk_label`, `public_status`, `materiality_reason`, `matched_public_sources`, `unverified_claims`) so the chain-of-evidence contract holds. Higher-quality reasoning than a self-hosted 20B model, at the cost of one outbound call per ambiguous case. **Recommended:** server SKU, off by default, opt-in per tenant.
- **LLM-assisted defined-term extraction.** Current regex catches `(the "Purchaser")` and `"Vendor" means …`. Real contracts also write `Acme (hereinafter referred to as "the Seller")`, `we will use "X" to refer to Y`, or `each of the Sellers (collectively, the "Sellers")`. An LLM pre-pass over just the contract preamble (~first 500 tokens) gives near-perfect recall on these patterns. The output is a list of defined terms → no private content leaves with the response, only the preamble enters. Treat as opt-in; cache by document hash.
- **Severity calibration on ambiguous findings.** Static `low|medium|high` per rule misses context. A named person in `"please cc Dr Jane Tan when convenient"` is low; in `"the Founder, Dr Jane Tan, owns 60% of Class A"` is high. Optional `severity_review` step that ships just the matched span + ±200-char window to a cloud LLM and returns a structured severity adjustment. Defaults bias toward stricter; LLM can only soften, never tighten beyond the deterministic floor.
- **Cross-document mapping inheritance.** Today the mapping store is hash-keyed per document. When a user processes a SPA followed by a disclosure schedule, an LLM could compare extractive entity lists and propose "these two share defined terms; merge mappings?" UX is one-click apply. Saves the user re-defining `Purchaser` 4× in a deal-room workflow.
- **"What did we miss?" inverse audit.** A complementary scan: send only the deterministic findings + a hash of the rest, ask the LLM "given these findings, what might the engine have missed?" Output goes into the journal as a `coverage_warning` event, *never* auto-acted-on. Useful as a CI signal against the legal corpus, and as an in-product nudge for compliance reviewers.
- **Rationale composition.** Today `citations.py` is templated. An LLM-generated rationale that quotes the matched span *and* the surrounding clause ("the matched NRIC appears in a beneficial-ownership disclosure clause; PDPA s13 applies and the recipient must be a documented data intermediary") is more forwardable than the template. Run only when the finding has been accepted, so the cost is bounded by the post-review path.
- **Two-tier engine.** The deterministic engine stays as the hot path and the source of truth for high-confidence findings; the LLM tier runs only on documents that score in an "ambiguous band" (e.g. PII findings present but MNPI score between thresholds). The LLM verdict is advisory only — it can raise the severity of an undecided finding, but it cannot suppress a deterministic high. Keeps latency bounded for the 90% case.

### Bold architectural shifts (worth debating)

These are the moves that would meaningfully change the shape of the product. Calling them out because the team said the architecture isn't locked.

- **Drop the legacy classifier from the product story; keep it as an experiment.** The `lexicon → embedding → clustering → model1 → model2 → mosaic → regression` pipeline carries most of the dependency weight (`torch`, `transformers`, `sentence-transformers`, `xgboost`, `scikit-learn`). The deterministic engine + LLM adjudicator covers the buyer-visible product surface (PII anonymisation, MNPI review). A bold move: keep the classifier endpoints alive for compatibility but stop investing in training; spend the cycles on the deterministic + LLM-adjudication path. Saves significant complexity in the server SKU and frees the `kaypoh-server` install size.
- **LLM-first defined-term extraction.** If a cloud LLM is allowed at build-time but not runtime, generate a "defined-term grammar" once per document type (SPA / SHA / NDA template language) and bake the patterns into the deterministic engine. Regex stays the runtime; the LLM is just a corpus-mining tool. This is a no-runtime-cost way to capture the long tail of defined-term variants.
- **Treat synthetic data as a first-class artefact.** `test/fixtures/legal-corpus-synthetic/` becomes a separate corpus alongside the hand-labelled gold set. Recall gate runs both; the gold set is the hard fail; the synthetic set is a precision/coverage metric. Generation script + manifest committed so reproducibility is preserved.
- **"Audit-grade" vs "fast-path" review profiles.** Today `review_profile` defaults to `strict`. A new `audit_grade` profile would automatically engage the LLM adjudicator + LLM-assisted defined-term extraction + LLM rationale composition; the `strict` profile remains deterministic only. Customers pay per audit-grade call. The deterministic profile remains the offline-default desktop story.
- **Privacy-preserving server SKU: structured tokens out, structured tokens in.** For runtime LLM use, never send raw text; send {entity_id, context_window_hash, sanitised_query}. The LLM operates on a constrained vocabulary the server has already validated. Stronger privacy guarantee than "we redact before sending"; harder engineering. Worth scoping if a regulated tenant requires it.
- **OpenAI gateway abstraction.** Add an OpenAI provider alongside vLLM / Ollama in `layer8_llm_adjudicator`, with `KAYPOH_LLM_PROVIDER=openai` and `OPENAI_API_KEY`. Same `LocalLLMAdjudicator` interface, same privacy-guard discipline. Treat OpenAI as just another remote provider that requires `allow_remote_base_url=True` plus a tenant-level opt-in flag.

### Where this lands in priority order

If the team agrees with the framing above, the recommended order is:

1. **Build-time synthetic corpus expansion** — highest ROI, zero privacy risk. Land `scripts/generate_legal_fixture.py` + grow the corpus from 6 → 30 docs in week one.
2. **Adversarial PII fixtures + recall_adversarial.lock baseline.** Locks precision as a regression metric, not just recall.
3. **OpenAI provider in `layer8_llm_adjudicator`** behind the existing remote-LLM flag. Server SKU only, off by default. Unlocks higher-quality MNPI adjudication for tenants who opt in.
4. **LLM-assisted defined-term extraction at runtime** for the server SKU only. Reuses the privacy ledger discipline.
5. **Two-tier engine** (deterministic + LLM-advisory) once #3 and #4 are stable.

Steps 1–2 move the accuracy story decisively. Steps 3–5 are server-SKU growth and depend on a customer asking for it. The desktop SKU stays untouched.
