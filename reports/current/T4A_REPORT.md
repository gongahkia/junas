# T4A — Existing AI output integrity and privacy

Date: 2026-11-22 (Asia/Singapore).

## Outcome and scope

**PASS for the T4A mocked integrity/privacy scope.** Both Python CI runtime suites, focused checks, all nine historical gates and exact strict-profile parity passed. AI coverage and term proposals remain unverified advice; adjudication cannot replace scored risk. This verdict does not establish real-model detection accuracy or production readiness.

The paused implementation was already recorded in `773665c605afc3ac50c893361aff082c5e44477e` when work resumed. Its baseline is `13e98d45bcf9d8479bd4f25a51261c8393551343`. Earlier reproduction evidence used `b95875c05d19de8f6fec47e0339e83d4973292cd`; the intervening commit contains the user's T3B annotation work, with no classifier-source changes. The resume preserved that work and reviewed the existing implementation rather than replacing it.

This is a mocked integrity/privacy assessment, not a detection-accuracy experiment. No provider inference, model training, benchmarking, protected-holdout use, annotation generation, label/lock updates, README edits, commit or push was performed during the resumed work.

## Existing architecture and dependencies

`ReviewPipeline` loads `RuntimeSettings`, extracts text, and creates `PreSendReviewEngine`. Strict construction does not attach retrieval, adjudication or either LLM helper. Audit-grade construction attaches only explicitly configured components. The deterministic detectors, span validation, deduplication, scoring and risk thresholds remain the classification path.

| Component | Inputs and routing | Effect after T4A |
|---|---|---|
| LLM coverage audit (`review/llm_coverage_audit.py` → runtime helper → `httpx`) | Audit grade; preliminary MNPI score in `[25, 70)`; closed finding metadata, safe document-type enum, document hash | Deduplicated, unverified `coverage_warnings`; no findings, spans, scores or risk changes |
| Defined-term extraction (`review/llm_defined_terms.py` → runtime helper → `httpx`) | Separate audit-grade pre-pass, including PII-only inputs; at most 2,000 preamble characters; attributable disk cache | Unverified term proposals in `coverage_warnings`; no deterministic suppression authority |
| Adjudication (`advisory/llm_adjudicator/inference.py`) | Audit grade; same preliminary MNPI band; non-SAFE scored classification; local/private or explicitly allowed remote endpoint | `llm_adjudication` recommendation, separate from scored risk |
| Existing local distilled adapter (`training/distillation/student_provider.py`) | Selected through adjudicator; lazy local model loading; raw or structured mode | Shared response validation and advisory contract; no weights loaded in this assessment |
| Public-evidence retrieval (`external/public_evidence/inference.py` + `PrivacyGuard`) | Explicit configuration; same band; sanitized entity/event/year queries through existing adapters | Candidate sources, not verification of each claim; may annotate MNPI source state and the existing conjunctive detector's metadata |
| Local OCR-region LLM (`advisory/local_ocr_llm.py`) | Separate disabled-by-default experiment; clipped low-confidence fragments; configured loopback Ollama only | Validated standalone result; no integration into pipeline findings or scores |
| Optional local NER and OCR ingestion | Existing explicit local NER fallback and configured image scanner; distinct from advisory routing | Can affect extracted text or grounded findings; existing provenance/degradation and OCR consent controls retained; no new integration |
| `advisory/signals.py` | Deterministic lexical/similarity helpers | Separate experimental scores, not connected to the main risk calculation |

No provider architecture was replaced. Existing vLLM/Ollama, OpenAI-compatible, Azure and local-distilled paths remain. Provider and profile controls are still implemented in runtime configuration and retained clients.

## Confirmed defects and preserved trade-offs

| Investigation | Evidence and disposition |
|---|---|
| A: fabricated coverage evidence | Confirmed: warnings became findings with `[LLM_COVERAGE_WARNING]` and `(0, 0)` offsets. Promotion removed; warnings asserting evidence/verification fields are rejected. |
| B: duplicate score amplification | Confirmed: 20 identical warnings raised the synthetic example from 58/LOW_RISK to 100/HIGH_RISK. Advice no longer enters scoring and identical warnings are deduplicated. |
| C: scoreless label override | Confirmed: a fake SAFE response changed the label at score 58. Removed; the proposed label is visible with `classification_applied=False`. |
| D: sensitive structured identifier | Confirmed: arbitrary `entity_id` text was sent verbatim. Structured mode now rejects nonstrings and sends a SHA-256 reference. Finding metadata uses closed vocabularies; exact bounds and text are validated before transport. |
| E: ungrounded term suppression | Confirmed: proposing `Seller` removed the `Mr Seller` finding. Model terms no longer enter the suppression set; deterministic definitions and explicit caller context retain their existing behavior. |
| F: ambiguous MNPI routing | Existing latency/scope trade-off, preserved. Retrieval, adjudication and coverage audit skip PII-only and above-band inputs. The band is evaluated before conjunctive MNPI scoring. Defined-term extraction is a separate pre-pass, not subject to that band. Expanding eligibility is outside T4A. |
| G: audit grade without AI | Intentional existing deterministic profile difference, preserved. Quasi-identifier handling can differ (`quasi_identifier_seed` versus strict `singling_out_v2`) even without a provider. Do not interpret an audit/strict delta as purely AI attribution. |
| H: cache identity | Confirmed: document-only entries could reuse another model's proposals. Version 2 keys and stored identities include provider, model and prompt identity; legacy entries are ignored. Unattributed injected extractors bypass disk caching. |

Additional confirmed paths were hardened: malformed classifications/confidence/arrays no longer normalize into successful advice; an internal `TypeError` no longer retries adjudication; document-wide retrieved links no longer mark every MNPI claim `public_source_matched`. The earlier Hong Kong source-name heuristic also lacked claim-level grounding and was removed from retrieval verification. Existing deterministic in-document citation behavior was preserved, not certified as independently verified public evidence.

## Evidence and advisory contract

1. **Deterministic finding:** detector-produced evidence with valid source bounds and exact matched text. Existing deterministic scoring controls the result.
2. **AI advisory:** unverified proposal with explicit origin, provenance and advisory status. Coverage/term proposals use the existing `coverage_warnings` list; adjudication uses `llm_adjudication`. `evidence_status=unverified` and `classification_applied=False` distinguish these from evidence. Missing attribution on injected components is explicitly `unattributed`.
3. **Verified AI-supported finding:** would require exact source evidence, validated offsets and an explicit independently justified acceptance policy. T4A introduces no such detector or policy.

Adjudication retains a proposed `risk_label` and model self-reported confidence. Model-suggested public status and sources become `proposed_public_status` and `proposed_public_sources`; authoritative-facing `public_status` is `not_checked` and `matched_public_sources` is empty. Retrieved candidates carry `verification_scope=retrieval_candidates_only` and `claim_verification=not_established`.

Malformed configured outputs, disabled configured providers, transport failures and helper failures raise `ReviewLayerError` at the review boundary. They do not return a completed classification with missing advice hidden. Standalone coverage/term utilities retain their explicit fail-open option; engine calls use `fail_closed=True`. The standalone OCR experiment reports malformed output as an error/ambiguous result. Existing ingest and local NER degraded modes remain separate.

## Privacy, outbound fields and cache attribution

Structured adjudication sends a body hash, hashed entity reference, closed rule/category/severity/jurisdiction metadata, context-window hashes and retrieval status/counts. Free-form detector reasons, custom rule names, arbitrary jurisdiction strings, matched text and offsets are not forwarded. Invalid source spans are refused locally. Unknown document types become `generic`; unknown rule/jurisdiction labels become safe placeholders.

Coverage audit independently validates its summary fields and SHA-256 body hash. The defined-term helper sends raw preamble text, so a remote endpoint requires the existing raw-text permission even if adjudication itself uses structured tokens. Provider-specific tenant consent and remote URL/raw-text gates remain in configuration and runtime clients. Ordinary strict text classification does not invoke them. Configured remote OCR is a separate image-content opt-in boundary, unchanged here.

Public search continues to use `PrivacyGuard` sanitization and external-query policy. That sanitizer is pattern-based and is not a general names/identifiers anonymizer. Structured-token hashing does not change public search's separate query contract. No raw document was automatically sent to any remote provider in this work.

Cache v2 stores document hash, provider/model, prompt version/hash, endpoint and implementation identity, preamble cap, policy fingerprint and credential-scope fingerprint. Configuration checks occur before reuse. Writes are atomic; malformed or mismatched entries are treated as misses; unattributed extractors are not cached. Legacy files are neither migrated nor overwritten. Hashes are pseudonymous/linkable, not anonymization or proof of source truth. Attribution records configured identity, not immutable hosted weights or a verified local adapter revision.

## Mocked before/after examples

Synthetic document: `Acme acquisition for $2.5 billion is pending.` Baseline: two findings, score 58, LOW_RISK.

| Intervention | Before | After |
|---|---|---|
| One coverage warning | Three findings; one zero-length span; score 61 | Two findings; no zero-length span; score 58; separate advice |
| Twenty identical warnings | 22 findings; 20 zero-length spans; score 100/HIGH_RISK | Two findings; score 58/LOW_RISK; one advisory warning |
| AI proposes SAFE/public | Score 58 with overall SAFE | Score 58 with overall LOW_RISK; SAFE/public are unverified proposals |
| AI proposes Seller for `Mr Seller shall execute the contract.` | Named-person finding removed | Named-person finding retained; term proposal displayed separately |
| Second extractor returns Buyer for same text | Cached Seller reused without second call | Buyer returned; second extractor called |
| Sensitive structured entity identifier | Identifier forwarded verbatim | Identifier absent from wire JSON; hashed reference only |
| Model confidence is NaN | Successful advice with confidence 1.0 | Explicit validation rejection |

The cache reproduction uses injected extractors without full cache identity: their disk cache is now deliberately disabled. Separate regression tests exercise attributed v2 cache reuse/invalidation.

## Strict-profile parity and regression gates

The network-blocked before/after replay compared complete serialized `ReviewResult` objects, including every finding field, scores, classification, jurisdictions, suggestions, advisory fields, privacy ledger and degraded modes. It used the nine historical corpus directories, their existing label metadata and the same frozen Python 3.12 environment, with `JUNAS_*` overrides removed. No provider was attached. Source snapshots were loaded in separate processes; corpus/label/lock fingerprints are recorded in the evidence JSON.

**1,722 documents and 27,034 findings matched exactly.** Changed findings, scores, classifications, advisories and degraded modes: **zero**. Invalid spans and exact duplicate findings: **zero**.

| Corpus | Documents | Findings | Exact parity |
|---|---:|---:|---|
| legal-corpus | 147 | 2,460 | yes |
| legal-corpus-adversarial | 134 | 2,328 | yes |
| legal-corpus-sea | 5 | 52 | yes |
| legal-corpus-hk-au-jp-kr | 4 | 60 | yes |
| legal-corpus-cn | 1 | 16 | yes |
| legal-corpus-in | 1 | 12 | yes |
| legal-corpus-ae | 1 | 16 | yes |
| legal-corpus-sa | 1 | 12 | yes |
| legal-corpus-reviewed-candidates | 1,428 | 22,078 | yes |

Historical gates and exact-output parity are distinct checks. Existing gates preserve historical expectations, not independently measured accuracy. T3A metric implementations and T3B annotation tooling/data were unchanged.

## Verification

The environment uses frozen `uv.lock` dependencies. Python 3.12.16 additionally has the locked local OCR extras; the Python 3.11.18 core CI environment has the locked dev dependencies. Neither environment resides in the repository.

| Check | Command / method | Result |
|---|---|---|
| Focused AI/provider/profile/privacy and T1 integrity tests | `uv run --frozen pytest -q` with `test_ai_output_integrity`, `test_llm_coverage_audit`, `test_llm_defined_terms`, `test_review_profile_router`, `test_source_verification`, `test_structured_tokens_llm`, `test_tinyfish_and_remote_llm`, `test_openai_provider_optin`, `test_public_evidence_llm`, `test_finding_integrity` | 158 passed; 12 subtests passed |
| Complete suite, Python 3.12 | `uv run --frozen pytest -q` | 1,838 passed; 254 subtests passed; 2 skipped |
| Complete core CI suite, Python 3.11 | `uv run --frozen pytest -q -rs` | 1,826 passed; 254 subtests passed; 14 optional OCR/PDFium tests skipped |
| Nine historical gates | `uv run --frozen python scripts/evaluate_accuracy.py --external skip --output /tmp/junas-t4a-resumed/accuracy.json` | all nine passed; 1,722 documents |
| Exact strict replay | Separate baseline/current processes; full result comparison; socket connects refused | 1,722 documents / 27,034 findings identical |
| Conjunctive-label provenance | `uv run --frozen python scripts/check_mnpi_conjunctive_provenance.py` | passed |
| Fixture privacy scrub | `uv run --frozen python scripts/check_fixture_scrub.py` | passed; 6,381 files |
| Reviewed-lock freshness | `uv run --frozen python scripts/check_promoted_lock_freshness.py --base-ref 13e98d45 --head-ref HEAD` | passed; no promoted fixture input changes |
| Changed-file Ruff | `ruff check` and `ruff format --check` on all 16 T4A Python files | passed |
| Core mypy | `python -m mypy src/junas/models.py src/junas/pipeline.py src/junas/cli.py src/junas/configs/runtime.py` | passed; four core files |
| Build and strict CLI | `uv build --out-dir /tmp/junas-t4a-resumed/dist`; `uv run --frozen junas classify --text 'Contact alice@example.test'` | sdist/wheel built; CLI completed |
| Local OCR CI slice | `uv run --frozen pytest -q test/test_tesseract_ocr.py test/test_image_scan.py test/test_core_pipeline.py` | 36 passed; 2 skipped |
| Diff and preservation | `git diff --check 13e98d45`; unchanged-path checks against baseline | passed |

The two Python 3.12/local-OCR skips require macOS control fonts unavailable on Linux; other local Tesseract tests ran. The Python 3.11 environment mirrors core CI's dev-only install, so its 14 skips require optional `pypdfium2`/`pytesseract`; those paths were covered by the Python 3.12 OCR-enabled environment except for the two macOS-font controls. External dataset acquisition/evaluation and real model/provider tests were intentionally excluded from this task. Regression gates use the original locks; they were not regenerated. The full Python 3.12 run and the final focused run cover the same test string value after its formatting-only split.

An initial Ruff lint run failed on the overlong test string; the final scoped run passes after splitting it. A supplemental directory-wide formatting check also flagged the unchanged `src/junas/advisory/llm_adjudicator/__init__.py`; it was left outside this diff. CI checks changed Python files, which all pass. This report does not claim repository-wide formatting cleanliness.

The [machine-readable evidence](t4a_evidence.json) retains source/corpus/lock fingerprints, per-corpus gate summaries, exact parity counts, reproductions, environment versions and verification results. Detailed run logs, replay script and complete before/after results are under `/tmp/junas-t4a-resumed`; earlier reproduction evidence is under `/tmp/junas-t4a-pa9yyk8h`. These temporary files are diagnostic artifacts, not committed fixture or annotation data.

## Exact T4A files

The paused implementation changed these files (already committed before this resume):

- `src/junas/advisory/llm_adjudicator/contracts.py` (new validation/provenance contract)
- `src/junas/advisory/llm_adjudicator/helpers.py`
- `src/junas/advisory/llm_adjudicator/inference.py`
- `src/junas/advisory/llm_adjudicator/structured_query.py`
- `src/junas/advisory/local_ocr_llm.py`
- `src/junas/review/engine.py`
- `src/junas/review/llm_coverage_audit.py`
- `src/junas/review/llm_defined_terms.py`
- `training/distillation/student_provider.py` (runtime response validation only)
- `test/test_ai_output_integrity.py` (new mocked regressions)
- `test/test_llm_coverage_audit.py`
- `test/test_llm_defined_terms.py`
- `test/test_review_profile_router.py`
- `test/test_source_verification.py`
- `test/test_structured_tokens_llm.py`
- `test/test_tinyfish_and_remote_llm.py`

The resume additionally updated `docs/llm-governance.md`, split one overlong string in `test/test_ai_output_integrity.py` without changing its value, and added this report and `reports/current/t4a_evidence.json`. It did not edit `pipeline.py`, `configs/runtime.py`, `external/privacy_guard.py`, detector rules, metric tooling, annotation tooling, historical labels or locks.

## Compatibility and remaining research limits

The `ReviewResult` dataclass is unchanged, but **audit-grade output semantics intentionally change**: no `llm_raised_*` findings; no LLM-defined-term suppression; no AI replacement of scored risk; no document-wide retrieved-source promotion to verified status. The warning list can now contain defined-term proposals, distinguished by `source=llm_defined_terms`. Consumers must inspect advisory/source markers and must not interpret all warnings as detector evidence. Stricter validation can now reject malformed injected providers that previously returned a partial result. Structured entity references change to hashes. The internal defined-term cache format advances to v2.

Retrieval verification changes can affect audit-grade conjunctive findings, scores and classifications relative to the earlier assisted implementation; this is an explicit consequence of removing unsupported public-status claims. Existing deterministic no-provider audit behavior and all measured strict outputs are preserved. No new top-level result schema or verified-AI acceptance policy was invented.

Real-model usefulness, hallucination rate, confidence calibration, false positives/negatives, model drift, prompt-injection resilience and OCR/model interactions remain unmeasured. Stable provider/model/prompt configuration does not identify immutable weights, and local adapter-content attribution remains limited. There is still no independently reviewed protected holdout or established claim-level public-source verifier. Mocked checks provide integrity evidence only. T4A stops here; it does not authorize T4B, T5, remote inference or paid experiments.
