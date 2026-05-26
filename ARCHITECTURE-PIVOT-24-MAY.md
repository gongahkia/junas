# Kaypoh Architecture Pivot - 24 May 2026

> Last revised 2026-05-26. Title date refers to the original pivot decision; the body is kept current as items ship.

## Decision

Kaypoh should be treated as a pre-send document safety layer first, not as a raw MNPI classifier. The core workflow is:

1. Extract inline text or text/DOCX/PDF content locally.
2. Detect PII and MNPI evidence with deterministic rules, jurisdiction packs, and optional LLM reasoning.
3. Return review findings, remediation suggestions, and scores.
4. For safe downstream analysis, produce deterministic placeholders and a local mapping table through `POST /anonymize`.

`POST /review` and `POST /anonymize` are the primary product surfaces. `POST /classify` is retained as a compatibility shim; the legacy `lexicon → embedding → clustering → model1 → model2 → mosaic → regression` pipeline is no longer the product wedge and the team does not invest in further training of that classifier stack. Investment goes into the deterministic engine, LLM-assisted reasoning, and — for accuracy recovery on the LLM tier — targeted distillation and preference-tuning (expansion-sequence items 29–32).

## Positioning and ICP

Kaypoh is a *narrow, defensible* pre-send safety layer for legal-corporate workflows where client/issuer confidentiality is a procurement blocker for GenAI adoption. It is **not** a horizontal DLP replacement. Microsoft Purview, Google Sensitive Data Protection, Netskope, and Nightfall already compete on detector breadth + infrastructure coverage; matching them is a multi-year investment with no defensible wedge. Kaypoh wins where those tools are weakest: SG/SEA-native local-ID + legal-MNPI detection, reversible local anonymisation, an HMAC-sealed reviewer-attributed audit trail, and an offline-default desktop SKU that survives an air-gapped review-board demo.

Initial ICP (priority-ordered):

- Singapore / SEA law firms experimenting with GenAI but blocked by client-confidentiality duty under PDPA + Legal Profession Act.
- Listed-company in-house legal and corporate-secretarial teams subject to SGX / Bursa / IDX / SET / PSE / HOSE continuous-disclosure rules.
- M&A, capital-markets, and PE deal teams pre-announcement.
- Investor-relations functions managing embargo windows.
- Corporate legal departments where ABA Formal Opinion 512 (or non-US equivalents) is being cited as a GenAI-adoption blocker.

Anti-positioning (claims kaypoh deliberately does **not** make):

- *Not* a general DLP. Endpoint coverage, network egress control, file-share scanning, SaaS posture management are out of scope.
- *Not* a legally conclusive MNPI classifier. Reg FD / MAR / SFA materiality is contextual; kaypoh surfaces *evidence* of MNPI for human review, not a regulatory determination.
- *Not* a public-status oracle. Public-status verification requires `audit_grade` + a configured public-evidence provider + sufficient entity context.
- *Not* a substitute for legal review. Reviewer attribution + maker-checker controls are scaffolding for human judgement, not a replacement for it.

### Why now / demand signals

The market timing is not "AI is popular"; it is that unsanctioned GenAI use has become a measurable data-loss vector while regulators are moving from principles into supervisory expectations. Evidence to keep current before external use:

- LayerX's 2025 GenAI reporting says organisations lacked visibility into 89% of enterprise GenAI usage, while its later Enterprise AI and SaaS Data Security Report says 77% of GenAI users pasted data into tools and about 40% of file uploads to GenAI sites contained PII/PCI. Sources: [LayerX Enterprise GenAI Security Report 2025](https://layerxsecurity.com/blog/layerxs-enterprise-genai-security-report-2025-exposing-hidden-ai-security-blind-spots/) and [LayerX Enterprise AI and SaaS Data Security Report 2025](https://go.layerxsecurity.com/hubfs/LayerX_Enterprise_AI_and_SaaS_Data_Security_Report.pdf).
- Cyberhaven's 2025 AI Adoption and Risk Report put sensitive data at 34.8% of enterprise data shared with AI tools, up from 10.7% two years earlier. Source: [Cyberhaven 2025 AI Adoption and Risk Report](https://www.cyberhaven.com/resources/lp-eb-ai-adoption-risk-report-2025).
- Netskope's 2026 Cloud and Threat Report says GenAI data-policy violations doubled year over year, with the average organisation seeing 223 incidents per month. Source: [Netskope Cloud and Threat Report 2026](https://www.netskope.com/resources/cloud-and-threat-reports/cloud-and-threat-report-2026).
- Gartner predicted in February 2025 that by 2027 more than 40% of AI-related data breaches would be caused by improper cross-border GenAI use. Source: [Gartner press release, 17 Feb 2025](https://www.gartner.com/en/newsroom/press-releases/2025-02-17-gartner-predicts-forty-percent-of-ai-data-breaches-will-arise-from-cross-border-genai-misuse-by-2027).
- Regulator posture is tightening in kaypoh's target jurisdictions: IMDA / AI Verify finalised the Model AI Governance Framework for Generative AI on 30 May 2024; OAIC guidance from 21 Oct 2024 recommends not entering personal information, especially sensitive information, into publicly available GenAI tools; APRA's 30 Apr 2026 AI letter calls for stronger AI risk management across regulated entities; MAS issued a Nov 2025 consultation on AI Risk Management Guidelines for financial institutions. Sources: [IMDA / AI Verify](https://www.imda.gov.sg/resources/press-releases-factsheets-and-speeches/factsheets/2024/gen-ai-and-digital-foss-ai-governance-playbook), [OAIC commercial AI guidance](https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/guidance-on-privacy-and-the-use-of-commercially-available-ai-products), [APRA AI letter](https://www.apra.gov.au/apra-letter-to-industry-on-artificial-intelligence-ai), [Baker McKenzie summary of MAS consultation](https://insightplus.bakermckenzie.com/bm/financial-services-regulatory/singapore-mas-publishes-consultation-paper-on-proposed-guidelines-on-ai-risk-management-for-financial-institutions).

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

SG legal/finance coverage should keep expanding in the wedge direction, not into generic DLP breadth. The backlog includes PayNow identifiers, MAS licence numbers, SGX stock codes and counter names, insurance policy numbers, crypto wallet addresses for MAS-regulated VASP workflows, court and tribunal references, IPOS registration numbers, ACRA filing references, HDB / strata / title references, URA / SLA references, and contract-commercial terms such as unit pricing, discounts, volume commitments, royalty rates, and total contract value. These are first-class because they appear in the documents the ICP actually wants to send into LLMs.

### Evaluation corpus posture

Synthetic data is a first-class artefact. `test/fixtures/legal-corpus/` is the default legal-contract corpus (118 fixtures as of 2026-05-26). `test/fixtures/legal-corpus-adversarial/` is the obfuscated / negative-prose / multilingual corpus (115 fixtures). `test/fixtures/legal-corpus-sea/` and `test/fixtures/legal-corpus-hk-au-jp-kr/` are seed jurisdiction corpora for MY / ID / TH / PH / VN and HK / AU / JP / KR respectively. `docs/accuracy.md` is generated from the committed lock files and is the public accuracy disclosure.

Adversarial and multilingual coverage matter because SG contracts mix English with Mandarin, Bahasa Melayu, and Tamil names, and PDF inputs come with OCR ligature artefacts and broken DOCX runs. The generation tooling at `scripts/generate_legal_fixture.py`, `scripts/generate_legal_fixture_batch.py`, `scripts/autolabel_fixture.py`, and `scripts/autolabel_batch.py` wraps the OpenAI API for build-time synthetic inputs only. Hand spot-checking remains mandatory before any model-derived label baseline is treated as procurement-grade.

The HK / AU / JP / KR seed corpus is **one fixture per jurisdiction** as of 2026-05-26 (4 fixtures total); recall/precision at 1.0 is trivially achievable at that volume and should not be read as population-level coverage. SEA seed corpus is similarly one fixture per jurisdiction (5 fixtures total). Item 86 follow-up + item 90/91 discipline grows each toward the 30-doc-per-jurisdiction target before the coverage claim hardens.

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

A **structured-tokens-in/out** runtime LLM mode is offered: instead of sending raw text fragments to the LLM, the server sends `{entity_id, body_hash, findings_summary, public_evidence_summary}` plus per-finding `context_window_hash` values, over a constrained vocabulary the server has already validated. Stronger privacy guarantee than redact-then-send. Activated by setting `llm.llm_input_mode = "structured_tokens"` (env `KAYPOH_LLM_INPUT_MODE`); local/private LLM endpoints keep `raw_text` as the default, while remote endpoints default to `structured_tokens`. Remote `raw_text` now requires both `KAYPOH_LLM_ALLOW_REMOTE_BASE_URL=1` and `KAYPOH_LLM_ALLOW_REMOTE_RAW_TEXT=1`. In structured mode the server clamps the LLM's response against a closed `STRUCTURED_REASONS` vocabulary, strips `matched_public_sources` and `unverified_claims` (potential leak channels), and surfaces `output_clamped: bool` on the adjudication response so an auditor can see how often the model attempted to emit free-form prose. Module: `src/kaypoh/workflow/layer8_llm_adjudicator/structured_query.py`.

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
- `POST /documents/scrub`: metadata scrubber for supported DOCX / PDF / JPEG / PNG payloads. Returns scrubbed base64, metadata findings found before scrubbing, scrub actions, and any remaining warnings.
- `POST /review/{review_id}/decision`: per-finding `accept | reject | rewrite` review-state mutations, persisted to the append-only HMAC-chained journal at `${KAYPOH_JOURNAL_DIR:-./kaypoh-journal}/journal.jsonl`. Gated by `KAYPOH_REVIEW_PERSIST=1`. Decisions carry `reviewer_id` sourced from the `X-Reviewer-ID` header (header takes precedence over body).
- `GET /review/{review_id}`: replay the journal for a session and return findings merged with their latest decision; surfaces `decisions_recorded`, `decision_reviewer_id` per finding, and audit-export references.
- `POST /classify` and `POST /classify/batch`: programmatic compatibility surface over `engine.review()`; legacy classifier fields remain `null`.
- `GET /health`, `/ready`, `/diagnostics`, `/metrics`: operational surfaces.

Audit-pack tooling: `scripts/export_audit_pack.py` produces HMAC-sealed ZIPs; verification via `scripts/verify_audit_pack.py` and whole-journal integrity via `scripts/verify_journal.py`. Shipped extensions: reviewer roll-up in the manifest (decisions by reviewer X: accept N, reject M, rewrite K — surfaces maker-checker violations), the optional `KAYPOH_AUDIT_MIN_WAIT_SECONDS` gate that surfaces batch-approval red flags (exit code `2` on violation, pack still HMAC-sealed), and per-organisation `KAYPOH_JOURNAL_KEYS_FILE` rotation: each entry serialises with its `key_version`, `verify_chain` resolves keys per-entry, and `rotate_journal_key(to_version, reason)` writes a `journal_key_rolled` sentinel sealed under the new active key. Recall-baseline changes (`recall.lock.json`) are similarly attributable: actor + commit SHA + diff summary committed alongside the lock so an auditor can reconstruct *why* recall expectations changed.

### Format gate posture

Document ingest fails closed when the PDF extractor cannot prove it has a reliable text layer. Scanned PDFs, image-only PDFs, and uncertain PDFs are rejected with conversion guidance instead of best-effort OCR. The gate uses text-layer density, empty-page ratio, embedded-image signals, and scanner/producer metadata. Text-layer PDFs still pass, but image-bearing PDFs surface extraction warnings because only the text layer has been reviewed. False confidence is worse than a blocked upload in this category.

### Distribution shape

- `kaypoh-local` (`pip install kaypoh[local]`): offline-default desktop SKU. Deterministic engine + Presidio + spaCy + extractors only. No `torch`, `transformers`, `sentence-transformers`, `redis`, `xgboost`, `scikit-learn`, `pandas`, or `accelerate`. Bundles `en_core_web_sm` via the PyInstaller spec at `packaging/kaypoh-local.spec`. The entrypoint at `packaging/kaypoh_local_entrypoint.py` binds 127.0.0.1:8765 by default. Browser extensions, mail plugins, and Slack/Outlook hooks are thin clients of the local daemon on `127.0.0.1`.
- `kaypoh-server` (`pip install kaypoh[server]`): deterministic API server plus opt-in public-evidence retrieval (Exa, Tinyfish, Serper, SerpAPI) and local/remote LLM adjudication (vLLM, Ollama, OpenAI). Cloud opt-in flows live here. The legacy classifier and mosaic stack are archived, not part of the active server runtime. Runtime packaging is UV-first (`uv.lock`) and Docker-capable (`Dockerfile`, `docker-compose.yml`).
- Enterprise `kaypoh-server` deployment modes are future packaging shapes, not replacements for the desktop wedge. Default enterprise posture is a customer-managed appliance: VM/container deployed inside the customer's own environment, operated by the customer's platform team, with customer-held keys and no kaypoh access to content. A later premium BYOC managed-service option may let kaypoh operate the appliance health/upgrade plane only; the customer still owns root credentials, data keys, content, vault, and audit logs. For accuracy-first managed deployments where Kaypoh supplies the LLM/search keys, `docker-compose.managed-llm.yml` enables `public_evidence,llm_adjudicator` with remote `structured_tokens` and still requires a tenant opt-in flag before any provider key is used.
- Both SKUs share `src/kaypoh/` and the same wire contracts. Splitting is a packaging concern, not a fork. `test/test_local_sku_runtime.py` blocks every server-only module via `sys.modules[name] = None` and proves the local SKU still boots and round-trips through `anonymize → reidentify`.

The browser-extension thin client (planned) is an MV3 service worker hooking `paste` / `beforesend` events on chatgpt.com, claude.ai, gemini.google.com. Rewrites the textarea via `POST http://127.0.0.1:8765/anonymize`. Document hash retained client-side so the paired in-place re-identify after the LLM round-trip is one click.

### Deprecated product assumptions

- Archived HTML demo frontends are not active runtime surfaces.
- The old classifier-only framing is not the product architecture. `/classify` and `/classify/batch` are compatibility-only; investment goes into the deterministic engine, LLM-assisted reasoning, and LLM-tier distillation / preference-tuning.
- Model confidence alone is not sufficient for a defensible MNPI decision.
- "Strict offline, full stop" is not the platform stance. Offline-default applies to the desktop SKU; cloud is allowed elsewhere when it improves specificity or accuracy and the privacy guard permits it.

### Known gaps as of 2026-05-26

The current `/review` path is deliberately conservative and deterministic. PII coverage is not yet a general semantic personal-data engine: broad address parsing, DOB/age, online/device identifiers, health/biometric special-category data, US SSN / driver-license / EIN, UK NI, EU member-state ID breadth, and non-honorific name detection are not fully implemented. Jurisdiction-local direct identifiers now cover SG / SEA seed packs plus HK / AU / JP / KR seed packs, but those newer packs are seed-scale and do not yet include local postal-address recognizers. SG legal/finance sensitive-data coverage has a first shipped slice (`sg_court_citation`); PayNow IDs, MAS licence numbers, SGX counter identifiers, IPOS / ACRA filing references, property-title references, and richer commercial-term detectors remain backlog items.

MNPI coverage detects evidence of material events, non-public markers, legal-contract signals, and exact scalars; it still does not prove legal materiality or public status by default. Public-status verification requires the `audit_grade` tier plus configured public-evidence provider credentials and enough entity context to form a privacy-approved query. Contingent / probabilistic MNPI, tipping language, selective-disclosure markers, blackout-window reasoning, sector-specific packs, and HK's narrower "not generally known" semantics remain open.

Some LLM surfaces are scaffolded or injectable rather than fully production-wired runtime layers. LLM-defined-term extraction and inverse coverage audit exist, but they are not first-class configured layers with readiness/diagnostics parity. Rationale composition and journal-trained severity calibration are roadmap items. Remote raw-text LLM mode can still send document text, but only after the explicit remote-URL gate and explicit remote-raw-text gate are enabled; remote endpoints otherwise default to `structured_tokens`.

Evaluation is broader but still seed-scale for non-SG jurisdictions: `docs/accuracy.md` publishes locked baselines over 118 default, 115 adversarial, 5 SEA, and 4 HK/AU/JP/KR fixtures. Persistence remains confidentiality-sensitive: HMAC protects journal integrity, mapping records can be Fernet-encrypted when `KAYPOH_MAPPING_STORE_KEY` is configured, and matched-text journal payloads remain plaintext unless the deployment adds separate encryption, access control, and retention policy. Mapping persistence is still best-effort on `/anonymize`; item 65 remains open because a store write failure logs/returns the inline mapping instead of refusing the request.

Document metadata leakage review/scrub now exists for DOCX core/app/custom properties, DOCX comments, DOCX track-change author/date/initials, PDF info metadata, and JPEG/PNG EXIF when optional dependencies are installed. Remaining document-safety gaps are the broader container/binary surfaces: embedded binaries, hidden Office content, PDF annotations/forms/XMP/embedded files, XLSX pivot caches, PPTX notes/masters, EML/MSG attachments, archives, HTML/SVG/RTF/Markdown hidden text, and image OCR.

### Enterprise readiness self-assessment (2026-05-26)

Honest scoring across procurement-relevant dimensions. Each row maps to expansion items that close the gap; refusing to score a dimension is dishonest, and the 2/10 line is on purpose.

| Dimension | Rating | Closing items / posture |
|---|:---:|---|
| Narrow legal/finance pilot value (SG/APAC) | 8/10 | SG/SEA + HK/AU/JP/KR direct-ID seed packs, reversible anonymisation, metadata scrub, accuracy disclosure; corpus depth and integrations still limit scale (1, 40, 44, 45) |
| Broad enterprise DLP replacement | 2/10 | **out of scope** — see anti-positioning |
| Compliance-grade PII accuracy | 5/10 | direct-ID coverage materially improved; broad PII, semantic names, addresses, DOB/age, online IDs, and special-category data remain (33, 34, 35, 40, 70, 71, 78, 79) |
| MNPI decision reliability | 5/10 | deterministic legal-MNPI rules + source-verification states are useful; contingent/tipping/selective-disclosure/blackout/sector gaps remain (72–85) |
| Auditability | 7/10 | shipped (14–18, 36, 46); reviewer identity binding (57), bounded rationale (38), defensibility export (89) lift this further |
| Security / procurement readiness | 6/10 | mapping encryption/retention, tenant isolation/RBAC, deployment hardening, and SIEM shipped (41–43); reviewer identity binding, local-daemon ACL, subject erasure, per-tenant citations, and workflow-wide fail-closed remain (57–60, 65) |
| Distribution / integration coverage | 4/10 | Docker/Compose server path exists (51 partial); browser extension, Office add-ins, DMS connectors, clipboard/file-watcher, macOS notarisation, and Windows build remain (22–24, 44, 45, 47) |
| Pre-send document safety completeness | 7/10 | metadata review/scrub + fail-closed PDF ingest shipped (49, 50); SG wedge pack, container recursion, image OCR, and fail-closed meta-audit remain (48, 61, 64, 65) |
| Enterprise appliance / BYOC operability | 5/10 | deterministic Docker image and managed-LLM overlay exist (51 partial); no full appliance runbook, upgrade/backup story, external KMS integration, or customer-held ops-plane separation yet |
| Product differentiation | 8/10 | reversible local anonymisation + APAC legal-MNPI/direct-ID angle + HMAC audit trail hold; breadth remains intentionally narrower than DLP incumbents |

The 2/10 on "broad enterprise DLP replacement" is intentional. The 8/10 on "narrow legal/finance pilot value" is the wedge; it is not a claim of general compliance-grade coverage.

## Jurisdiction Coverage

Snapshot of detection capabilities by jurisdiction as of 2026-05-26. ✓ = available today; △ = partially available or available only under explicit configuration / opt-in; ✗ = not yet implemented. Universal rules fire regardless of jurisdiction pack; jurisdiction-specific rules and statute citations require a curated pack.

| Capability | SG | SEA | MY | ID | TH | PH | VN | HK | AU | JP | KR | US | UK | EU |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Curated jurisdiction pack registered | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Statute-cited suggestion rationales | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Local personal/government-ID detector | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Local company/tax-ID detector | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Local postal-address format | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Broad postal-address parser (multi-line / free-form) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| SG legal/finance sensitive-data pack | △ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **Universal PII rules** | | | | | | | | | | | | | | |
| `passport_number` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `email_address` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `phone_number` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `bank_account` / IBAN [^bank-adv] | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `named_person` (honorific-anchored + linked variants) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| General semantic PII model / NER fallback in `/review` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| DOB / age detector | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| IP / device / online identifier detector | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Health / biometric special-category detector | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| US SSN / driver-license detector | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| UK NI / EU member-state national-ID detector | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **Universal MNPI rules** | | | | | | | | | | | | | | |
| `material_event` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `nonpublic_marker` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `transaction_codename` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `definitive_agreement` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `material_adverse_change` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `embargo_marker` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `financial_amount` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `financial_percentage` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `large_number` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Source-verified public-status adjudication by default | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `audit_grade` public-evidence adjudication | △ | △ | △ | △ | △ | △ | △ | △ | △ | △ | △ | △ | △ | △ |

[^bank-adv]: `bank_account` is shipped as a universal recognizer in `engine.py` (`BANK_ACCOUNT_RE`), but its adversarial-corpus recall is locked at 0.0 ("not locked") in `recall_adversarial.lock.json` as of 2026-05-26. Detector is available; adversarial precision/recall baselines have not been hand-locked yet. Item 40 corpus discipline closes this.

When a customer specifies a jurisdiction without a curated pack, the runtime falls through to a synthesised baseline pack named `{CODE}_PERSONAL_DATA_BASELINE` and `{CODE}_MNPI_BASELINE`. Universal rules still fire; jurisdiction-specific local-ID detection and statute-cited rationales do not. As of 2026-05-26, SG / SEA / MY / ID / TH / PH / VN / HK / AU / JP / KR / US / UK / EU ship curated packs. The fall-through case mostly applies to bespoke customer codes. The HK / AU / JP / KR packs are useful but seed-scale: they ship direct personal/company identifiers and statutes, not full local address or jurisdiction-specific MNPI language coverage. The US / UK packs ship direct government-ID recognizers (SSN + EIN + NIN) added 2026-05-26 with checksum/prefix validators; broader US sectoral coverage (driver-license, ITIN, state-DLN) and EU member-state national IDs remain item 33 backlog.

Operational hardening coverage as of 2026-05-26:

| Capability | Status |
|---|:---:|
| HMAC-chained review journal integrity | ✓ |
| Journal key rotation | ✓ |
| Encrypted local mapping-store option | ✓ |
| Mapping retention / purge tooling | ✓ |
| Mapping-store ACL / at-rest encryption guidance | ✓ |
| Multi-tenant request isolation (server SKU) | ✓ |
| JWT/API-key tenant auth + RBAC | ✓ |
| SSO / production IdP packaging (Okta / Azure AD / SAML) | △ |
| SIEM export (JSON-over-syslog) | ✓ |
| Per-detector recall + precision published in `docs/accuracy.md` | ✓ |
| Document metadata leakage review/scrub | ✓ |
| Fail-closed scanned-PDF / uncertain-format gate | ✓ |
| Workflow-wide `degraded_modes` / fail-closed all layers | ✗ |
| Enterprise appliance / BYOC deployment posture | △ |
| Reviewer identity bound to authenticated principal | ✗ |
| Local-daemon production ACL | ✗ |
| Subject-erasure reverse index | ✗ |
| Per-tenant citation override files | ✗ |

### Coverage gaps → expansion-item map

The map below distinguishes product-critical gaps with explicit closing items from breadth gaps that stay out of scope until promoted into the roadmap.

| Capability gap | Closing item(s) |
|---|---|
| Local personal/government-ID detector gaps for US / UK / EU | 33 |
| Local company/tax-ID parity outside shipped packs | 33 for US EIN; future jurisdiction-pack follow-up before any UK/EU/SEA company-ID coverage claim |
| HK / AU / JP / KR local postal-address formats | 86 follow-up + 34 |
| Broad postal-address parser (multi-line) | 34 |
| General semantic PII / NER fallback in `/review` | 35 |
| SG legal/finance sensitive-data pack beyond `sg_court_citation` | 48 |
| DOB / age detector | 33 |
| IP / device / online identifier detector | 33 |
| Health / biometric special-category detector | 33 (conservative seed) + 40 (corpus lock) |
| US SSN / driver-license detector | 33 |
| UK NI / EU member-state national-ID detector | 33 |
| Source-verified public-status adjudication by default | 36 shipped explicit proof states; default-on retrieval remains intentionally off outside `audit_grade` |
| SSO/Okta/Azure AD/SAML packaging on top of JWT/RBAC primitive | 42 |
| Enterprise appliance / BYOC deployment posture | 51 |
| Reviewer identity binding | 57 |
| Local-daemon ACL | 58 |
| Subject-erasure reverse index | 59 |
| Per-tenant citation overrides | 60 |
| Binary/container coverage | 61 |
| Image OCR / recognition | 64 |
| Workflow-wide fail-closed / degraded-mode audit | 65 |

## First-Principles Statutory Analysis

The deterministic engine's defensibility derives from anchoring every detector to a statutory or regulatory concept. This section enumerates each in-scope jurisdiction's PII and MNPI / insider-information definitions, maps current detector coverage against them, and surfaces gaps as actionable expansion items. Treat this as the authoritative source for the planned `docs/statutory-coverage.md` (item 69).

Citations below are sourced from official statutes, regulator guidance, and authoritative commentary as of 2026-05-26. Item 53 keeps these citations current before any external use.

> [Unverified] Statute section numbers in the tables below (notably SG SFA s215/s218/s219/s221, HK SFO Cap. 571 Part XIV s270-281, JP FIEA Art 166-167, KR FSCMA Art 174-179) are reproduced from public commentary and not re-checked against the primary statute text on every doc edit. Before any external use of these citations (procurement pack, defensibility report, customer-facing rationale), re-verify against the official statute revision in force as of the use date. Item 53 owns this cadence; item 88 (regulator-update watcher) automates it.

### PII / personal data — by jurisdiction

| Jurisdiction | Statute / source | Definition pivot | Reach |
|---|---|---|---|
| **Singapore (SG)** | PDPA 2012 s2(1); PDPC Advisory Guidelines on Key Concepts (rev 2024) | "data, whether true or not, about an individual who can be identified from that data; or from that data and other information to which the organisation has or is likely to have access" | Very wide: "or is likely to have access" pulls in quasi-identifiers and contextual combinations |
| **Malaysia (MY)** | Personal Data Protection Act 2010 s4 (as amended 2024) | "any information that relates directly or indirectly to a data subject, who is identified or identifiable" | "Directly or indirectly" + statutory list of sensitive personal data |
| **Indonesia (ID)** | UU PDP No. 27/2022 Art 1, Art 4 | "data about an identified or identifiable natural person, alone or combined with other information" | General + 7-category specific personal data (health, biometric, genetic, etc.) |
| **Thailand (TH)** | PDPA B.E. 2562 (2019) s6 | "any information relating to a Person, which enables the identification of such Person, whether directly or indirectly" | Sensitive personal data per s26 (race, religion, biometric, health) requires explicit consent |
| **Philippines (PH)** | Data Privacy Act 2012 (RA 10173) s3(g)(h) | "any information from which the identity of an individual is apparent or can be reasonably and directly ascertained, or when put together with other information would directly and certainly identify an individual" | Distinguishes personal information from sensitive personal information (s3(l)) |
| **Vietnam (VN)** | Decree 13/2023/ND-CP Art 2 | "information in the form of symbols, letters, numbers, images, sounds or similar forms in electronic environment that is associated with a specific person or helps to identify a specific person" | Basic + sensitive (10 categories including health, sex life, financial accounts) |
| **Hong Kong (HK)** | Personal Data (Privacy) Ordinance (Cap. 486) s2(1); PCPD guidance | Data relating directly or indirectly to a living individual, where identity is directly or indirectly ascertainable and access/processing is practicable | "Practicable" narrows the reach versus GDPR-style "reasonably likely" tests, but HKID and matter/counterparty records are plainly covered |
| **Australia (AU)** | Privacy Act 1988 (Cth) s6(1); OAIC APP guidance | "information or an opinion about an identified individual, or an individual who is reasonably identifiable" | Broad and context-dependent; includes opinions, inferred facts, TFNs, health, credit, employee-record contexts, and sole-trader/business overlap |
| **Japan (JP)** | APPI Art 2; My Number Act | Information about a living individual that identifies a specific individual, including information readily collated with other information, plus individual identification codes | My Number / Individual Number is a restricted identifier; APPI also recognises special care-required personal information |
| **Korea (KR)** | Personal Information Protection Act Art 2; Art 24 / 24-2 identifier controls | Information relating to a living individual that identifies the individual directly or when combined with other information | Resident registration numbers are high-control identifiers; sensitive information and personally identifiable information have separate handling limits |
| **United States (US)** | CCPA/CPRA Cal. Civ. Code §1798.140(v); HIPAA 45 CFR §164.514; GLBA "non-public personal information" | "information that identifies, relates to, describes, is reasonably capable of being associated with, or could reasonably be linked, directly or indirectly, with a particular consumer or household" | Patchwork: CCPA + state laws + sectoral (HIPAA / GLBA / FERPA / COPPA); SSN is a federal flashpoint via various statutes |
| **United Kingdom (UK)** | UK GDPR Art 4(1); DPA 2018 s3(2) | "any information relating to an identified or identifiable natural person ('data subject')" | "All means reasonably likely to be used" (Recital 26 retained) |
| **European Union (EU)** | GDPR Art 4(1); Recital 26 | identical to UK GDPR | Plus Art 9 special-category (health, biometric, genetic, sex life, religion, racial/ethnic origin, political opinion, trade-union membership) |

**Common doctrine across jurisdictions:**

- *Identifiability is a spectrum, not a binary.* "Reasonably likely to be used" (GDPR Recital 26 / UK / EU) and "is likely to have access" (PDPA SG) explicitly cover indirect identification.
- *Quasi-identifier combinations are PII.* Sweeney 2000: DOB + 5-digit ZIP + gender uniquely identifies ~87% of US adults. No single attribute is PII; the combination is.
- *Special-category data triggers a separate consent regime.* GDPR Art 9, PDPC special-category, PIPA "sensitive information", LGPD Art 5(II), APPI "special care-required", DPDPA "sensitive personal data" all require explicit / heightened consent and stricter handling.
- *Pseudonymised but linkable data remains personal data.* GDPR Recital 26 explicit; PDPC Advisory Guidelines on Anonymisation similar.

**What kaypoh currently catches (against these definitions):**

The deterministic engine fires on **statute-named direct identifiers**: NRIC/FIN, UEN, MyKad, NIK, Thai national ID, PhilSys, PH TIN, CCCD, HKID, HK CR No., AU TFN / ABN / ACN, JP My Number / corporate number, KR RRN / business registration number, passport, email, phone, bank/IBAN, named person (honorific-anchored + linked variants), SG postal-address, and SG court-citation. These are unambiguously personal-data or matter-identifying signals in the jurisdictions above. The non-SG jurisdiction packs are still seed-scale and should not be sold as population-level coverage.

**What kaypoh currently misses (gaps surfaced by definitions):**

| Statutory concept | Detection gap | Closing item |
|---|---|---|
| Quasi-identifier combinations (PDPA + GDPR + CCPA reach) | No multi-attribute reasoning | **Item 70** |
| Special-category data (GDPR Art 9, PDPC special-cat, PIPA, LGPD, APPI, DPDPA) | No health / biometric / sex life / religion / political opinion / trade-union detectors | **Item 71** |
| Pseudonymised-but-linkable IDs | No employee-ID, customer-account-number, internal-session-ID detectors | **Item 78** (new — below) |
| Date of birth / age | No detector | **Item 33** |
| IP address / device identifier | No detector | **Item 33** |
| US SSN, driver-license, EIN | No detector | **Item 33** |
| UK NI, EU member-state national ID | No detector | **Item 33** |
| Broad postal-address parsing | SG-only postal-code signal | **Item 34** |
| Free-form named persons (no honorific) | Honorific-anchored only | **Item 35** (semantic fallback) |
| Inferred attributes (relationship, location) | No inference layer | **Item 79** (new — below) |
| HK / AU / JP / KR local postal-address patterns | Seed packs cover direct ID/company ID only | **Item 86** follow-up + **Item 34** |

### MNPI / insider information — by jurisdiction

| Jurisdiction | Statute / source | "Material" pivot | "Non-public" pivot |
|---|---|---|---|
| **Singapore (SG)** | SFA s218 (insider trading), s219 (tipping), s221 (penalty); MAS Disclosure of Interests; SGX Mainboard / Catalist Rules ch 7 | "information that is not generally available but, if it were generally available, a reasonable person would expect it to have a material effect on the price or value" of securities | "generally available" — limbs in s215 |
| **Malaysia (MY)** | Capital Markets and Services Act 2007 s183-198; Bursa Listing Requirements ch 9 | "information that on becoming generally available, a reasonable person would expect to have a material effect on the price or value of securities" | "generally available" per s184 |
| **Indonesia (ID)** | UU Pasar Modal No. 8/1995 Art 95-99; OJK Reg 31/POJK.04/2015 | "material information that has not been made public and that may influence investor decisions or the price of securities" | "has not been disclosed to the public" |
| **Thailand (TH)** | Securities and Exchange Act B.E. 2535 s241-244 (insider trading); SEC Notification TorChor.1/2566 | "information that has not been disclosed to the public which, if disclosed, may have a material effect on the price of securities" | "has not been disclosed to the public" |
| **Philippines (PH)** | Securities Regulation Code (RA 8799) s27; SEC Memorandum Circular No. 11 s.2019 | "material non-public information... [information] which would have been considered important by a reasonable investor in making investment decisions" | "is not generally available to the public" |
| **Vietnam (VN)** | Law on Securities 2019 Art 11, Art 124; Decree 155/2020/ND-CP | "information about an issuer or about securities not yet made public that, if made public, would have a significant impact on the price of securities" | "not yet made public" |
| **United States (US)** | Securities Exchange Act 1934 s10(b); SEC Rule 10b-5; Reg FD (17 CFR 243.100); SEC v. Texas Gulf Sulphur (1968); Basic v. Levinson (1988) | "substantial likelihood that a reasonable shareholder would consider it important in deciding whether to buy, hold, or sell" — Basic v. Levinson | "not disclosed in a manner sufficient to ensure broad, non-exclusionary distribution" — Reg FD |
| **United Kingdom (UK)** | UK Market Abuse Regulation (UK MAR) Art 7; Criminal Justice Act 1993 s56 | "information of a precise nature, which has not been made public, relating, directly or indirectly, to one or more issuers... and which, if it were made public, would be likely to have a significant effect on the prices" | "not been made public" — limbs in UK MAR Art 7(1)(a) |
| **European Union (EU)** | EU Market Abuse Regulation 596/2014 Art 7; MAR Art 14 (prohibition); MAR Art 17 (disclosure obligation) | identical to UK MAR (UK MAR is post-Brexit copy) | identical |
| **Hong Kong (HK)** | Securities and Futures Ordinance (Cap 571) Part XIV s270-281; SFC Inside Information Guidelines (2012) | "specific information about... a corporation... which is not generally known to the persons who are accustomed or would be likely to deal in the listed securities... but would if generally known to them be likely to materially affect the price" | "not generally known" — note this is a *narrower* test than "not generally available" |
| **Australia (AU)** | Corporations Act 2001 s1042A-1043O; ASIC Regulatory Guide 62 | "information that is not generally available and, if the information were generally available, a reasonable person would expect it to have a material effect on the price or value of financial products" | "generally available" |
| **Japan (JP)** | Financial Instruments and Exchange Act Art 166-167 (insider trading); JFSA Cabinet Office Order | "material fact" enumerated in specific decisions / occurrences / financial-results criteria, not yet publicly disclosed | "publicly disclosed" per Art 166 |
| **Korea (KR)** | Financial Investment Services and Capital Markets Act (FSCMA) Art 174-179; FSC Enforcement Decree Art 201 | "important information... not yet publicly disclosed" | "publicly disclosed" |

**Common doctrine across jurisdictions:**

- *Materiality is contextual to issuer size and circumstance.* SEC Staff Accounting Bulletin No. 99 explicit. A $1M impact on a $10M company is material; on a $100B company, immaterial. **No jurisdiction in the table above defines a fixed numerical materiality threshold** — every regime is a "reasonable investor" / "significant effect" test.
- *Non-public is "not generally available" in most jurisdictions, but HK's "not generally known" is narrower.* Information *available* but not *known* by the target audience still triggers HK's regime.
- *MNPI is forward-looking and probabilistic.* Basic v. Levinson sets a "magnitude × probability" test for contingent / future events (e.g. merger negotiations). A discussion that's only 30% likely to close can still be MNPI if the deal would be massive.
- *Selective disclosure to analysts / institutional holders triggers obligations.* Reg FD (US) is the canonical example; MAR Art 17 (EU/UK) similar.
- *Tipping liability is co-extensive with trading liability.* SFA s219 (SG), Rule 10b5-2 (US), MAR Art 14 (EU/UK) — passing the information on to someone who *might* trade is itself the offence.

**What kaypoh currently catches (against these definitions):**

The MNPI lexicon detects **deal-stage and corporate-event tells**: `transaction_codename` (Project <CapitalizedName>), `definitive_agreement` (SPA/SHA/APA/MOU/LOI/Term Sheet), `material_adverse_change` (MAC/MAE), `embargo_marker` (Signing/Closing/Effective Date), `material_event` (broad), `nonpublic_marker` (broad), `financial_amount`, `financial_percentage`, `large_number`. Plus source-verification states (item 36) and `audit_grade` public-evidence retrieval.

**What kaypoh currently misses (gaps surfaced by definitions):**

| Statutory / doctrinal concept | Detection gap | Closing item |
|---|---|---|
| Issuer-relative materiality (SAB No. 99, MAR "significant effect") | Severity is uniform regardless of entity size | **Item 73** |
| Cross-document materiality (SEC v. Texas Gulf Sulphur — pieces individually noise, together MNPI) | Per-doc only; defined-term inheritance is the only cross-doc plumbing | **Item 74** |
| Forward-looking / probabilistic MNPI (Basic v. Levinson) | No detector for hedged / contingent language ("if we acquire", "subject to board approval") | **Item 80** (new — below) |
| Sector-specific MNPI (pharma trial endpoints, FDA decisions, tech sec-incident, FS regulatory action) | No sector packs | **Item 72** |
| Tipping language detection (passing-on as the offence) | No detector for forwarding / sharing / re-distribution language | **Item 81** (new — below) |
| HK "not generally known" narrower test | Public-evidence retrieval uses general-availability semantics | **Item 82** (new — below) |
| Selective disclosure red flags (Reg FD trigger) | No detector for analyst-call / institutional-investor mailing language | **Item 83** (new — below) |
| Quiet-period / blackout-window markers | Partial via `embargo_marker`; no calendrical reasoning | **Item 84** (new — below) |
| Jurisdiction-specific safe-harbour citations on findings | Suggestion rationales append jurisdiction statute suffixes, but findings do not yet carry full safe-harbour / regulator-pack context | **Item 85** + **Item 89** |
| HK / AU / JP / KR jurisdiction-specific MNPI lexicon variants | Seed packs ship statutes and direct-ID recognizers; MNPI detection still mostly uses universal rules | **Item 86** follow-up + **Item 82** / **Item 85** |

### Threats and gaps — summary

A document that contains *only* implied materiality + a target entity + a quiet-period reference would today **pass kaypoh's `strict` profile with no findings**. The lexicon doesn't fire; the entity is named in a public press release; the quiet-period reference doesn't match `embargo_marker`. Reviewer sees SAFE. That's a real recall hole on a textbook MNPI scenario. Items 70–86 close it across multiple axes (multi-attribute reasoning, sector specificity, cross-document inference, jurisdiction-specific doctrine).

The deterministic engine is the *precision floor*. The first-principles analysis above is the *recall ceiling* it's measured against.


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

54. **LLM upgrade path / symmetric findings.** Promote `coverage_warning` events (item 8) from advisory-only to a first-class LLM-raised finding type with `origin=llm`, capped severity (cannot exceed deterministic-medium floor; cannot suppress deterministic-high), required evidence trace (`context_window_hash` + structured reason from `STRUCTURED_REASONS`), and reviewer-action support via `POST /review/{id}/decision`. Closes the asymmetry where deterministic misses surfaced by the LLM go un-actioned. Gated by `audit_grade` + tenant opt-in; never overrides deterministic-high invariant.

### Round-trip + persistence

12. ~~Fuzzy entity linking for non-anchored variants — extend the linker to recognise bare surname references when an anchored honorific form is present elsewhere in the same document.~~ Shipped 2026-05-24. Pass 3 in `_named_person_findings`: trailing surname tokens from anchored multi-word names fire as `named_person` variants, suppressed if the surname matches a contract defined term.
13. ~~`POST /reidentify` + persistent per-document mapping store keyed by SHA-256 of the extracted text.~~ Shipped 2026-05-24.

55. **Matter-scoped defined-term inheritance.** Add a `matter_id` dimension above `session_id` (item 25). Sessions belong to a matter; defined terms accumulate at matter level and inherit into every session within that matter. Persistence under `${KAYPOH_JOURNAL_DIR}/matters/{matter_id}/defined_terms.json`. Tenant + matter isolation enforced via the same plumbing as item 42. Closes the real-world M&A case of 30+ documents over weeks across multiple reviewers — session-scoping was the right v1 but loses inheritance the moment the review session rotates.

### Audit-grade compliance

14. ~~Per-organisation `KAYPOH_JOURNAL_KEY` rotation with a versioned tenant-id → key mapping and a forward-compatible chain header (`prev_hmac`, `key_version`). Rotation events written as `journal_key_rolled` sentinels.~~ Shipped 2026-05-24. TOML keystore at `KAYPOH_JOURNAL_KEYS_FILE` carries `{active, keys.{version}.secret}`; each journal entry serialises with its `key_version` field; `verify_chain` resolves the HMAC key per-entry and reports `key resolution failed` when the version is missing. `rotate_journal_key(to_version, reason)` writes a `journal_key_rolled` sentinel sealed under the new active key. Legacy `KAYPOH_JOURNAL_KEY` flow stays byte-identical when no keystore is configured.
15. ~~Audit-pack reviewer roll-up: manifest summarises "decisions by reviewer X: accept N, reject M, rewrite K." Surfaces maker-checker violations where one reviewer approves their own decision.~~ Shipped 2026-05-24. `_build_reviewer_rollup` in `scripts/export_audit_pack.py` writes `reviewer_rollup` to the manifest and feeds it into `pack_hmac`.
16. ~~Reviewer attribution for `recall.lock.json` updates: actor + commit SHA + diff summary committed alongside lock changes so auditors can reconstruct *why* recall expectations changed.~~ Shipped 2026-05-24. `scripts/recall_gate.py --update` now requires `--reason` and appends `{ts, actor, commit_sha, reason, diff}` to `test/fixtures/legal-corpus/recall.lock.history.jsonl`. Actor resolves from `KAYPOH_RECALL_ACTOR` → `git config user.email` → `$USER`; commit SHA from `git rev-parse HEAD`.
17. ~~Reviewer-mandated wait period: optional `KAYPOH_AUDIT_MIN_WAIT_SECONDS` gate on `scripts/export_audit_pack.py` to surface batch-approval red flags.~~ Shipped 2026-05-24. The exporter emits `min_wait_status` / `min_wait_warning` in the manifest and exits `2` when the bound is violated; the pack itself remains HMAC-sealed.
18. ~~`POST /review/{id}/decision`, `GET /review/{id}`, HMAC-chained journal under `KAYPOH_JOURNAL_DIR`, audit-pack export+verify scripts. Reviewer identity threaded through schemas + endpoint + session view.~~ Shipped 2026-05-24.

57. **Bind reviewer identity to authenticated principal.** Drop free-form `X-Reviewer-ID` header trust. Reviewer identity must resolve from the JWT subject or API-key principal — same source as tenant resolution under item 42 — so maker-checker rollup (item 15) cannot be spoofed by a caller submitting two different header values. Free-form header accepted only when `KAYPOH_DEV_AUTH=1` for local development. New journal field `reviewer_identity_source ∈ {jwt, api_key, dev_header}` distinguishes authenticated from legacy attribution. Existing journal entries keep header-sourced `reviewer_id` for back-compat; verification scripts surface a warning when a session contains mixed sources.

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

63. ~~**Repurpose `/classify` as a programmatic findings surface (post-deprecation).** Today `/classify` and `/classify/batch` lazy-import the legacy 9-layer pipeline (`layer1_lexicon → layer2_embeddings → layer3_clustering → layer4_classification.model1+model2 → layer5_mosaic → layer6_regression → layer7_public_evidence → layer8_llm_adjudicator`) and return a model-confidence score with no statute-cited rationale. Repoint the endpoint at `engine.review(...)` so it returns the same deterministic + LLM-tier evidence stack as `/review`, in a flatter machine-readable shape better suited to programmatic clients (no review-session state, no decision endpoint, no journal write by default). Wire contract: `POST /classify {text, document_type, jurisdiction, review_profile}` → `{findings: [...], pii_score, mnpi_score, source_verification, coverage_warnings}`. Legacy classifier kept callable for one release as `POST /classify?engine=legacy` returning the old score shape, with `Deprecation` + `Sunset` headers; sunset after one major version. Layers 1–6 stay on disk until sunset completes, then archived. Closes the "is it useful at all?" question — the endpoint becomes a thin client over the current architecture instead of a dead pipeline.~~ Shipped 2026-05-26. The legacy classifier compatibility path was removed rather than kept behind `engine=legacy`; legacy response fields remain as `null` compatibility fields only.

58. **Local-daemon production-grade access control (later actionable).** Today `127.0.0.1:8765` has no auth — vulnerable to DNS rebinding (browser-originated cross-origin requests), malicious local processes (npm postinstall, other users on shared macOS), and cross-tab credential theft against the mapping store. Add: Origin header allowlist (`chrome-extension://*`, `https://chatgpt.com`, `https://claude.ai`, `https://gemini.google.com`, configured Office add-in origins); per-install pairing token written to OS keychain (macOS Keychain / Windows Credential Manager / GNOME Keyring) with first-connect handshake from the browser ext + Office add-in; optional Unix-domain-socket binding (`KAYPOH_LOCAL_SOCKET_PATH`) for stricter macOS/Linux deployments. Sequenced after item 22 so there is a real client to handshake with; blocks before any procurement-security review can sign off on the desktop SKU.

### Privacy hardening

27. ~~Structured-tokens-in/out runtime LLM mode for regulated tenants: send `{entity_id, context_window_hash, sanitised_query}` instead of raw text fragments. Stronger guarantee than redact-then-send.~~ Shipped 2026-05-24. `llm.llm_input_mode ∈ {raw_text (default), structured_tokens}`. In structured mode the request body contains zero raw document text (verified by tests that grep the wire payload), the LLM sees only `{mode, entity_id, body_hash, findings: [{rule, category, severity, jurisdiction, context_window_hash}, ...], public_evidence_summary: {status, source_count, blocked_query_count}}`, and the response is server-clamped against `STRUCTURED_REASONS` (closed vocabulary of 8 reason codes). `matched_public_sources` and `unverified_claims` are always emptied in structured mode (potential URL/text leak channels). `output_clamped` boolean on the response tells the auditor whether the LLM tried to step outside the closed vocabulary. `LLMAdjudicationResponse` schema gains `input_mode` and `output_clamped` fields so the wire contract makes the privacy posture explicit.

59. **Subject-erasure path + multi-jurisdiction equivalents (ASAP).** Today `scripts/purge_mappings.py` (item 41) deletes by `document_hash` or by retention age. Neither path satisfies a subject-initiated deletion request ("delete every mapping containing NRIC X"). Implement: per-tenant reverse-index `(tenant_id, pii_hash) → [document_hash, ...]` where `pii_hash = HMAC(canonical_value, tenant_secret)` and canonicalisation normalises NRIC casing, lowercases email, strips phone non-digits. The index itself does not leak PII. Subject-deletion request → derive `pii_hash` → scan reverse-index → delete matching mappings → emit `subject_erasure_recorded` journal events with statute citation. New CLI `scripts/erase_subject.py --tenant X --value Y --citation PDPA-s16`. Statute citations covered: PDPC PDPA s16 + Advisory Guidelines on Anonymisation (SG), GDPR Art 17 (EU), UK DPA 2018 s47, CCPA/CPRA right to delete (California), Australia Privacy Act APP 11.2, Japan APPI Art 30, Korea PIPA Art 36, Brazil LGPD Art 18, India DPDPA 2023 s12, HK PCPD PDPO s26. Per-jurisdiction rationale resolved via `KAYPOH_CITATIONS_OVERRIDE` (per item 60).

60. **Per-tenant `KAYPOH_CITATIONS_OVERRIDE` (ASAP).** Today `KAYPOH_CITATIONS_OVERRIDE` is a single global TOML — in a multi-tenant server SKU this leaks tenant A's internal policy citations into tenant B's rationales. Migrate to per-tenant resolution: `KAYPOH_CITATIONS_OVERRIDE_DIR/{tenant_id}.toml`, resolved through the same tenant-context plumbing as item 42. Global file remains as fallback for tenants without an override. Tests prove cross-tenant citation leakage is blocked, mirroring the cross-tenant isolation suite from item 42.

61. **Binary content + container metadata coverage (ASAP).** Today's pipeline is text-extract-then-rewrite — embedded binaries inside DOCX/PDF/XLSX/PPTX/EML/archives pass through carrying PII the text path already scrubbed. Coverage surfaces required:
    - **DOCX:** embedded images, OLE objects, footnotes/endnotes, table headers/footers, embedded fonts, comment author metadata (item 49 partial — extend).
    - **PDF:** AcroForm fields, annotations (author-attributed), XFA forms, embedded files, signed/encrypted regions.
    - **XLSX:** cell comments, hidden sheets, hidden rows/cols, named ranges, **pivot caches** (retain source data after sheet delete), defined names, ext lists.
    - **PPTX:** speaker notes, slide masters, hidden slides, embedded media.
    - **Email (`.eml`/`.msg`):** attachments (recursive), inline base64 images, forwarded mail.
    - **Archives:** ZIP / 7z / tar containing nested docs (recursive extract → review per-entry).
    - **HTML:** `data-*` attributes, HTML comments, `display:none` content, attribute-encoded text.
    - **SVG:** text-in-graphics, metadata block.
    - **RTF:** embedded objects, `\object` tagged binaries.
    - **Markdown:** HTML comments, image alt-text.
    - **Tracked-change deleted text** (DOCX `w:del` elements).

    **Container-security vectors** (treat as fail-closed per item 65):
    - Password-protected DOCX/PDF/ZIP — refuse with explicit error, do not prompt for password silently.
    - Macro-enabled containers (`.docm`, `.xlsm`, `.pptm`) — refuse by default; opt-in extras for tenants who explicitly accept macro risk.
    - PDF JavaScript (`/JS`, `/JavaScript` actions, `/OpenAction`) — strip + log finding; never execute.
    - External references — DOCX `<w:hyperlink>` to remote images / `<v:imagedata r:href>`, PDF `URI` actions, HTML `<img src="http://...">` — flag as `external_reference` finding; tracking pixels are a privacy leak.
    - Polyglot files (file claims DOCX but is actually a polyglot ZIP/JAR/PDF) — magic-byte check against declared content-type; fail closed on mismatch.
    - Compression bombs — zip bombs, gzip bombs, recursive nested archives — cap decompression ratio + recursion depth, refuse on breach.
    - XXE / billion-laughs in XML-based formats (DOCX, SVG, RTF, XML) — use `defusedxml` everywhere; disable DTD resolution.
    - Path traversal in archives — `../` entries, absolute paths, symbolic links — reject archive entirely.
    - Embedded foreign docs — Office docs inside PDF (`/EmbeddedFiles`), PDF inside DOCX (OLE), `.eml` inside `.zip` inside `.docx` — recurse with depth cap, treat each as a sub-document.

    Item 50 fail-closed gate extends per-container: if the extractor cannot enumerate embedded binaries (encrypted ZIP, corrupted XLSX, polyglot file), refuse rather than proceed with partial coverage. Image OCR / image recognition is item 64 (separated for provider-pluggability).

64. **Image recognition + OCR with multi-provider backend.** Embedded images, scanned annexures, signature blocks, and screenshots-of-text inside DOCX/PDF/PPTX/EML routinely carry the same NRIC / UEN / counter-party-name PII that the text-path scrubs. Today these slip through. Add an `ImageScanner` interface with pluggable providers selected via `KAYPOH_IMAGE_SCAN_PROVIDER ∈ {none, tesseract, openai_vision, google_vision, aws_rekognition, azure_vision}`:

    - **Local: Tesseract** — offline-default, ships in `[ocr]` extras; baseline coverage for typed text in screenshots.
    - **Cloud: OpenAI Vision** (gpt-4o / o1 vision) — best on mixed text + signature + handwriting; tenant opt-in (same opt-in matrix as the LLM tier per the per-tenant principle), key via `OPENAI_API_KEY`.
    - **Cloud: Google Cloud Vision** — strong on Asian-script OCR (Mandarin/Tamil signatures common in SG/SEA contracts), key via `GOOGLE_APPLICATION_CREDENTIALS` (service account JSON path).
    - **Cloud: AWS Rekognition** — face/PII detection in image content (driver-license photos, passport pages), key via `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (or instance profile).
    - **Cloud: Azure AI Vision** — for tenants standardised on Microsoft cloud; key via `AZURE_VISION_KEY` / `AZURE_VISION_ENDPOINT`.

    All cloud providers pass through `PrivacyGuard` first — raw image bytes are *content*, so they get the same treatment as raw document text in the LLM tier (per-tenant opt-in, ledger entry per call, structured_tokens-equivalent metadata-only mode where the provider API supports it). `kaypoh-local` desktop SKU stays Tesseract-only by default; cloud-vision is `kaypoh-server` + opt-in. Returned findings carry `source: "image_ocr"` + `image_locator: {container_path, image_index}` so reviewers can trace which image flagged. Fail-closed per item 65: if the configured provider is unreachable, refuse the document rather than silently skipping image content.

65. **Fail-closed everywhere — workflow-wide audit.** Item 50's fail-closed posture is currently scoped to PDF ingest. Extend the principle to every step of the workflow where ambiguous state today defaults open:

    - **Detector failures** — if any deterministic recognizer throws (regex catastrophic backtrack, jurisdiction-pack parse error), today the engine catches + continues; should refuse and surface the error rather than ship a finding-incomplete review.
    - **LLM-tier failures** — if `audit_grade` is requested but the LLM provider 5xxs, today the engine downgrades to deterministic-only silently; should either refuse or surface `llm_tier_status: degraded` explicitly so the reviewer knows audit_grade did not actually engage.
    - **Public-evidence retrieval failures** — if Tinyfish/Exa errors, today returns `not_checked` indistinguishably from "actually not checked"; should surface `retrieval_status: error` separately.
    - **Mapping-store failures** — if `KAYPOH_REVIEW_PERSIST=1` but the store path is unwritable or `KAYPOH_MAPPING_STORE_KEY` is missing when encryption is required, today writes plaintext or fails open; should refuse the request.
    - **Image-scan failures** — per item 64, if the configured image provider is unreachable, refuse rather than silently skip image content.
    - **Subject-erasure failures** — if reverse-index lookup fails (item 59), refuse the erasure request rather than report success.
    - **Citation-override resolution failures** — if `KAYPOH_CITATIONS_OVERRIDE_DIR/{tenant_id}.toml` is malformed, refuse rather than fall back to global silently.

    Single meta-audit pass: grep every `try / except` in `src/kaypoh/` for swallowed exceptions in the runtime path; add `_fail_closed_or_open` decision points with explicit logging + structured error responses. Surface a `degraded_modes` array on every API response so callers can act on partial coverage rather than discover it post-hoc.

### Continuous accuracy substrate (training)

These items target overall accuracy improvement on the LLM tier without changing the deterministic-engine contract. Every item gates on the existing recall + precision baselines in `test/fixtures/legal-corpus/recall.lock.json` and `test/fixtures/legal-corpus-adversarial/recall_adversarial.lock.json` — a trained artefact ships only when it meets or beats both.

> **Training-run status — 2026-05-26:** item 29 pipeline scaffolding (`training/distillation/`) is ready and `local_distilled` is wired as a provider, but no trained student artefact is promoted. Dataset-prep / dry-run for items 30 (DPO export) and 31 (severity calibrator) remains operator work. Promotion gates remain `--min-agreement ≥ 0.85` and `--max-invariant-violations == 0` against `legal-corpus-adversarial`. Trained artefacts that miss either gate do not ship; the deterministic + cloud-teacher path stays the production fallback.

29. ~~Cloud-adjudicator distillation → local student model.~~ Shipped 2026-05-24 (pipeline scaffolding). `training/distillation/` ships five components: `prompts.py` (shared message templates so teacher/student/trainer see byte-identical shapes), `teacher_collector.py` (walks corpora, calls the configured teacher adjudicator, writes idempotent JSONL + a per-call training ledger to `${KAYPOH_JOURNAL_DIR}/training_ledger.jsonl`), `distill_train.py` (LoRA-tunes a configurable base model; `--dry-run` validates the dataset without any GPU code path — catches single-label degeneracy, too-few-rows, malformed teacher verdicts), `eval_against_corpus.py` (measures agreement-rate vs deterministic engine + counts invariant violations where the student tries to upgrade past a deterministic label), and `student_provider.py` (`LocalDistilledAdjudicator` — loads the LoRA adapter and serves `adjudicate()` calls). `LocalLLMAdjudicator` routes `provider=local_distilled` to the student backend via `KAYPOH_LLM_DISTILLED_ADAPTER_PATH` + `KAYPOH_LLM_DISTILLED_BASE_MODEL`. Heavy ML imports (`torch`/`transformers`/`peft`) are lazy so the scaffolding tests run on a clean Python env. 16 tests cover the full pipeline with mocked LLMs. Actual training and student promotion remain operator-driven; the pipeline is ready to run as soon as you have an OpenAI key + a GPU box + `pip install peft datasets accelerate`.

30. **Journal-driven preference tuning (DPO).** New module `training/journal_preference_export.py` reads the HMAC-chained journal (`KAYPOH_JOURNAL_DIR/journal.jsonl`), filters to `decision_recorded` events with an associated LLM verdict, and produces a sanitised JSONL of preference pairs (`accept` = chosen, `reject` = rejected). Sanitisation is the gating step: a `PrivacyGuard.sanitise_for_training()` pass strips matched-text spans, named-person tokens, and email/phone/NRIC values from rationales before export; every export emits a privacy-ledger entry. Trainer: standard DPO on the local student from item 29 (or directly on a local-only base if 29 hasn't shipped). Per-tenant fine-tunes are out of scope for v1 — the first release pools accepted/rejected pairs across all consenting tenants and produces a single shared-tenant model.

31. **Journal-trained severity calibrator.** Replace the hard-coded `MNPI_DOC_TYPE_SEVERITY_OVERRIDES` table with a small gradient-boosted-trees model (LightGBM or `sklearn.ensemble.GradientBoostingClassifier`) trained on `(rule, jurisdiction, document_type, context-feature-bag)` → reviewer-accepted severity, taken from `decision_recorded` events on findings whose decision was `accept` or `rewrite`. Scope is narrow: only medium ↔ low borderline; `high`-severity findings are not subject to ML adjustment (preserves deterministic-floor invariant). Lives under `training/severity_calibrator/` with `train.py` + `serve.py`; ships in `kaypoh-server` (adds `scikit-learn` to `[server]`); desktop SKU keeps the deterministic table. Activated per request via `review_profile=audit_grade` only.

32. ~~Escalation-threshold calibration for the two-tier engine~~ Shipped 2026-05-24. `scripts/calibrate_escalation_threshold.py` searches over `(LLM_TIER_MNPI_LOWER, LLM_TIER_MNPI_UPPER)` pairs, scoring each candidate on a weighted mix of precision, recall, escalation-rate (LLM cost proxy), and latency-score against any corpus directory. Includes shipped defaults as a baseline candidate so the report shows whether the recommendation actually improves over status quo. `--apply` writes the recommendation to `configs/runtime_calibrated.toml` for explicit opt-in by `configs/runtime.py` (engine continues to use compile-time defaults unless the file is wired). Default 50 iterations of random sampling over the 2-D band space; objective weights tunable via `--w-precision`, `--w-recall`, `--w-latency`, `--w-cost`. Lightweight — no model training, just hyperparameter search — and serves as the eval scaffolding that items 29–31 will plug into.

62. **Synthetic-corpus prompt actionables + API-key documentation.** Improve `scripts/generate_legal_fixture.py` prompts to widen the synthetic distribution so the distilled student (item 29) and DPO export (item 30) do not collapse onto the generator's own distribution:
    - Sweep SG / SEA jurisdictions per batch (currently single-jurisdiction).
    - Inject obfuscation modes as prompt parameters: NRIC-in-URL, NRIC-with-ZWJ, NRIC-across-line-break, OCR ligature artefacts, broken-DOCX-runs.
    - Mix English / Mandarin / Bahasa Melayu / Tamil names per doc (SG-realistic).
    - Vary `document_type`: SPA, SHA, APA, MOU, LOI, term sheet, memo, research note, embargoed press release, earnings call transcript.
    - Generate negative-prose siblings ("no MAC clause", "without any SPA", absent codename) for adversarial precision.
    - Generate adversarial false-positive bait (Mac OS X mentions, MAC addresses, "spa day", "Tan-coloured envelope") to keep precision from regressing.
    - Hand-review remains mandatory before any `recall.lock.json` / `recall_adversarial.lock.json` refresh.
    **OpenAI API key:** `export OPENAI_API_KEY=...` in shell env before running `python3 scripts/generate_legal_fixture.py <doc_type> --slug <name>` (script reads `os.environ["OPENAI_API_KEY"]`; example invocations at top of the script).

66. **Trained classifier as additive recall booster.** The deterministic engine has a precision floor (statute-citable findings) but a recall ceiling on contextual MNPI — implied materiality, sector-specific tells, negotiation-stage signals, cross-document inference. Reintroduce a trained classifier as an *additive* signal, never as the source of truth. Training corpus: synthetic (`legal-corpus`, `legal-corpus-adversarial`, `legal-corpus-sea`) + reviewer-accepted findings from the journal (item 30 sanitisation). Output: `classifier_score` field on `/review` response, plus per-rule classifier-suggested findings tagged `origin=classifier` and capped at deterministic-medium severity (cannot upgrade past deterministic-high, cannot suppress deterministic-high — same invariant as the LLM tier). Inference is fast and local; LightGBM or a small transformer (DistilBERT-class). Lives under `src/kaypoh/classifiers/` — NEW code, not revived layer4. Shipped under `audit_grade` only; `strict` stays pure-deterministic.

67. **Document similarity / clustering as advisory signal.** When a document is structurally similar to known-MNPI documents in the corpus, that's a useful signal even when no deterministic rule fires. Embed every reviewed document with a small local model (e.g. `all-MiniLM-L6-v2` via `sentence-transformers` in the `[ml]` extras), index in a local FAISS or hnswlib index per tenant, and on `/review` return `similar_documents: [{doc_hash, similarity, reviewer_disposition}]` as advisory context. Surfaces "this doc is in the same cluster as 3 docs the reviewer accepted as high-MNPI last month" without making the engine act on it. Never feeds into severity scoring directly; reviewer judgment closes the loop. Lives under `src/kaypoh/similarity/` — NEW code, not revived layer2 + layer3.

68. **Multi-signal aggregator with transparent attribution.** Replace the implicit "max severity wins" rule in `engine.review()` with an explicit aggregator that combines deterministic findings (precision anchor) + classifier score (item 66) + similarity matches (item 67) + LLM verdict (existing) + public-evidence verification (existing) into a single `aggregated_mnpi_score` and per-signal attribution. The aggregator is **not** a black-box regression — it's a transparent weighted blend with reviewer-visible per-signal contributions: `{deterministic: 0.55 (anchor), classifier: 0.18 (DistilBERT), similarity: 0.08, llm: 0.15, public_evidence: -0.20}`. Reviewer can see exactly which signal pushed the score. Weights are config-tunable per tenant (per-tenant principle), defaults locked by the calibration script (item 32 extended). Deterministic findings remain non-negotiable (a deterministic-high cannot be diluted by other signals voting low). Lives in `src/kaypoh/aggregator/` — NEW code; the layer5 mosaic concept is reborn as a transparent, statute-citable aggregator.

69. **First-principles statutory taxonomy (`docs/statutory-coverage.md`).** Author a formal mapping of each in-scope jurisdiction's PII + MNPI statutory definition → required detector categories → current detector coverage → known gaps. Replaces ad-hoc "we cover SG" assertions with a defensible audit-trail of *exactly* which statutory concepts each detector implements. Maintained alongside jurisdiction packs; updated whenever a regulator publishes new guidance (item 53 keeps citations current). The doc itself is downstream of the "First-principles statutory analysis" section in this architecture doc — which is the authoritative draft of the taxonomy until `docs/statutory-coverage.md` is generated.

70. **Quasi-identifier combination detection.** Fire a `quasi_identifier_combination` finding when a document contains ≥3 quasi-identifiers (DOB + postcode + gender; employer + role + salary; address + family relationship; full-name + birthplace + employer) that together breach a k-anonymity threshold (default k=5). Severity scaled by re-identification probability estimate. Multi-attribute reasoning, not span-local. Anchors in PDPA s2 ("identified from that data or from that data and other information"), GDPR Recital 26 ("means reasonably likely to be used"), CCPA "reasonably capable of being associated". New module `src/kaypoh/review/quasi_identifiers/`.

71. **Special-category PII detectors.** Detect health (diagnosis codes, medication names, treatment narratives), biometric (fingerprint refs, facial templates, gait signatures), sex life / sexual orientation, religion, racial/ethnic origin, political opinion, trade-union membership. Each maps to a special-severity tier under GDPR Art 9, PDPC special-category (per s17 + Advisory Guidelines), PIPA "sensitive information", LGPD Art 5(II), APPI "special care-required personal information", DPDPA "sensitive personal data". Ships as new detector pack under `src/kaypoh/review/detectors/special_category/`.

72. **Sector-specific MNPI packs.** Beyond M&A + earnings tells: pharma (clinical trial primary endpoints, FDA correspondence, AE reports), tech (security incident pre-disclosure, executive departures, security-vuln advisories), financial-services (regulatory investigation, capital ratio breaches, AML enforcement actions), energy (reserve revisions, environmental incidents, pipeline disruptions), legal (settlement amounts, judgment pre-publication, sealed-court-record references). Each sector pack ships its own lexicon + statute citations + adversarial fixtures. Loaded per `industry_sector` field on `/review` request.

73. **Entity-size-relative materiality.** Cross-reference detected entities against a market-cap / annual-revenue lookup (provided via opt-in connector to SGX / Bursa / IDX / SET / PSE / HOSE / Bloomberg / Refinitiv at `audit_grade`); scale `financial_amount` and `financial_percentage` severity by entity-relative thresholds. SEC Staff Accounting Bulletin No. 99 anchor: materiality is contextual to issuer size. Default heuristic when no lookup configured: 1% of market cap as rough materiality floor. Cached per `entity_id` with TTL.

74. **Cross-document materiality reasoning.** Extend defined-term inheritance (item 25 / 55) to per-finding cross-document inference. When document A in a matter has a `transaction_codename` and document B has a specific entity reference, surface a `combined_mnpi_inference` finding tagged with both source documents and the inference chain. Built on top of the matter store (item 55).

75. **Cross-jurisdiction conflict resolution.** Today `/review` already accepts `source_jurisdiction` + `destination_jurisdiction` separately, but the engine runs the *strictest-wins* policy. Extend to surface findings under both jurisdictions with explicit attribution: `{rule: "sg_nric_fin", source_juris_finding: true, destination_juris_finding: true}` and `{rule: "us_ssn", source_juris_finding: false, destination_juris_finding: true}`. Distinguishes "you can't export this under PDPA" from "the destination juris (US) does not regulate this" so the reviewer can see why a finding fires.

76. **Active-learning loop closure.** Extend item 30 (DPO export) into an end-to-end loop: reviewer-rejected findings → adversarial corpus growth → adversarial detector retraining → tighter precision baseline. Reviewer-accepted previously-missed spans (e.g. from coverage_warning promotions per item 54) → positive corpus growth → recall lock improvement. Requires journal sanitisation (item 30 prerequisite) + a `scripts/promote_journal_to_corpus.py` tool that surfaces candidate fixtures for hand-review before they enter the recall gate.

### Statutory-gap closure (PII / personal-data side)

77. ~~placeholder, intentionally unused~~ (numbering preserved so subsequent items align with the first-principles gap table above)

78. **Pseudonymised-but-linkable identifier detection.** GDPR Recital 26 and PDPC Anonymisation Advisory Guidelines both treat pseudonymised data that *the organisation* can re-link as personal data. Add detectors for: employee IDs (`EMP-XXXXX`, `SE-XXXXX` patterns), customer account numbers (numeric with org-prefix), internal session IDs (UUID with `_session` / `_user` tagging), bank-internal customer reference numbers, hospital MRNs (medical record numbers), insurance member IDs. Detection requires both pattern + context (the surrounding sentence references "employee", "customer", "patient", "member" — defined-term suppression is not in scope here because these tokens are *anchored* to specific subjects, not generic role nouns). Severity tier: PII medium by default, escalating to PII high under `audit_grade` when linkable to a named person in the same document.

79. **Inferred-attribute detection (relationship + location + employer chain).** When a document contains a named person AND a relationship verb / location preposition / employment marker pointing to another entity, surface a `personal_attribute_inference` finding for the inferred attribute. Examples: "John Tan's wife Mary" → infers Mary's family relationship; "Sarah works at Acme" → infers Sarah's employer; "Dr Lim lives in Bukit Timah" → infers Lim's residential area. The PII universe under PDPA / GDPR / CCPA is the *inferred attribute*, not just the named person. Severity medium by default, contextual escalation when special-category inference (health condition, religious affiliation, sexual orientation) is the result. Local NER + relation extraction; lives behind `audit_grade` to keep `strict` precision-pure.

### Statutory-gap closure (MNPI side)

80. **Forward-looking / contingent-language MNPI detection.** Basic v. Levinson (US) plus MAR Art 7(2-3) (EU/UK) and SFA s215 (SG) all extend MNPI to *probabilistic / contingent* future events. Add detectors for: contingent verbs ("if approved", "should the board agree", "subject to regulatory clearance"), probabilistic language ("likely to", "may result in", "expected to"), hedged disclosure ("management believes", "early indications suggest"), pre-decisional markers ("under consideration", "in discussions", "exploratory"). Severity gated by adjacency to known MNPI tells (deal codename, definitive agreement, regulatory entity) — alone these phrases are noise; in proximity to existing MNPI signals they amplify the score. Lives as new rule `contingent_mnpi_language`.

81. **Tipping-language detection.** SFA s219 (SG), Rule 10b5-2 (US), MAR Art 14 (EU/UK), SFO Part XIV (HK) all make *passing on* MNPI co-extensive with trading on it. Add detectors for: forwarding language ("please share with", "feel free to circulate", "passing this along"), institutional-investor distribution markers ("for distribution to clients only", "select investors", "limited partners list"), draft-sharing markers ("attached for your review", "see attached deck"). Severity tier: MNPI high when adjacent to existing MNPI findings (one rule firing alone is noise; tipping language + MNPI content together is the tipping offence). New rule `tipping_language`.

82. **Public-evidence retrieval — narrower "not generally known" semantics for HK.** Today the public-evidence retriever uses general-availability semantics (matched a public source → soften severity). HK SFO Part XIV is narrower: "not generally known to the persons who are accustomed or would be likely to deal in the listed securities". A press release buried on an obscure regulator page is "available" but not "generally known". When `destination_jurisdiction == "HK"`, public-evidence soft-down requires a stricter retrieval threshold (multiple major-publication hits + recency window ≤14 days). Configurable per `KAYPOH_HK_PUBLIC_EVIDENCE_PROFILE`.

83. **Selective-disclosure red-flag detection (Reg FD trigger).** Reg FD (US Rule 100, 17 CFR 243.100) prohibits selective disclosure of MNPI to analysts / institutional investors / shareholders without simultaneous public disclosure. Add detectors for: analyst-call language ("Q&A with sell-side", "analyst day prep", "buy-side mailing"), institutional-mailing markers ("to our largest holders", "for institutional investors only"), one-on-one meeting language ("scheduled call with [analyst firm]"). When co-occurring with MNPI findings, surface a `selective_disclosure_risk` finding tagged with Reg FD / equivalent jurisdiction rule. New rule `selective_disclosure_risk`.

84. **Calendrical reasoning — quiet-period + blackout-window detection.** Most listed-company regimes have quiet periods around earnings (e.g. US SEC 30-day pre-earnings, SGX no-go window). Today `embargo_marker` catches explicit "Embargoed" / "Press Hold" strings but no calendrical reasoning. Add a `blackout_period_reference` rule that fires when a document references a date / period within a known blackout window for a detected entity (requires entity → ticker → next-earnings-date lookup at `audit_grade`). Closes the gap where a doc is dated mid-quiet-period without saying "embargo".

85. **Jurisdiction-specific MNPI statute citations on findings.** Today MNPI suggestions cite a generic legal basis. Wire the same statute-citation pattern as PII findings: SG findings cite SFA s218-221 + relevant SGX listing rule; US findings cite Rule 10b-5 + Reg FD; EU/UK findings cite MAR Art 7 / Art 14 / Art 17; HK findings cite SFO Part XIV; AU findings cite Corporations Act s1042A; JP findings cite FIEA Art 166-167; KR findings cite FSCMA Art 174-179. Resolved per `destination_jurisdiction`. Override via `KAYPOH_CITATIONS_OVERRIDE` (per-tenant per item 60).

86. **Curated jurisdiction packs — HK / AU / JP / KR.** Partially shipped 2026-05-26. Built-in TOML packs, aliases, statute rationales, checksum validators, direct personal/government-ID recognizers, company/tax-ID recognizers, seed fixtures, and combined recall/precision lock are in place for HK / AU / JP / KR. Shipped rules: `hk_hkid`, `hk_cr_no`, `au_tfn`, `au_abn`, `au_acn`, `jp_my_number`, `jp_corporate_number`, `kr_rrn`, `kr_business_registration`. Remaining work: local postal-address formats, jurisdiction-specific MNPI lexicon variants, and corpus growth beyond one seed fixture per jurisdiction. The first-principles analysis keeps HK / AU / JP / KR in scope for the legal-corporate ICP (HK financial centre + AU APRA-regulated + JP/KR institutional cross-border deals).

### Procurement-substrate items surfaced by the first-principles analysis

87. **Per-jurisdiction defensibility audit report.** Generate `docs/defensibility/{jurisdiction}.md` per jurisdiction from `docs/statutory-coverage.md` (item 69) — a 2-page PDF-renderable summary a procurement reviewer can hand to compliance: "this is what kaypoh detects under PDPA, with statute citations; this is what it doesn't detect; this is how the residual risk is managed." Generated, not hand-authored — drift from the statutory taxonomy is caught by CI.

88. **Regulator-update watcher.** Statutes drift. PDPC publishes new advisory guidelines; MAS updates AI Risk Management Guidelines; OAIC issues new AI guidance; SEC promulgates new disclosure rules. Add `scripts/check_regulator_updates.py` that polls a configured list of regulator publication feeds (RSS / Atom where available, manual checklist where not) and surfaces a diff against the last-known statute-citation snapshot. Cadence: weekly. Output goes to the maintenance backlog as a "regulator-update-pending" item.

89. **Defensibility evidence pack export.** Extend the audit-pack tool (`scripts/export_audit_pack.py`) with an opt-in `--include-defensibility` flag that bundles, for every finding in the pack: matched statute, statute version date, jurisdiction-specific safe-harbour analysis, current PDPC/SEC/MAS guidance citation, and a sanitised reviewer-accept-rate from journal history. Reviewers forward the pack to internal audit + external regulators with no additional hand-prep.

### Sharpened actionables surfaced by the 2026-05-26 doc-vs-repo audit

These items pre-existed in the expansion sequence but the audit surfaced specific concrete next steps that were not previously enumerated. Numbering continues the global sequence.

92. **HK/AU/JP/KR seed-corpus growth from 1 → 10 fixtures per jurisdiction.** Current `legal-corpus-hk-au-jp-kr/` has one `.txt` + `.labels.json` per jurisdiction; recall/precision locks at 1.0 are trivially achievable at that volume and the procurement claim for those packs is overstated. Use `scripts/generate_legal_fixture_batch.py --jurisdiction {HK|AU|JP|KR} --count 9` per jurisdiction, then `scripts/autolabel_batch.py --model o1` per generated batch, hand spot-check ≥30%, then `scripts/recall_gate.py --update --reason "HK/AU/JP/KR corpus growth to 10 per juris"`. Until this lands the §Jurisdiction Coverage table cannot honestly mark those packs as procurement-grade. Sequenced after item 33's remaining detectors so each new detector ships with corpus coverage rather than retrofitting after.

93. **`docs/statutory-coverage.md` extraction from in-doc taxonomy (item 69 closer).** The §First-Principles Statutory Analysis section is the authoritative taxonomy draft. Extract it to `docs/statutory-coverage.md` with a CI gate (`test/test_statutory_coverage_doc.py`) that diffs the rendered doc against (a) the section in this file, (b) `jurisdictions_data/*.toml` recognizer inventory, and (c) `citations.py` rationale + suffix dictionaries. Drift fails the test. Procurement reviewers cite the standalone doc; the architecture file remains the editor's source. One-time extraction + ongoing diff check.

94. ~~**Per-jurisdiction MNPI statute citations on finding rationales (item 85 closer).**~~ Shipped 2026-05-26. Audit confirmed the existing wiring is healthy: `engine.py:_mnpi_findings` stamps each finding with `jurisdiction=_pack_scope(packs)` (e.g. `SG` or `SG+US`); `engine.py:_suggestions` forwards that to `mnpi_rationale(jurisdiction=...)`; `citations.py:mnpi_rationale` splits on `+`, looks up each code's entry in `_MNPI_JURISDICTION_SUFFIX`, and joins via `_join_suffixes`. No call sites drop the suffix. `test/test_mnpi_jurisdiction_suffix.py` ships 7 audit tests covering: (a) every in-scope juris has a non-empty MNPI suffix in the catalogue (13/13: SG, US, UK, EU, MY, ID, TH, PH, VN, HK, AU, JP, KR); (b) direct `mnpi_rationale()` call carries the suffix for every (rule × juris) pair (11 rules × 13 jurisdictions = 143 assertions); (c) end-to-end engine pipeline carries the suffix all the way through `engine.review(include_suggestions=True).suggestions[*].rationale` for every (rule × juris) pair (143 more assertions); (d) cross-juris routing `SG → US` carries BOTH SG SFA and US Reg FD suffixes; (e) amplified `contingent_mnpi_language` / `tipping_language` findings still carry the suffix after the `_amplify_co_occurring_low_mnpi` post-pass; (f) `KAYPOH_CITATIONS_OVERRIDE` substitution still cleanly replaces the base+suffix when configured. Total: 158 regression tests + 7 audit tests pass.

95. ~~**Forward-looking / contingent MNPI lexicon (item 80 closer).**~~ Shipped 2026-05-26. `CONTINGENT_MNPI_RE` in `engine.py` matches `if approved`, `should the board (agree|approve)`, `subject to (board|shareholder|regulatory|management|due diligence|financing|conditions precedent) (approval|clearance|sign-off|consent)`, `(likely|expected) to (close|approve|materialise|impact|complete|result in|conclude|sign|announce)` (likelihood verbs gated on deal-stage verbs to keep precision survivable), `under (active) consideration`, `in (advanced|preliminary|early-stage|ongoing) (discussions|negotiations)`, `exploratory (talks|discussions|stage|phase)`, `pre-decisional`, `management believes`, `early indications suggest`, `may (result in|lead to|trigger) (acquisition|merger|disposal|takeover|restructuring|divestiture|impairment|spin-off)`. Severity defaults to `low` standalone; `_amplify_co_occurring_low_mnpi(findings)` in `review()` escalates to `medium` when a finding's span lies within ±200 chars of any `transaction_codename` / `definitive_agreement` / `material_adverse_change` / `material_event` / `embargo_marker` / `nonpublic_marker` span. Negation guard reuses `_is_negated_context` so "no longer in discussions" / "not under consideration" don't fire. Citation in `citations.py` cites Basic v. Levinson, SFA s215, MAR Art 7(2-3). 23 unit tests in `test/test_contingent_tipping_mnpi.py` cover canonical recall, gated-verb precision, negation suppression, and co-occurrence escalation.

96. ~~**Tipping-language lexicon (item 81 closer).**~~ Shipped 2026-05-26. `TIPPING_RE` in `engine.py` matches `please (share|forward|circulate|distribute) (with|to)` (plus a 40-char trailing context capture), `feel free to (share|forward|circulate|distribute)`, `passing this (along|on)`, `for (distribution|circulation) to (clients|investors|partners|select|preferred|institutional|limited partners)`, `limited partners list`, `select (investors|holders|clients)`, `institutional (investors|holders|clients) only`, `(to|with) our (largest|key|preferred|select|top) (holders|clients|investors|shareholders|stakeholders)`, `(sell|buy)-side (mailing|distribution|q&a)`. Same `low → medium` co-occurrence amplifier as item 95. Citation in `citations.py` cites SFA s219, Rule 10b5-2, MAR Art 14, SFO Part XIV. Tests in `test/test_contingent_tipping_mnpi.py` cover canonical recall, false-positive rejection ("market share", "circulate freely"), and amplification.

97. ~~**Reg FD selective-disclosure red-flags (item 83 closer).**~~ Shipped 2026-05-26. `SELECTIVE_DISCLOSURE_RE` in `engine.py` matches Reg FD §100(b)(1) recipient-category vocabulary — verified verbatim against 17 CFR 243.100 (Cornell LII, 2026-05-26): (i) `broker-dealer (contact|distribution|mailing|outreach)`, `sell-?side (analyst|mailing|distribution|coverage|q&a|outreach)`, `buy-?side ...`; (ii) `investment adviser (mailing|distribution|outreach)`, `13F filer`; (iii) `investment company / affiliated person` constructions; (iv) `top-?ten (holders|shareholders|investors)`, `largest institutional (holders|shareholders|investors)`; plus the canonical `analyst (day|call|q&a|breakfast|prep|briefing)` and `one-?on-?one (call|meeting|session|briefing) with [recipient]`. **Jurisdiction-gated**: the rule is only registered into the post-pass when `any(pack.code == "US" for pack in packs)` — i.e. source OR destination is US. Routing through SG-only / UK-only / EU-only does not fire the rule (Reg FD is US-specific). Added to the items 95/96 co-occurrence amplifier set: severity low standalone, medium when within ±200 chars of an MNPI substrate. Citation in `citations.py` cites 17 CFR 243.100 verbatim and lists the four recipient categories. 19 tests in `test/test_reg_fd_selective_disclosure.py` cover jurisdiction gating (fires when source=US OR destination=US; does NOT fire on SG/SG, UK/UK), recall across all vocabulary forms, precision (bare "analyst" alone, "one-on-one feedback" without `with`), and amplification. Item 94's suffix audit extended (`us_only_rules` carve-out) to cover selective_disclosure_risk under US-scoped routing.

98. **Special-category PII seed pack (item 71 partial).** Ship a conservative first slice under `src/kaypoh/review/detectors/special_category/` (NEW module — engine post-pass after the TOML-driven recognizers). v1 categories: religion (Christian/Muslim/Buddhist/Hindu/Sikh + congregation/parish/mosque/temple context words), trade-union membership (`\b(union member|NTUC|trade union|labor union)\b` + employment context anchor), political opinion (`\b(party member|PAP|WP|PSP|opposition party|ruling party)\b` + politics context anchor). Excludes health/biometric/sex-life from v1 — those need a separate medical-vocabulary lexicon and dedicated adversarial fixtures (medication brand names that are also common nouns; "union" outside labor context). Severity: high under GDPR Art 9 / PDPC special-category. Statute citation already wired in `_PII_JURISDICTION_SUFFIX`. Per-category opt-out via `KAYPOH_SPECIAL_CATEGORY_DISABLE=religion,union,political` for tenants with high false-positive sensitivity.

99. ~~**Pseudonymised-but-linkable ID seed pack (item 78 partial).**~~ Shipped 2026-05-26. Three new universal PII rules in `engine.py` (universal because the linking-key concept is statute-agnostic): `employee_id`, `customer_account_number`, `medical_record_number`. Each anchor-required (`Employee ID:` / `EMP-` / `Customer Account:` / `ACCT-` / `Patient ID:` / `MRN:`) with the capture group wrapped in `(?-i:...)` + digit-presence lookahead to defend against the false-positive case where lowercase prose follows the anchor word ("your employee ID will be linked to your NRIC" — without the case-sensitive + digit guard, "will" would match as the ID under `re.IGNORECASE`). `_amplify_pseudonymised_when_linked()` post-pass escalates `employee_id` / `customer_account_number` from medium → high when a `named_person` finding co-occurs anywhere in the document (document-scoped, not span-local — the re-link risk holds even paragraphs apart). `medical_record_number` ships at high standalone (special-category data under GDPR Art 9 + HIPAA 45 CFR §164.514). Citations in `citations.py` cite GDPR Recital 26 + PDPC Anonymisation Advisory Guidelines for the linkable-pseudonymisation doctrine; HIPAA + GDPR Art 9 for MRN. 25 tests in `test/test_pseudonymised_linkable.py` cover canonical recall (4 anchor forms × 3 rules), prose-precision (the adversarial-corpus "employee ID will be linked" case), digit-presence enforcement, document-scoped amplifier (medium alone, high with named_person, far-apart linkage still amplifies), and citation suffixes.

100. ~~**SG wedge expansion — first follow-up slice (item 48 follow-up).**~~ Partial shipped 2026-05-26. Three new TOML recognizers in `src/kaypoh/review/jurisdictions_data/SG.toml`: (a) **`sg_paynow`** — PayNow identifier anchored on `PayNow / Pay Now / PAYNOW` context word, captures UEN (legacy + T-format), NRIC, or SG mobile (`+65 [89]xxx xxxx` or bare `[89]xxxxxxx`), severity high. `capture_group=1` keeps the matched span clean. (b) **`sg_mas_licence`** — MAS-issued Capital Markets Services (CMS) or Financial Adviser (FA) licence anchored on `MAS licence|MAS No.|MAS Register|MAS ID|licence no.|licensed by MAS` context, severity medium. The anchor-required approach defends against the bare-prefix false-positive surface (CMS as "Content Management System", FA as initials). (c) **`sg_sgx_counter`** — SGX counter / cashtag (`[A-Z][A-Z0-9]{1,3}` — DBS, D05, U11, ABC1) anchored on `SGX:|SGX counter|SGX code|listed on SGX|ticker SGX|stock code SGX`, with the capture group wrapped in `(?-i:...)` to enforce uppercase even though the recognizer compiler defaults to `re.IGNORECASE` — without case-sensitive capture, "SGX is..." and "SGX in..." would false-positive on lowercase 2-letter tokens. Severity low. 30 tests in `test/test_sg_wedge_detectors.py` cover canonical recall (UEN/NRIC/mobile PayNow variants, CMS/FA with all four anchor forms, SGX colon/counter/ticker/listed-on forms) plus adversarial precision (PayNow landlines, "pay now" imperative without ID, "MAS-regulated" descriptor without licence, FA Cup years, CMS Content-Management-System tickets, SGX index/is/in lowercase tokens, 3-letter currency codes, bare DBS without SGX anchor). Citations in `citations.py` cite PDPA s13 + MAS PaymentServices Act 2019 for PayNow, SFA 2001 + FA Act 2001 for MAS licence, SFA s218 + SGX Mainboard Rule 703 for SGX counter. Remaining backlog (deferred to a second slice): IPOS registration numbers, ACRA filing references, HDB / strata / title references, URA / SLA references, contract-commercial terms (royalty rates, volume commitments).

101. ~~**Quasi-identifier combination detection — minimal viable seed (item 70 partial).**~~ Shipped 2026-05-26. `_QUASI_IDENTIFIER_RULES` frozenset in `engine.py` enumerates 30 quasi-identifier rule names (named_person + direct contact + postal-address + all shipped local government/company IDs across SG/SEA/HK/AU/JP/KR/US/UK + pseudonymised-linkable IDs from item 99). `_detect_quasi_identifier_combinations()` runs greedy left-to-right over findings sorted by `start_char`: for each window where the rightmost-quasi-ID's start_char is within 500 chars of the leftmost's start_char, count distinct rules. If ≥3 distinct rules cluster, emit a single `quasi_identifier_combination` finding spanning [window_start, max(window_end)], category PII, severity medium. The left pointer advances past the cluster after emission so overlapping windows don't double-fire. **audit_grade only** — `strict` profile skips the pass entirely (per item 70 v1 description, the seed rule is recall-floor scaffolding; the full k-anonymity probability estimate is deferred to item 70 v2). Citation in `citations.py` cites PDPA s2, GDPR Recital 26, CCPA §1798.140(v), and the Sweeney 2000 (DOB+ZIP+gender uniquely identifies 87% of US adults) result. 11 tests in `test/test_quasi_identifier_combination.py` cover the profile gate (strict=no emission, audit_grade=emit), the ≥3-distinct-rules threshold (2 doesn't fire, 3 same-rule doesn't fire, 3 distinct fires), the 500-char window boundary (close=fires, far=doesn't fire), the per-cluster-at-most-one emission invariant, and citation suffixes.

### Completed pre-flight items

These were the immediate blockers before deeper detector/product work.

90. ~~**HK / AU / JP / KR fixture seeding (depends on: item 86).** Mirror the SEA-pack discipline (`test/fixtures/legal-corpus-sea/`) for the four jurisdictions added in item 86. Produce one seed fixture per jurisdiction with hand-validated labels, then grow each corpus toward 30 docs using `scripts/generate_legal_fixture_batch.py` (gpt-4o, jurisdiction-scoped prompt variants). Seed recall + precision baselines at 1.0 in `legal-corpus-hk-au-jp-kr.lock.json` (one lock per jurisdiction or one combined file — combined is fine for v1). Detectors required before fixtures are useful: HK ID `A123456(7)`, AU TFN, JP MyNumber, KR RRN; HK CR No., AU ABN/ACN, JP corporate number, KR business registration number. Land detectors first, then fixtures, then locks. Statute citations resolved per item 85.~~ Shipped 2026-05-26. HK/AU/JP/KR jurisdiction packs, checksum validators, seed fixtures, and combined recall/precision lock are in place.

91. ~~**Run the autolabel pipeline against the 233-fixture corpus.** The synthetic corpus (118 default + 115 adversarial) was generated 2026-05-25/26 via `scripts/generate_legal_fixture_batch.py`. Every fixture carries a stub `labels.json` from the generator awaiting hand-fill of `must_detect` / `must_not_detect`. Use the auto-labeler instead of hand-review: validate on 5 fixtures first with `OPENAI_API_KEY=... python3 scripts/autolabel_batch.py --model o1 --limit 5`, spot-check the output (verbatim-text validator catches hallucinations; provenance field `_label_source: "o1-auto"` lands in every labels.json), then full sweep with `OPENAI_API_KEY=... python3 scripts/autolabel_batch.py --model o1`. [Inference] Cost ~$12 at o1 prices for full sweep; ~$1.50 with gpt-4o if budget-constrained. After labeling, run `scripts/recall_gate.py --update --reason "auto-label sweep $(date +%F)"` to refresh `recall.lock.json`; the lock-history (item 16) preserves attribution that this baseline was model-derived, not human. Spot-check ≥10% before promoting the lock baseline — model-derived labels become circular if the recall gate trains on its own teacher's verdicts.~~ Shipped 2026-05-26. `scripts/autolabel_batch.py` is parallelized; 25 fixtures were spot-checked; default/adversarial recall locks and `docs/accuracy.md` were refreshed with provenance.

### Gap-closure roadmap

33. **Broaden deterministic PII recognizers.** Add conservative detectors for DOB/age, IP address, device identifiers, US driver-license patterns, US ITIN, and EU member-state national-ID hooks. Ship each detector behind recall + precision fixtures first; default-enable only rules whose adversarial precision baseline does not regress. **Partial shipped 2026-05-26:** US SSN (`us_ssn`) with full SSA validator (rejects area 000/666/9XX, group 00, serial 0000, public sentinels 078-05-1120 / 219-09-9999), US EIN (`us_ein`) with IRS prefix allowlist validator, UK NIN (`uk_nin`) with HMRC prefix exclusion validator (rejects D F I Q U V first letters, O second letter, reserved BG/GB/KN/NK/NT/TN/ZZ prefixes), JP postal code (`jp_postal_code`), AU postal address (`au_postal_address`). 25 unit tests in `test/test_us_uk_packs.py` cover canonical recall + validator-rejection precision. Remaining: DOB/age, IP/device IDs, US driver-license, US ITIN, EU member-state national-IDs, KR postal, HK address signal.

34. **Add broad address detection.** Introduce a jurisdiction-aware address layer. SG keeps the current postal-code signal as the strict baseline; US/UK/EU start with conservative postal-address patterns; SEA packs get opt-in address recognizers where a reliable local format exists. Free-form multi-line address detection stays disabled until the corpus covers false positives in contracts, invoices, and signature blocks.

35. **Add semantic PII fallback.** Add an optional local semantic PII pass to `/review` using Presidio/spaCy or a lightweight local NER model for names, organizations-as-identifiers, addresses, dates of birth, and special-category cues. Keep it feature-flagged and off in `strict` local default until defined-term, signatory, organization, and multilingual SG precision fixtures are locked.

36. ~~Make public-status proof explicit.~~ Shipped 2026-05-25. `ReviewFinding` and `ReviewFindingResponse` now carry `source_verification ∈ {not_checked, public_source_matched, no_public_source_found, ambiguous}`. PII findings always emit `not_checked`. The `material_event` rule no longer softens severity from `PUBLIC_RE` phrasing alone — softening to `low` now requires an in-document `http(s)://` reference in the same line (the "document self-cites" carve-out) or a retriever-matched verdict under `audit_grade`. The post-retrieval pass in `engine.review()` attributes per-finding state from the aggregate retriever output: `queried`+sources → `public_source_matched`; `queried`+empty+unverified_claims → `ambiguous`; `queried`+empty → `no_public_source_found`. In-doc self-citation wins over aggregate retrieval (per-finding evidence beats document-aggregate). Test: `test/test_source_verification.py` covers all five guarantees (PII always not_checked; strict + phrasing only stays medium; strict + in-doc URL softens to low; audit_grade + sources flips to public_source_matched; audit_grade + empty flips to no_public_source_found).

37. **Production-wire LLM helper layers.** Promote LLM-defined-term extraction and inverse coverage audit from injectable helpers to named runtime components with config keys, readiness/diagnostics visibility, and privacy-ledger events. `strict` remains deterministic; only `audit_grade` may invoke these layers.

38. **Implement LLM rationale composition.** Add bounded structured rationale composition for accepted findings only. Output must be short, citation-aware, and chain-of-thought-free; it must work in `structured_tokens` mode and respect `KAYPOH_CITATIONS_OVERRIDE`.

39. ~~Make `structured_tokens` the regulated-tenant default.~~ Shipped 2026-05-25. Remote LLM endpoints now default to `structured_tokens` when `llm.llm_input_mode` is unset; local/private endpoints keep `raw_text` as the default. Explicit remote `raw_text` requires `llm.allow_remote_raw_text=true` / `KAYPOH_LLM_ALLOW_REMOTE_RAW_TEXT=1` in addition to the existing remote URL gate. `PrivacyLedgerEntryResponse` carries `input_mode`, and `/review` + legacy `/classify` append an `llm_adjudication` privacy-ledger event whenever the LLM tier is invoked.

40. **Expand evaluation corpora to compliance-grade gates.** Replace seed-scale coverage claims with locked targets: 50 default legal-contract fixtures, 50 adversarial/negative fixtures, 30 fixtures per SEA jurisdiction, OCR/PDF broken-run variants, multilingual name variants, and sector-specific finance / HR / healthcare / legal templates. Require both recall and precision locks before any new detector is marked available in the coverage table.

41. ~~Harden persistence and mapping storage.~~ Shipped 2026-05-25. Persisted mappings can be Fernet-encrypted by setting `KAYPOH_MAPPING_STORE_KEY`; legacy plaintext mappings remain readable for compatibility. `scripts/purge_mappings.py` deletes mappings by `document_hash` or by retention age with `--dry-run`, and `docs/mapping-store-hardening.md` documents key generation, retention, filesystem ACLs, and disk-encryption expectations. HMAC remains the journal-integrity primitive; mapping confidentiality and deletion are now separate operator-visible controls.

56. **Latency SLO targets + CI gate.** Publish explicit p95 latency budgets and gate them in CI via `test/benchmarks/`:

    | Path | Profile | p95 budget |
    |---|---|---|
    | `/review` | `strict` | < 500 ms (doc ≤ 10 KB extracted text) |
    | `/review` | `audit_grade` | < 3 s |
    | `/anonymize` | `strict` | < 800 ms |
    | `/anonymize` | `audit_grade` | < 4 s |

    [Inference] Targets derived from pre-send UX research: paste/Outlook-send users tolerate ≤500 ms perceptibly, ≤3 s acceptable with explicit "reviewing…" indicator (Grammarly / Notion AI bands). Benchmark fixtures cover doc-size variation (1 KB / 10 KB / 100 KB) and seed corpora. Numbers locked only after first benchmark run; until then, they are aspirational. Latency results feed back into item 32 escalation calibration so cost ↔ latency ↔ accuracy trade is explicit.

### Enterprise GTM substrate

These items unblock procurement at SG/SEA law firms and listed-company in-house teams. They are the lowest-leverage technical work but the highest-leverage commercial work, and explicitly serve the ICP defined above — not a general DLP push.

42. **Multi-tenant isolation + SSO/RBAC for the server SKU.** Partial shipped 2026-05-25. Tenant context now resolves from a configured API-key registry or validated JWT, never from caller-supplied tenant headers. Role checks cover `reviewer | maker | checker | admin | auditor`, with stricter maker/checker/admin and auditor/checker/admin gates on decision and review-state endpoints. Journals, persisted mappings, and defined-term session sidecars are partitioned under tenant-specific storage paths, and tests prove cross-tenant review, decision, mapping, and session leakage is blocked. Remaining work: production IdP packaging for Okta / Azure AD / SAML and explicit per-tenant key-management UX.

43. ~~Deployment hardening + SIEM integration.~~ Shipped 2026-05-25. `docs/deployment-hardening.md` now covers filesystem ACLs, at-rest disk encryption, Nginx / Envoy mTLS proxy shapes, secrets-manager handling, Kubernetes security context / volume posture, and SIEM setup. Runtime SIEM export is config-gated under `[siem]` / `KAYPOH_SIEM_*` and emits `kaypoh.siem.v1` JSON-over-syslog events for privacy-ledger entries, HMAC journal appends, API-key denials, HTTP errors, and mapping-store persistence/decrypt failures. Payloads hash or summarize sensitive fields so raw document text, matched text, mapping originals, public-evidence queries, reviewer rationales, and secrets do not enter SIEM.

44. **Word add-in + Outlook add-in.** Microsoft 365 add-ins hooking pre-send (Outlook) and pre-save / pre-share (Word). Same `127.0.0.1:8765/anonymize` contract as the browser extension (item 22); Office.js client; document-hash retained client-side for in-place re-identify. The Outlook add-in is the higher-leverage surface because legal/IR teams send drafts via email and the threading model gives a natural "review before send" interception point. Office store distribution unblocks IT-managed deployment via M365 admin centre.

45. **DMS connectors: iManage Work + NetDocuments.** Read-side connectors that batch-scan a matter / workspace folder, run `/review`, and surface findings inside the DMS UI as document tags. Read-only by default; write-back (anonymise-in-place) is a separate opt-in. iManage Work API + NetDocuments REST API are the two integration targets covering the [Inference] majority of SG / UK / AU law-firm DMS share — verify with each ICP pilot before sequencing.

46. ~~Published per-detector accuracy disclosure (`docs/accuracy.md`).~~ Shipped 2026-05-25; refreshed 2026-05-26 after the autolabel sweep and HK/AU/JP/KR seed packs. `scripts/generate_accuracy_doc.py` renders `docs/accuracy.md` from `recall.lock.json`, `recall_adversarial.lock.json`, `legal-corpus-sea.lock.json`, and `legal-corpus-hk-au-jp-kr.lock.json`, including corpus fixture counts, per-detector recall/precision, and known limitations. `test/test_accuracy_doc.py` fails when the committed disclosure drifts from the lock files.

47. **Clipboard + file-watcher fallback (desktop SKU).** For surfaces without a native add-in (Slack desktop, generic web textareas, native macOS/Windows apps), ship an opt-in clipboard monitor + watched-folder daemon that runs everything paste-buffered or dropped into the folder through `/review` and surfaces a system-tray notification on findings. Strict opt-in; off by default; never autoreplaces clipboard content — one-click "anonymise this" only. Bounded scope: closes the long-tail-surface gap without committing to per-app integrations.

48. **SG legal/finance sensitive-data expansion.** Add wedge-specific detectors and fixtures for PayNow IDs, MAS licence numbers, SGX stock codes / counter names, insurance policy numbers, crypto wallet addresses, court references, IPOS registration numbers, ACRA filing references, HDB / strata / title references, URA / SLA references, and contract-commercial terms such as unit pricing, discounts, volume commitments, royalty rates, and total contract value. Ship each detector only with recall + adversarial precision locks. **First slice shipped 2026-05-25:** `sg_court_citation` — SAL neutral citations (`[YYYY] SG{CA|HC|HC(A)|HC(F)|HCAR|HCAF|HCF|HC/SIC|DC|FC|MC|CRA} <num>`) registered as a recognizer on the SG pack. Severity medium, category PII. Recall + precision both 1.0 on the inline corpus in `test/test_sg_court_citation.py` (10 positives across all SAL court codes, 10 adversarial negatives covering EWCA / HKCA prefixes, round brackets, missing-code variants, 2-digit-year variants, and bracketed-year tokens that are not citations). Remaining backlog detectors (PayNow, MAS licence, SGX counter, insurance policy, crypto wallet, IPOS, ACRA filing, HDB / strata / title, URA / SLA, contract-commercial terms) still pending and follow the same recall + adversarial precision lock discipline.

49. ~~Document metadata leakage review and scrubber.~~ Shipped 2026-05-25. `/review` and `/anonymize` now report container metadata findings under `document.metadata_findings`, separate from visible-text PII/MNPI findings. `POST /documents/scrub` returns scrubbed base64 payloads plus scrub actions for DOCX properties/comments/track-change author/date attributes, PDF info metadata, and JPEG/PNG EXIF when Pillow is installed.

50. ~~Fail-closed document ingest gate.~~ Shipped 2026-05-25. PDF extraction now applies a configurable fail-closed quality gate using text-layer density, empty-page ratio, embedded image signals, and scanner/producer metadata hints. Sparse, image-only, or scanned-like PDFs return `422` with conversion guidance instead of silently reviewing partial text; text-layer PDFs continue through normal `/review` and `/anonymize` flow.

51. **Enterprise server deployment modes.** Package `kaypoh-server` for customer-managed VM/container deployment first. Document key ownership, no-content-access boundaries, upgrade process, and operational responsibilities. Keep customer-hosted/kaypoh-managed BYOC as a later premium path with a sharply separated operations plane and no read path to content, vault, or audit logs. Partial shipped 2026-05-26: deterministic Docker image (`kaypoh:local`) builds and smoke-tests; base Compose is deterministic-only and whitelists runtime env vars; `docker-compose.managed-llm.yml` is the accuracy-first managed overlay for Kaypoh/provider-key deployments with explicit tenant opt-in.

52. **Commercial validation gates.** Month 3: stop or pivot if fewer than 5 of 15 discovery calls express willingness to pay for a local/on-prem pilot. Month 4: stop, narrow, or hire if MNPI benchmark recall remains below 0.80. Month 6: stop or re-scope if no paid pilots convert. Ambitious v1 proof points: precision >= 0.95, recall >= 0.85 on an internal held-out eval set, no critical pilot incidents, and three paid pilot conversions.

53. **Source-backed why-now evidence maintenance.** Keep the demand-signal section citation-backed and date-stamped. Before using it externally, re-check LayerX, Cyberhaven, Netskope, Gartner, IMDA, MAS, OAIC, and APRA sources; drop any claim whose source cannot be recovered or whose methodology no longer supports the wording.

### Maintenance / codebase health

Recurring refactor cadence so the codebase stays debuggable, maintainable, and easy to extend as expansion items land. Each refactor is sequenced after a related feature cluster so there is real surface to consolidate. All refactors are gated by existing recall + precision locks — zero behaviour change.

M1. **Engine refactor — after item 33 (broader PII detectors).** `src/kaypoh/review/engine.py` will gain detector branches. Extract a `DetectorRegistry` so each detector (NRIC, UEN, MyKad, NIK, SSN, DOB, IP, etc.) lives in its own module under `src/kaypoh/review/detectors/{rule}.py`, plugin-registered into the engine. Engine becomes a coordinator, not a switch statement. Recall + precision locks gate the refactor.

M2. **Schemas refactor — after items 54–57 (new finding origins, reviewer identity sources).** `src/kaypoh/backend/schemas.py` will gain fields per expansion. Split into `schemas/findings.py`, `schemas/decisions.py`, `schemas/audit.py`, `schemas/llm.py`. Single import path preserved via `__init__.py` re-export.

M3. **Workflow refactor — after item 37 (LLM helpers promoted).** Standardise the runtime-component interface across `src/kaypoh/workflow/layer8_llm_adjudicator/` siblings: each component exposes `name`, `enabled_under_profile`, `privacy_ledger_events`, `health()`. `/diagnostics` and `/ready` enumerate them uniformly.

M4. **Extractor refactor — after item 61 (binary content coverage).** Extractors will multiply (DOCX-binary, PDF-binary, XLSX, PPTX, EML, MSG, ZIP, HTML, SVG, RTF, MD, image-OCR). Consolidate under `src/kaypoh/extractors/` with a common `Extractor` protocol returning `{text, metadata_findings, binary_findings, container_type}`. Format-gate (item 50) becomes per-extractor `accept(content) -> Decision`.

M5. **Persistence refactor — after items 59–60 (subject erasure + per-tenant citations).** Mapping store, session store, journal store, citations store all gain tenant + matter dimensions. Extract a `TenantScopedStore` base with consistent path layout `{base}/{tenant_id}/{store_kind}/...`. Migration script for existing single-tenant deployments.

M6. **Recurring dead-code sweep (every ~10 shipped items).** Schedule `vulture` + `ruff --select=F` + manual review of `# TODO` / `# XXX` / `# FIXME` markers. Cap at 1 day per sweep; reverts allowed if it touches anything not strictly dead. Goal is delta-readability, not codegolf.

### Deferred

28. Rust or Go span engine — only after profiling shows deterministic extraction/replacement is the bottleneck. The current bottleneck is more likely model inference and document extraction than string replacement.
