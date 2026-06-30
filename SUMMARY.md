# Junas Repo Summary

Snapshot date: 2026-06-30.

Scope: local repo inspection across root config, docs, source, integrations, scripts, tests, reports indexes, and training metadata. I did not line-read every generated fixture/report payload because the legal corpus and generated reports are large; use their manifests/status docs as the verified source for corpus state.

## Product Identity

Junas is a pre-send review runtime for GenAI prompts, email, document sharing, and related workflow submissions. Its stated job is to detect PII/personal data and MNPI before content leaves a workflow, return statute-cited findings, record audit evidence, and route to rewrite/redaction/pseudonymization/approval/hold/public-citation actions.

The backend FastAPI service is the trust boundary. UI adapters are optional activation surfaces.

Non-goals from docs:

- Not legal advice.
- Not a full enterprise DLP replacement.
- Not eDiscovery.
- Not endpoint control.
- Not a CASB.
- Not an IdP policy engine.
- Not population-level/procurement-grade accuracy evidence unless docs explicitly promote a benchmark.

## Repo Shape

Top-level runtime/config/docs:

- `pyproject.toml`: Python package metadata, deps, extras, and console script metadata.
- `uv.lock`: locked dependency state.
- `config.toml`: default deterministic/no-cloud config.
- `.env.example`: documented env vars and provider examples.
- `Dockerfile`, `docker-compose.yml`, `docker-compose.managed-llm.yml`: container launch paths.
- `README.md`, `TODO.md`, `INTEGRATIONS.md`: main product/status docs.
- `docs/`: architecture, install/run, schema, security, governance, roadmap, accuracy, limitations.
- `scripts/`: preflight, runtime verification, benchmark/eval, audit, retention, packaging, OpenAPI/example tooling.
- `src/junas/`: backend, review engine, policy, anonymization, config, external provider guardrails, client SDK.
- `integrations/`: browser extension, Outlook add-in, Word add-in, desktop watcher.
- `packaging/`: local desktop/PyInstaller packaging.
- `test/`: unit/integration/eval tests and fixture harnesses.
- `training/`: distillation/promotion metadata and export helpers.
- `reports/`: generated latency/layer/eval outputs.
- `archive/`, `asset/`, `config/`: archived docs/assets/config variants.

No repo-local `AGENTS.md` was present at inspection time.

## Python Package

`pyproject.toml`:

- Package: `junas`.
- Version: `0.1.0`.
- Python: `>=3.10`.
- Description: "Pre-send PII anonymisation and MNPI review runtime for GenAI prompts."
- Core deps include `fastapi`, `uvicorn`, `pydantic`, `httpx`, `spacy`, `presidio-analyzer`, `presidio-anonymizer`, `prometheus-client`, `pypdf`, `cryptography`, `PyJWT`, `Pillow`, `numpy`.
- Extras:
  - `dev`: `pytest`, `ruff`, `mypy`.
  - `ocr`: `pytesseract`, `pypdfium2`.
  - `server`: cloud vision/public evidence deps.
  - `packaging`: `pyinstaller`.
- Potential packaging item to verify before relying on it: `pyproject.toml` advertises `junas-watch = junas.desktop.watch:main`, while the inspected tree contains `integrations/desktop/watch.py` and no `src/junas/desktop/`.

## Install And Run

Canonical local workflow uses `uv`:

- `uv sync --extra dev`
- `uv run python -m spacy download en_core_web_sm`
- `uv run python scripts/preflight.py --strict`

Backend launch paths:

- `./scripts/launch/run_backend_only.sh`
- `./scripts/launch/run_dev.sh`
- `./scripts/launch/run_prod.sh`
- Manual: `uv run uvicorn junas.backend.main:app --host 0.0.0.0 --port 8000`
- Docker: `docker compose up --build`

Local desktop SKU:

- `uv sync --extra local --extra packaging`
- `./scripts/package_macos_desktop.sh`
- PyInstaller artifacts land in `dist/junas-local/`.
- Local SKU binds `127.0.0.1:8765` by default and is deterministic/offline by default.
- Packaging docs state the local spec excludes public-evidence and LLM-adjudicator modules.

Server SKU:

- Production preflight: `JUNAS_DEPLOYMENT_MODE=production uv run python scripts/preflight.py --deployment production --strict`
- Managed LLM overlay requires explicit provider key and tenant/deployer opt-ins.

## Runtime Defaults

`config.toml` defaults:

- `api.host = 127.0.0.1`.
- `api.port = 8000`.
- `api.max_request_bytes = 10485760`.
- `pipeline.layers = []`.
- Public evidence disabled.
- LLM disabled.
- LLM provider default config references local `vllm` style settings, but disabled by default.
- Remote LLM gates default false.
- Privacy mode defaults to sanitized-only for external paths.
- Document ingest is fail-open by default; image-only PDF rejection is enabled.
- Tenancy disabled by default.
- SIEM disabled by default.
- Local daemon ACL disabled in default config, with allowed origin templates for local, browser extension, ChatGPT, Claude, Gemini.

Local SKU invariant from README/docs/tests:

- Offline-default.
- Should not require torch/transformers/sentence-transformers/redis/xgboost/scikit-learn/pandas/accelerate/external HTTP in local runtime tests.

Server SKU:

- Optional public evidence and LLM helper paths exist for opted-in tenants.
- `review_profile=strict` does not invoke helper layers.

## Main API Surface

Health/ops:

- `GET /health`
- `GET /ready`
- `GET /diagnostics`
- `GET /metrics`

Review/rewrite:

- `POST /review`
- `POST /pseudonymize`
- `POST /anonymize`
- `POST /redact`
- `POST /redact-pii`
- `POST /hold-until-public`
- `POST /cite-public-source`
- `POST /request-approval`
- `POST /safe-rewrite`
- `POST /reidentify`
- `POST /documents/scrub`

Compatibility:

- `POST /classify`
- `POST /classify/batch`

Review sessions:

- `POST /review/{review_id}/decision`
- `GET /review/{review_id}`

Local pairing:

- `/local/pairing/status`
- `/local/pairing/start`
- `/local/pairing/approve`
- `/local/pairing/claim`

Schema source:

- Live source of truth is FastAPI `/openapi.json`.
- Examples regenerate with `scripts/export_openapi_examples.py`.

## Request Model

`ReviewRequest` accepts either inline text or base64 document input. Verified fields include:

- `text`
- `document_base64`
- `filename`
- `mime_type`
- `source_jurisdiction`
- `destination_jurisdiction`
- `document_type`
- `review_profile`: `strict` or `audit_grade`
- `entity_id`
- `include_suggestions`
- `degraded_policy`: `allow`, `warn`, or `block_send`
- workflow fields: `surface`, `workflow`, `actor_role`, `recipient_domains`, `recipient_count`, `attachment_count`, `sensitivity_label`, `external_destination`, `requested_action`
- session/matter fields: `session_id`, `matter_id`

Validators sanitize control chars/domains and require either text or document payload.

`ClassifyRequest` text max is `100000`.

`send_allowed` remains for compatibility but is derived from `policy_decision.send_allowed`; new adapters should read `policy_decision` first.

Review/rewrite responses include `review_expires_at`; adapters must refresh review after expiry or if reviewed text, recipients, attachments, destination context, or tenant policy context changes.

## Backend Modules

Key backend files:

- `src/junas/backend/main.py`: FastAPI app, endpoint wiring, startup diagnostics, review/rewrite/session routes.
- `src/junas/backend/schemas.py`: Pydantic request/response models.
- `src/junas/backend/auth.py`: API key/JWT/tenant auth and role checks.
- `src/junas/backend/local_auth.py`: local daemon ACL, pairing, local signed tokens.
- `src/junas/backend/observability.py`: Prometheus metrics.
- `src/junas/backend/siem.py`: sanitized SIEM event export.
- `src/junas/client.py`: sync/async Python client.

## Review Engine

Core engine: `src/junas/review/engine.py`.

Primary class: `PreSendReviewEngine`.

High-level flow:

1. Resolve source/destination jurisdiction packs; stricter jurisdiction applies where needed.
2. Extract/merge session and matter defined terms.
3. Parse document structure.
4. Run deterministic PII, personal-data, MNPI, blackout, quasi-identifier, and conjunctive-MNPI detectors.
5. Score PII/MNPI/document risk.
6. Attach citations, source verification state, public evidence, suggestions, coverage warnings, privacy ledger, degraded modes, and policy context.
7. For `audit_grade`, optional helper layers can run only when configured and gated.

Detected concepts include:

- Personal identifiers: email, phone, passport, person, address, SG NRIC/UEN/postal, HKID, AU TFN/ABN/ACN, JP My Number/corporate, KR RRN/business, US SSN/EIN/ITIN, UK NIN, IN Aadhaar/PAN, CN resident/USCC, AE Emirates ID, SA IDs, TH national ID, and others via jurisdiction packs.
- Financial/business identifiers and scalars: bank account, financial amounts, percentages, share counts, deal value, revenue, EBITDA, guidance values.
- MNPI contexts: material events, M&A, transaction codename, definitive agreement, MAC clauses, embargo/nonpublic markers, selective disclosure, tipping, insider list, information barrier, blackout periods, legal proceedings, cyber, crypto/DPT, ESG, pharma, energy reserves, financial-services regulatory events.
- Privacy/special contexts: special categories, minor data, employee/customer/medical/internal IDs, privacy event markers, quasi-identifier combinations, singling-out.

Verified invariant target from docs/tests/code comments: LLM advisory layers are not allowed to suppress deterministic-high findings. Treat deterministic findings as the controlling source of truth unless code changes prove otherwise.

## Jurisdictions

Jurisdiction packs live in `src/junas/review/jurisdictions_data/*.toml`.

Packs present:

- `AE`
- `AU`
- `CN`
- `EU`
- `HK`
- `ID`
- `IN`
- `JP`
- `KR`
- `MY`
- `PH`
- `SA`
- `SEA`
- `SG`
- `TH`
- `UK`
- `US`
- `VN`

Unknown jurisdiction falls back to baseline pack behavior.

Recognizers verified from TOML/code scan:

- AE: Emirates ID, trade licence, passport.
- AU: TFN, ABN, ACN, postal address.
- CN: resident ID, USCC, mobile phone, passport.
- HK: HKID, CR number.
- ID: NIK.
- IN: Aadhaar, PAN, GSTIN, Voter ID.
- JP: My Number, Corporate Number, postal code.
- KR: RRN, business registration.
- MY: MyKad.
- PH: PhilSys PSN, TIN.
- SA: National ID, Iqama, Commercial Registration.
- SG: court citation, PayNow ID, MAS licence, SGX counter, IPOS trademark number, ACRA transaction, HDB reference, SLA land/strata lot, SLA/MCST plan, URA planning reference.
- TH: Thai national ID.
- UK: NIN.
- US: SSN, EIN, ITIN.
- VN: CCCD.

## Policy Engine

Policy code:

- `src/junas/policy/engine.py`
- `src/junas/policy/config.py`

Policy decisions:

- `allow`
- `warn`
- `rewrite_required`
- `approval_required`
- `block`

Action catalog:

- `redact_pii`
- `pseudonymize`
- `safe_rewrite`
- `cite_public_source`
- `request_approval`
- `hold_until_public`
- `proceed_with_warning`

Default profile behavior:

- High MNPI with public evidence can warn.
- High MNPI with reviewer approval can warn.
- High MNPI without required evidence/approval blocks and requires hold/approval actions.
- High PII can require rewrite or approval depending on actor/workflow context.
- Low/medium risks warn.
- Cross-border/external contexts can warn.
- Policy config validates known sections, actions, domains, and production `policy_version`.

## Rewrite And Data-State Endpoints

`/pseudonymize`:

- Same review plus reversible deterministic placeholders.
- Mapping returned.
- Optional mapping persistence when review persistence is enabled.

`/anonymize`:

- Irreversible placeholder-only output.
- No mapping returned/persisted.
- Docs explicitly state this is not statistical anonymization.

`/redact`:

- Opaque text markers.
- No mapping.
- No original matched text in redaction response.

`/redact-pii`:

- PII-only deterministic replacements.
- MNPI passages remain visible and flagged.

`/safe-rewrite`:

- Deterministic policy-approved replacements.
- No LLM call per schema docs.
- No mapping persistence.

`/hold-until-public`:

- High-severity MNPI hold output with display-safe user reasons and audit rationale.

`/cite-public-source`:

- Requires `review_profile=audit_grade`.
- Returns source URL, server retrieval timestamp, and privacy-ledger entry.

`/request-approval`:

- Records pending approval in HMAC journal.
- Returns reviewer-role requirements.

`/reidentify`:

- Restores placeholders from caller-supplied mapping or persisted pseudonymization document hash.

## Anonymization And Mapping Store

Core files:

- `src/junas/anonymize/engine.py`
- `src/junas/anonymize/mapping_store.py`

Behavior:

- Deterministic placeholder mapping for accepted findings.
- PII finding types map to placeholders such as email, phone, passport, person, address.
- Some MNPI scalar types can be placeholdered.
- Quasi-identifier combinations and conjunctive MNPI are not replaceable by the generic placeholder path.
- Overlap resolution uses priority/dedup logic.
- Reidentification replaces placeholders from mapping data.

Mapping persistence:

- Stored by document SHA under `${JUNAS_JOURNAL_DIR}/mappings/<hash>.json`.
- `JUNAS_MAPPING_STORE_KEY` enables Fernet envelopes.
- Without that key, plaintext-v1 compatibility exists in code.
- `JUNAS_SUBJECT_INDEX_KEY` is required when saving mappings.
- Encrypted mapping load fails closed if key is missing/wrong.
- Existing plaintext mappings remain readable for compatibility and are not auto-rewritten.

Security caveat:

- Do not claim mapping files are always encrypted. Code/docs show encryption is conditional on `JUNAS_MAPPING_STORE_KEY`.

## Document Ingest

Core files:

- `src/junas/review/document.py`
- `src/junas/review/container_scan.py`
- `src/junas/review/metadata.py`
- `src/junas/review/image_scan.py`

Supported/inspected inputs include:

- Inline text.
- Base64 documents.
- TXT/Markdown/JSON.
- PDF.
- DOCX.
- XLSX.
- PPTX.
- EML.
- HTML/SVG/RTF.
- Images when OCR is enabled.
- ZIP/TAR/container scanning.

Container safety caps:

- Max depth: 3.
- Max entries: 256.
- Max member: 25 MB.
- Max total: 100 MB.
- Compression ratio cap: 100.

Container/document risk handling:

- Macro Office files are refused/degraded.
- Encrypted/password PDF/zip are refused/degraded.
- Unsafe paths are detected.
- `.msg` and `.7z` are not supported by default.
- Hidden DOCX/XLSX/PPTX/PDF/EML/HTML/SVG/RTF structures are surfaced or degraded depending on mode.
- Unsupported or partially unreadable payloads fail-open by default; set `JUNAS_DOCUMENT_FAIL_CLOSED=1` for rejection.
- Request-level `degraded_policy=block_send` sets `send_allowed=false` when degraded coverage is present.

Metadata scrub:

- DOCX core/app/custom/comments/track-change metadata.
- PDF info metadata.
- Image EXIF/GPS/info.

Image/OCR:

- Local Tesseract support via OCR extra.
- Cloud OCR providers: OpenAI Vision, Google Vision, AWS Rekognition, Azure Vision.
- Cloud OCR is guarded by `PrivacyGuard` and tenant opt-in.
- OCR findings can map to redaction regions.
- PDF image redaction can flatten page pixels; docs warn this can lose signatures/forms/layers/editable text.

## Audit, Journal, Sessions, Erasure

Journal:

- `src/junas/review/journal.py`
- HMAC-chained JSONL under `${JUNAS_JOURNAL_DIR:-./junas-journal}/journal.jsonl`.
- Tenant-scoped subdirs exist when tenancy is enabled.
- Default dev key fallback exists if no `JUNAS_JOURNAL_KEY`.
- Optional keystore via `JUNAS_JOURNAL_KEYS_FILE`.
- Supports chain verification and key rotation sentinel.

Sessions/decisions:

- `src/junas/review/decisions.py`
- Event types include `review_started`, `decision_recorded`, `anonymize_applied`, `audit_exported`, `coverage_warning`, `policy_decision_recorded`, `subject_erasure_recorded`, `approval_requested`.
- Decision actions include `accept`, `reject`, `rewrite`, `approve`, `policy_exception`, `accept_risk`, `request_changes`, `hold`.
- Latest decision per finding wins.
- Only authorized `reject` removes a finding from downstream anonymization input; undecided findings stay in scope.

Subject erasure:

- Uses HMAC reverse index under `${JUNAS_JOURNAL_DIR}/subject_index/` or tenant equivalent.
- Deletes reversible mapping files and appends tombstone events.
- Does not universally delete append-only journals, SIEM exports, logs, backups, cold archives, or legal-hold records.
- Operators must separately enforce retention/legal-hold policy.

Security caveats:

- Do not claim OS-level append-only semantics are implemented by the app.
- Do not claim default journal key is production-safe.
- `TODO.md` flags removing default journal HMAC fallback and reducing persisted matched-span exposure as open security hardening work.

## Auth, Tenancy, Local ACL

Server auth:

- `src/junas/backend/auth.py`
- Tenancy disabled by default.
- With tenancy disabled, optional global `JUNAS_API_KEY` can gate access.
- With tenancy enabled, credentials come from API key registry and/or JWT.
- JWT supports HS256 and JWKS-backed verification.
- Tenant ID is derived from validated credential/JWT, not caller-supplied tenant headers.
- SIEM denial events are emitted for auth failures.

Roles:

- Review/rewrite: `reviewer`, `maker`, `checker`, `admin`.
- Decision recording: `maker`, `checker`, `admin`.
- Review-session read/audit: `auditor`, `checker`, `admin`.

Local daemon auth:

- `src/junas/backend/local_auth.py`
- Header: `X-Junas-Local-Token`.
- macOS Keychain or `~/.junas/local_daemon_token` with mode `0600`.
- Pairing code digest.
- Signed local client tokens use HS256 with issuer/audience/scope.
- Origin allowlist uses glob/fnmatch behavior.

Local pairing flow:

1. Client starts pairing.
2. Desktop/admin approval.
3. Client claims signed expiring token.
4. Protected endpoints accept `X-Junas-Local-Token`.

## Observability And SIEM

Metrics:

- `src/junas/backend/observability.py`
- Prometheus counters/histograms/gauges for HTTP requests, classification, policy duration, layer execution/load, required layer state, dependency state.

SIEM:

- `src/junas/backend/siem.py`
- SIEM-safe JSON events.
- Sensitive keys are hashed or dropped.
- Supports stdout or syslog sink.
- Events cover privacy ledger, journal, and security/auth activity.
- Backend request logs are documented as request ID, route, status, latency only.

Hardening docs state reverse-proxy body logging must not be enabled for Junas routes.

## External Providers And Privacy Guard

Core files:

- `src/junas/external/privacy_guard.py`
- `src/junas/external/public_evidence/inference.py`
- `src/junas/advisory/llm_adjudicator/inference.py`
- `src/junas/advisory/llm_adjudicator/structured_query.py`
- `src/junas/review/llm_defined_terms.py`
- `src/junas/review/llm_coverage_audit.py`

Public evidence:

- Disabled by default.
- Providers: `exa`, `tinyfish`, `serper`, `serpapi`, `none`.
- Sends PrivacyGuard-sanitized queries only.
- Query construction uses entity/restricted-entity terms, event terms, and years.
- Returns disabled/skipped/error/queried state, sources, query records, privacy ledger.

PrivacyGuard:

- Redacts email, phone, money, percent, long numbers.
- Truncates outbound content.
- Modes include `sanitized_only`, `derived_hashes_only`, `disabled`.
- Cloud OCR/content checks require tenant opt-in.
- Privacy ledger records hashes/content type.

LLM advisory:

- Disabled by default.
- Providers: `vllm`, `ollama`, `openai`, `azure_openai`, `local_distilled`, `none`.
- Remote LLM defaults to `structured_tokens` when mode unset.
- Remote base URL requires deployer opt-in.
- OpenAI/Azure require tenant opt-in.
- Remote raw text requires explicit `allow_remote_raw_text`.
- Structured-token mode sends body hash, rule/category/severity/jurisdiction/context-window hashes, and public evidence counts.
- Output is clamped to closed vocabularies and leak-prone fields are blocked.

LLM governance:

- `training/distillation/promotion_manifest.json` is the promotion source.
- Docs state no `local_distilled` adapter is promoted in this repo state; manifest is `promoted=false`.
- Promotion requires model card, privacy eval, corpus eval report, adapter dir, agreement threshold, and invariant threshold.
- Required privacy checks include structured-token default, remote raw text blocked, tenant consent required, privacy ledger recorded, and PDPC GenAI personal-data review.

## Integrations

Direct API:

- Baseline integration path.
- Python client in `src/junas/client.py`.
- Use when no UI adapter is needed.

Browser extension:

- `integrations/browser_extension/`
- Manifest V3.
- Name: Junas Local Review.
- Permissions include storage, context menus, active tab.
- Host permission for `http://127.0.0.1:8765/*`.
- Content scripts target ChatGPT, Claude, Gemini.
- `adapters.js` contains site selectors.
- `content.js` can intercept paste/submit, send prompt/selection to service worker, and show a fixed panel.
- `service_worker.js` calls local review/rewrite endpoints and manages local/Bearer token headers.
- Current maturity: supported target for managed GenAI prompt review.

Outlook add-in:

- `integrations/outlook_addin/`
- Uses Office.js Smart Alerts pre-send hook.
- Default endpoint: `http://127.0.0.1:8765`.
- Default send timeout: 4000 ms.
- Collects subject, body, recipients, attachments.
- Calls `/review` with workflow/email context and `degraded_policy=block_send`.
- Maps backend failure to hard block.
- Maps policy/degraded state to allow, prompt_user, soft_block, or hard_block behavior.
- Taskpane supports endpoint/token/timeout config, pairing, manual review/redact display.
- Current maturity: supported target.

Word add-in:

- `integrations/word_addin/`
- Taskpane review of selected text or body.
- Uses `/review` with document type `word_document`.
- Docs mark it as user-triggered review, not send-time enforcement.
- Current maturity: experimental.

Desktop watcher:

- `integrations/desktop/watch.py`
- CLI for explicit files, watched folder, and clipboard on Darwin.
- Posts to `/review`.
- Optionally calls `/anonymize` and writes `<filename>.anonymized.txt`.
- Supports local token header and macOS notification.
- Current maturity: experimental local fallback, not enterprise enforcement.

DMS hook:

- `src/junas/integrations/dms.py`
- Neutral JSON manifest scanner for iManage/NetDocuments-style exports.
- Read-side only; no vendor SDK is shipped.
- Current maturity: experimental.

Planned from `INTEGRATIONS.md`:

- Slack: planned; no adapter source yet.
- Google Workspace: planned; no adapter source yet.

## Client SDK

`src/junas/client.py` provides sync and async HTTP clients with typed Pydantic models.

Methods include:

- health/ready/diagnostics/metrics
- classify/classify_batch
- review
- anonymize
- pseudonymize
- redact
- safe_rewrite
- request_approval
- scrub_document
- reidentify

Helper functions:

- `classify_text`
- `async_classify_text`

## Scripts And Ops

`scripts/README.md` classifies stable entrypoints.

Runtime/launch:

- `scripts/launch/run_backend_only.sh`
- `scripts/launch/run_dev.sh`
- `scripts/launch/run_prod.sh`
- `scripts/preflight.py`
- `scripts/preflight_production.py`
- `scripts/verify_runtime.sh`
- `scripts/watch_backend_status.py`
- `scripts/trace_request_logs.sh`
- `scripts/smoke_local_daemon_acl.py`

Verification:

- `scripts/verify_runtime.sh` runs preflight, ruff on key paths, focused unit tests, starts uvicorn on a free port, and smoke-checks health/ready/diagnostics/metrics/review/pseudonymize/anonymize/redact/classify.
- `scripts/preflight.py` checks runtime settings, spaCy model, pypdf, Pillow, production auth/secrets/persistence requirements, optional provider gates.

Eval/corpus:

- `scripts/recall_gate.py`
- `scripts/generate_accuracy_doc.py`
- `scripts/benchmark_latency.py`
- `scripts/benchmark_latency_corpus.sh`
- `scripts/check_latency_slo.py`
- candidate corpus generation/review/stage-gate/bucketing/reconciliation scripts.
- layer attribution and defensibility report scripts.

Admin/audit:

- `scripts/export_audit_pack.py`
- `scripts/verify_audit_pack.py`
- `scripts/verify_journal.py`
- `scripts/erase_subject.py`
- `scripts/purge_mappings.py`
- `scripts/generate_tenant_credentials.py`
- `scripts/scan_dms_manifest.py`
- `scripts/check_retention_manifest.py`
- `scripts/promote_journal_to_corpus.py`

Packaging/clients:

- `scripts/package_macos_desktop.sh`
- `scripts/package_browser_extension.sh`
- `scripts/render_outlook_manifest.py`
- `scripts/validate_outlook_manifest.py`
- `scripts/check_python_clients.sh`
- `scripts/export_openapi_examples.py`

## Tests And Evaluation

Top-level test count at inspection: 118 `test_*.py` files under `test/`.

Coverage areas visible from test names/docs:

- API auth and tenant isolation.
- Policy engine/config/decision contract.
- Runtime settings/preflight/local SKU.
- Review endpoints and response formatting.
- Safe rewrite/redact/hold/cite-source/request-approval endpoints.
- Journal, key rotation, audit pack, SIEM, subject erasure, mapping store.
- Document hardening, metadata, image scan, OCR paths.
- Browser/Office/desktop integration tests.
- Jurisdiction packs and validators.
- MNPI detectors: blackout, conjunctive, contingent tipping, information barrier, Reg FD, cyber/ESG/crypto/pharma/sector contexts.
- PII detectors and special categories/minor data/quasi-identifiers/singling-out.
- Corpus recall, precision guards, layer attribution, latency SLO, benchmark regression.
- OpenAPI docs/snapshot.
- Packaging scripts and launch scripts.

Accuracy docs:

- `docs/accuracy.md` is generated.
- Corpus locks listed there: default legal 147, adversarial 134, SEA 5, HK/AU/JP/KR 4, reviewed candidate 1428.
- Known limitation: locked regression baselines are small hand-labelled corpora, not population-level claims.
- Public evidence and LLM helper layers are excluded from that accuracy document unless regenerated with them.

Candidate corpus:

- `docs/candidate_corpus_status.md` reports corpus `test/fixtures/legal-corpus-candidates`.
- Eval report: `reports/layer-attribution/20260608-strict-item70v2_strict_candidate_eval.json`.
- 17 jurisdictions.
- 1,428 docs.
- 84 docs per jurisdiction.
- Approved labels 1,428.
- Pending labels 0.
- Stage B: 17.
- Strict recall 1.0000 across listed jurisdictions.
- Precision range in table roughly 0.8992 to 0.9377.
- Treat this as internal candidate/eval evidence unless promoted by docs.

Miss concentration:

- `docs/miss_concentration.md` reports strict profile, miss count 23138.
- Main buckets: coverage_gap, conjunction_miss, singling_out_miss, needs_review, true_inference_miss.
- Top detector-family concentrations include mnpi_context, direct_identifier, mnpi_lexicon, privacy_event.

Latency:

- `test/benchmarks/latency_slo.py` and `test/benchmarks/latency_slo_budgets.json` define latency SLO checks.
- `reports/` contains generated latency outputs.

## Security And Deployment Hardening

Docs:

- `docs/threat-model.md`
- `docs/admin-security.md`
- `docs/deployment-hardening.md`
- `docs/mapping-store-hardening.md`
- `docs/llm-governance.md`

Threat model data flow:

1. Client sends inline text or base64 doc.
2. Ingest extracts text/metadata/structure/optional images.
3. Deterministic engine creates PII/MNPI findings.
4. Rewrite endpoints produce pseudonymized/anonymized/redacted text.
5. Optional persistence writes tenant-scoped journals/mappings/subject index/sessions/matter terms.
6. Optional public evidence/LLM layers run only after privacy gates and opt-ins.
7. SIEM emits redacted JSON with hashes/counts, not raw document payloads.

Deployment recommendations:

- Run as dedicated service account.
- Keep runtime state out of user-writable dirs.
- Protect `/etc/junas/config.toml`, journal dir, and logs with owner/mode controls.
- Use disk/volume encryption even if mapping encryption is enabled.
- Terminate TLS at reverse proxy.
- Use mTLS at proxy if required.
- Enable tenancy for multi-tenant server deployments.
- Inject secrets from secret manager or mounted files.
- Keep provider/API/JWT/journal/mapping/subject-index secrets out of checked-in config and shell history.
- Use read-only images and minimal writable volumes in Kubernetes.
- Restrict ingress and egress with network policy.

Secrets:

- `JUNAS_API_KEY`
- `JUNAS_JOURNAL_KEY`
- `JUNAS_JOURNAL_KEYS_FILE`
- `JUNAS_MAPPING_STORE_KEY`
- `JUNAS_SUBJECT_INDEX_KEY`
- provider keys such as `JUNAS_EXA_API_KEY`, `JUNAS_TINYFISH_API_KEY`, `JUNAS_LLM_API_KEY`

Known residual risks:

- Operator remains responsible for identity policy, retention, backups, legal hold, and user training.
- Subject erasure is not universal deletion.
- Lost encrypted mapping key means persisted mapping recovery is not possible.
- Remote/cloud paths require careful tenant and deployer opt-ins.
- Unsupported/partially readable documents are degraded fail-open by default unless fail-closed mode is enabled.

## Known Limitations

From `docs/known-limitations.md` and TODO/code:

- Not legal advice or procurement-grade legal evaluation.
- `.msg` and `.7z` degrade fail-open unless fail-closed is enabled.
- PDF signatures/XFA/forms/annotations/embedded files/URIs are surfaced but cryptographic validation is not performed.
- EML/DOCX/XLSX/PPTX/ZIP/TAR scan is bounded and best-effort.
- Macro Office files fail-open/degrade unless fail-closed rejects them.
- Image OCR is optional.
- Public evidence and LLM are disabled by default.
- Junas does not parse SAML assertions directly.
- Windows desktop packaging is not shipped by default.
- Browser/Office local pairing requires desktop/admin approval.
- Manual redaction has lower adoption risk than workflow-capture integrations.
- Accuracy/eval docs are internal unless promoted.
- Mapping encryption is conditional.
- Default dev journal key fallback exists.
- TODO flags additional object auth/rate limiting/body size/local daemon CSRF-CORS/SSRF/log regression/security docs as open hardening work.

## Roadmap And Future Direction

Source: `docs/roadmap.md`, `TODO.md`, `INTEGRATIONS.md`.

Current strategic direction:

- Keep deterministic review engine as runtime source of truth.
- Maintain API-first backend contract.
- Promote adapters based on workflow value, privacy evidence, QA, and admin controls, not technical feasibility alone.
- Treat Outlook Smart Alerts and managed browser GenAI extension as main supported adapter targets.
- Keep Word taskpane and desktop watcher experimental unless promotion criteria are met.
- Expand direct integration contracts so vendors/adapters can use the API without changing the trust boundary.
- Harden security before production claims: tenant isolation, object auth, local daemon ACL/CSRF/CORS, rate limits, body-size tests, SSRF tests, SIEM/log regression, mapping encryption, journal key handling, retention, SBOM/dependency scanning, release checklist.
- Improve evaluation independence: avoid circular runtime-generated ground truth, add independent MNPI labels, external benchmark comparisons, precision gates, promotion docs, dashboards.
- Build admin/reviewer workflows: read-only review session list, policy config UI, reviewer queue, false-positive triage, audit export UI, auth/telemetry/tests.
- Document adapter protocol, failure handling, auth, privacy, telemetry, recipient/document context, OpenAPI examples, compatibility matrix, DMS vendor docs, Slack/Google Workspace notes, certification checklist.

Open TODO themes:

- Browser extension hardening: selector failure behavior, privacy tests, enterprise deployment docs, permission review, MV3 lifecycle tests, Playwright smoke, telemetry, tenant adapter policy, QA matrix.
- Desktop watcher: mark experimental, threat model, config sample with clipboard disabled, output/auth tests, docs as fallback not enforcement, LaunchAgent admin controls.
- Feedback loop: journal-to-corpus promotion path, taxonomy, payload extension, review queue scripts, break recall-gate circularity, privacy-safe telemetry, no-train invariant, retention/eval/precision gates.
- Security: mapping-store encryption mandatory, reidentify fail-closed tests, remove default journal HMAC key, avoid persisting matched spans by default, fixture secret scrub CI, dependency scanning, SBOM, release checklist.
- Docs: update install/running/deployment, architecture diagrams, sequence diagrams, deployment comparison, limitations, FAQs, migration guide, correct unconditional encryption/append-only claims.
- Eval: TAB benchmark, ai4privacy PII masking, PIIBench notes, Presidio conventions, independent MNPI labels, deterministic singling-out scorer, conjunctive MNPI element scorer, LLM-tier residual boundary.

Do not tell a chatbot these are already complete unless it verifies current TODO/code.

## Chatbot Usage Guidance

For repo Q&A, prefer this hierarchy:

1. `src/junas/backend/main.py`, `src/junas/backend/schemas.py`, and `/openapi.json` for live API behavior.
2. `src/junas/review/engine.py` and detector modules for detection behavior.
3. `src/junas/policy/engine.py` and `src/junas/policy/config.py` for policy decisions.
4. `config.toml`, `src/junas/configs/runtime.py`, `.env.example` for runtime settings.
5. `docs/schema.md`, `docs/architecture.md`, `docs/running.md`, `docs/install.md` for supported public contract.
6. `TODO.md` for unfinished work and caveats.
7. `test/` for expected behavior and regression constraints.

Claims to avoid unless re-verified:

- "Junas is legal advice."
- "Junas replaces DLP."
- "All mappings are encrypted."
- "Subject erasure deletes all copies everywhere."
- "LLM paths are active by default."
- "Local SKU uses remote/cloud calls."
- "Accuracy numbers are procurement-grade."
- "Slack or Google Workspace adapters exist in source."
- "Word add-in enforces send-time policy."
- "Desktop watcher is enterprise enforcement."

Useful mental model:

- The deterministic engine finds and scores risk.
- Policy decides workflow action.
- Rewrite endpoints apply deterministic actions.
- Journals and SIEM create audit evidence.
- Optional external/LLM layers are gated advisory aids.
- Adapters should be thin clients that collect workflow context, call `/review`, obey `policy_decision`, and avoid retaining raw content outside documented runtime boundaries.
