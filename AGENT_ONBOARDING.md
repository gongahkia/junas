# Agent Onboarding — Kaypoh

You are an independent coding agent picking up work on Kaypoh. **Read this file first**, then the architecture document it points at, before touching any code. Do not skim. Every section below is load-bearing.

Date this onboarding was last revised: **2026-06-05**.

---

## 1. What Kaypoh is in one paragraph

Kaypoh is a pre-send document safety layer for legal-corporate workflows where client/issuer confidentiality is a procurement blocker for GenAI adoption. It detects PII and MNPI evidence in documents before they're pasted into ChatGPT / Claude / Gemini, anonymises sensitive spans reversibly, and produces an HMAC-sealed reviewer-attributed audit trail. It is **not** a horizontal DLP replacement (Purview / Netskope / Nightfall already compete on detector breadth). The wedge is SG/SEA-native local-ID + legal-MNPI detection, reversible local anonymisation, and an offline-default desktop SKU.

---

## 2. The document you must read before coding

Read this end-to-end:

1. **`ARCHITECTURE-PIVOT-24-MAY.md`** — the authoritative product / architecture / roadmap doc. Items 1–89 + M1–M6 + items 90–91. Items in `~~strikethrough~~` are shipped; un-struck items are open. The `## First-Principles Statutory Analysis` section is the ground truth for what's defensible per jurisdiction.

Older `ARCHITECTURE_*.txt` docs are historical only. Runtime flow now lives in `ARCHITECTURE-PIVOT-24-MAY.md` § Target Runtime and the code path in §7 below.

---

## 3. The state of the codebase as of 2026-06-05

**Current state after the 2026-05-26 pivot cleanup:**

- Legacy 9-layer classifier (`src/kaypoh/workflow/layer1_lexicon` through `layer6_regression` + `layer5_mosaic`) **deleted from the repo**. `/classify` is now a thin wrapper over `engine.review()` returning a flat findings shape. See item 63.
- 13 new expansion items (54-68) covering: LLM symmetric findings, matter-scoped inheritance, latency SLO, reviewer identity binding, local-daemon ACL, subject-erasure (PDPA s16 / GDPR Art 17 / etc.), per-tenant citations, container coverage, image scanning (Tesseract / OpenAI Vision / Google / AWS / Azure), fail-closed everywhere, additive signals (classifier + similarity + transparent aggregator). Subject erasure (item 59), reviewer identity binding (item 57), latency SLO (item 56), and the runtime fail-closed audit (item 65) shipped on 2026-05-28.
- Item 37 shipped on 2026-06-01: audit-grade LLM defined-term extraction and inverse coverage audit are now named runtime components with config keys, readiness/diagnostics visibility, and privacy-ledger events.
- 2026-06-01 recall-gate cleanup fixed a real `email_address` regression caused by the split-email guard swallowing valid emails after company-name lines, and normalized phone spans so `PHONE_RE` no longer absorbs following newline/list numbering. Default and adversarial recall gates pass without lock updates.
- 2026-06-01 item 124/126 substrate shipped: `scripts/run_layer_attribution_eval.py` orchestrates `scripts/evaluate_candidate_corpus.py --profile strict|audit_grade`, `scripts/bucket_candidate_misses.py`, and `scripts/miss_concentration.py` to produce heuristic ideal-miss buckets and detector-family × jurisdiction concentration reports. `audit_grade` requires `--allow-external-cost`. Initial strict Stage A run: 6,122 ideal misses; coverage_gap 4,430, conjunction_miss 1,513, singling_out_miss 142, true_inference_miss 9, needs_review 28. These buckets are prioritisation substrate and require spot-check before being treated as reviewed truth.
- 13 more items (69–86) derived from first-principles statutory analysis of every in-scope jurisdiction. Items 78, 80, 84, 90, and 91 are implemented; procurement-substrate items 87–89 remain open.
- Items 90 and 91 are implemented: HK/AU/JP/KR packs + seed fixtures are in place, and the default/adversarial recall locks were refreshed after the autolabel sweep. Items 78 and 80 shipped 2026-05-28 with new default/adversarial corpus fixtures and refreshed recall locks.
- Candidate Stage A is complete and Stage B-ready for all 17 in-scope jurisdiction packs under `test/fixtures/legal-corpus-candidates/` as of 2026-06-01. The reviewed global candidate report `/tmp/kaypoh-candidates-after-eu-reviewed.json` covered 357 docs / 4,295 strict labels at strict recall 1.0 and strict precision 1.0 with zero misses, zero unexpected findings, and zero must-not violations. On 2026-06-01, the project owner stated they manually reviewed all jurisdiction generated tests and approved them as ready for Stage B corpus expansion; this is tracked in `_stage_readiness` and gated by `scripts/check_candidate_review_status.py --require-stage-b-ready`. SG, HK, AU, MY, ID, TH, PH, VN, JP, KR, IN, CN, and AE have completed owner-approved Stage B first passes for internal benchmarking and pass `scripts/check_candidate_stage_gate.py --target-stage stage_b --require-promotion-ready` with strict recall/precision 1.0. SA and US have completed clean Stage B first passes (`84 docs` each, strict recall/precision 1.0, zero misses/unexpected/must-not), but are `evaluated_pending_owner_review` because each has 63 expanded labels awaiting project-owner approval. The current post-SA/US global candidate report `/tmp/kaypoh-sa-us-stage-b-eval-final.json` covers 1,302 docs / 16,022 strict labels / global ideal recall 0.4223 at strict recall/precision 1.0, with zero misses, zero unexpected findings, zero must-not violations, 1,176 approved labels, and 126 pending labels. Current per-jurisdiction status is generated in `docs/candidate_corpus_status.md`; none of these Stage B candidate sets has been promoted into locked recall baselines or reviewed as procurement-grade legal advice.
- Runtime setup is UV-first. Use `uv run ...` with the project lock; do not revive `requirements.txt` workflows.
- Docker support exists for the deterministic API server via `Dockerfile` and `docker-compose.yml`.

**Tests:**

- Focused detector / corpus / runtime suites should run through `uv run python -m unittest ...`.
- Use `scripts/verify_runtime.sh` for the current deterministic API smoke path.
- The old skipped modules for the classifier/mosaic/Redis/artifact stack have been removed instead of kept as skips.

**Repo state:**

```
src/kaypoh/
├── anonymize/         # placeholder rewriting + mapping store
├── backend/           # FastAPI app: main.py, schemas.py, auth.py, ...
├── client.py          # Python SDK
├── configs/           # runtime config
├── helper/            # determinism
├── review/            # engine.py + jurisdictions/ + detectors
└── workflow/
    ├── layer0_parser
    ├── layer7_public_evidence   # Exa / Tinyfish / Serper / SerpAPI retrieval
    ├── layer8_llm_adjudicator   # LLM tier (vLLM / Ollama / OpenAI)
    └── privacy_guard.py
```

Note the absence of `layer1` through `layer6` — those are deleted, on purpose.

---

## 4. Standing principles (do not violate without explicit user sign-off)

These are project-wide invariants. Every PR is measured against them.

1. **The deterministic engine is the source of truth.** LLM tier is advisory. Enforcement is structural, not procedural: any finding the LLM emits or modifies is severity-clamped against `SEVERITY_SCORE` such that `origin=llm` findings cannot exceed deterministic-medium and cannot displace or suppress an existing deterministic-high finding (the engine continues to cap any LLM-driven overall-risk label change at `max(pii_score, mnpi_score) < 85.0`). Under that cap the LLM operates as a **capped recall-raiser** (item 54, repositioned) — it may raise findings the deterministic engine missed and downgrade findings the deterministic engine flagged, with both directions reviewer-adjudicated and journaled. The prior asymmetry rule ("LLM can downgrade medium → low *only* when public evidence supports it; cannot raise findings") is retired — it constrained the LLM to refining already-detected substrate and made the LLM tier incapable of raising recall. The structural cap preserves the no-suppression-of-deterministic-high invariant without imposing the downgrade-only constraint. The same cap binds the planned classifier (item 66), similarity (item 67), and aggregator (item 68). A change that weakens the cap needs explicit user approval.

2. **Per-tenant opt-in is the default for every external-call feature.** Every new cloud / ML / external retrieval surface inherits the per-tenant opt-in pattern (`KAYPOH_LLM_TENANT_OPT_IN_OPENAI` style). Deployer-only env-var gates are insufficient. Tenant context resolves via the item 42 plumbing (JWT subject or API-key principal).

3. **Fail-closed everywhere (item 65).** PDF ingest, detector failures, LLM-tier failures, public-evidence retrieval failures, mapping-store failures, image-scan failures, subject-erasure failures, citation-override resolution failures — all surface as explicit `degraded_modes` on the response, never silent partial coverage.

4. **Every detector is statute-anchored.** New PII or MNPI detectors require a statute / regulator-guidance citation per applicable jurisdiction. Format follows existing detectors (e.g. `"S1234567D" detected → PDPA s13 and PDPC NRIC Advisory ...`). The `## First-Principles Statutory Analysis` section in the architecture doc is the lookup table.

5. **Recall + precision locks gate everything.** No new detector ships without seed fixtures + a recall.lock baseline. No training artefact promotes without beating the locked baseline. `scripts/recall_gate.py --update --reason "..."` writes attribution to `recall.lock.history.jsonl`.

6. **Privacy-sensitive paths go through PrivacyGuard.** LLM calls, public-evidence retrieval, image-scan cloud providers — all of them. A new external call without a `PrivacyGuard.check_external_query` gate is a bug.

7. **Synthetic corpus discipline.** Build-time LLM use (OpenAI for fixture generation) is unrestricted — synthetic inputs only, no customer data. Runtime LLM use is privacy-gated. Don't confuse the two.

8. **Don't refactor outside the immediate scope of the task.** Maintenance refactors (M1–M6) are scheduled — sequence is in the doc. Mixing a maintenance refactor into a feature PR makes review impossible.

9. **CLAUDE.md rules apply.** Minimal whitespace, in-line lowercase comments only, no unsolicited markdown docs, `[Inference]` labels on probabilistic claims.

---

## 5. What to work on next (in order)

Pick the next highest-leverage open item by ICP impact:

- **Item 40 Stage B corpus expansion** — SG, HK, AU, MY, ID, TH, PH, VN, JP, KR, IN, CN, and AE Stage B are owner-approved for internal benchmarking and promotion-ready as candidate sets. SA and US are Stage-B-clean but pending project-owner approval for 63 expanded labels each. UK and EU remain Stage B-ready and unexpanded. Either mark SA/US owner-approved after project-owner review or run UK/EU Stage B before making broader coverage claims.
- **Item 124 spot-check + item 125 audit-grade experiment** — the bucketing/concentration scripts now exist. Spot-check a 50-miss sample across SG/HK/EU/IN or similar, then run the `--profile audit_grade` candidate eval only with explicit API-cost approval and configured LLM/retrieval components.
- **Item 82** (HK "not generally known" public-evidence semantics) — closes a jurisdiction-specific MNPI defensibility gap.
- **Items 87 / 89** (defensibility report + evidence pack export) — turns the statute coverage work into procurement-facing artefacts.
- **Item 33 remainder** (EU member-state IDs + broader cookie/ad-ID/device serials + semantic DOB/age) — DOB/adult-age, IP/MAC/IMEI, US ITIN/DLN mini-slice shipped 2026-05-28.
- **Items 34 / 35 / 79** (addresses, semantic PII, inferred attributes) — broader PII recall once the deterministic slices are stable.
- **Item 48 fixture growth / item 86 follow-up** — SG wedge and jurisdiction packs are stronger now, but still need deeper adversarial/real-world fixture growth.

Always check the architecture doc for the latest user prioritisation before picking. If unsure, ask the user.

---

## 6. Things you must not do without explicit user sign-off

- **Revive any of the deleted legacy layers.** Items 66/67/68 are *new code* implementing the *conceptual heirs* of layer4 / layer2-3 / layer5. Do not copy the deleted layer1-6 source as a starting point.
- **Push to remote.** Commit locally; the user pushes. No `git push` without explicit instruction.
- **Modify `recall.lock.json` without `--reason`.** Item 16 requires attribution.
- **Add new top-level deps to `kaypoh-local` extras.** Item 26 contract is enforced by `test/test_local_sku_runtime.py`. Heavy deps go in `[server]` / `[ocr]` / `[ml]` extras.
- **Skip the spot-check on auto-labeled fixtures** before promoting them to a recall baseline. See item 91 caveat.
- **Describe reviewed candidate labels as procurement-grade legal review.** Project-owner/Codex approval is enough for internal benchmarking only.
- **Mix maintenance refactors (M1–M6) into feature PRs.** Schedule them separately per the doc.
- **Add unsolicited markdown docs.** CLAUDE.md rule. Architecture additions go *in* `ARCHITECTURE-PIVOT-24-MAY.md`, not in new files.
- **Confuse build-time and runtime LLM use.** Build-time = synthetic data only, unrestricted. Runtime = privacy-gated, tenant opt-in, ledger-logged.

---

## 7. Where to find things

| You want to... | Look here |
|---|---|
| Understand the product wedge + ICP | `ARCHITECTURE-PIVOT-24-MAY.md` § Positioning and ICP |
| Find what's shipped vs planned | `ARCHITECTURE-PIVOT-24-MAY.md` § Expansion Sequence (strikethrough = shipped) |
| Understand the runtime flow | `ARCHITECTURE-PIVOT-24-MAY.md` § Target Runtime; then `src/kaypoh/backend/main.py::_run_review_sync` → `src/kaypoh/review/engine.py::PreSendReviewEngine.review` |
| Find the statute behind a detector | `ARCHITECTURE-PIVOT-24-MAY.md` § First-Principles Statutory Analysis |
| Add a new jurisdiction pack | `src/kaypoh/review/jurisdictions_data/*.toml` (item 19 schema) |
| Add a new detector | `src/kaypoh/review/engine.py` — `_pii_findings` / `_mnpi_findings`; future: `src/kaypoh/review/detectors/` after the M1 refactor |
| Add a new fixture | `scripts/generate_legal_fixture[_batch].py`, then `scripts/autolabel_batch.py`, then hand-spot-check |
| Run tests | `PYTHONPATH=src python3 -m pytest -q --no-header` |
| Run the recall gate | `python3 scripts/recall_gate.py --corpus test/fixtures/legal-corpus` |
| Find the OpenAI key | `.env` at repo root (`OPENAI_API_KEY=...`) — `set -a && . ./.env && set +a` before invoking |
| Trace `/review` flow | `src/kaypoh/backend/main.py::_run_review_sync` → `src/kaypoh/review/engine.py::PreSendReviewEngine.review` |
| Trace `/classify` flow | `src/kaypoh/backend/main.py::_classify_core` (now a thin wrapper) |

---

## 8. Hand-off checklist for your own work

Before reporting any task complete:

- [ ] All tests pass except the 8 explicit skips and the pre-existing env-issue failures listed in §3.
- [ ] No new dead code (orphan helpers, unused imports). Item M6 cadence applies to your own work too.
- [ ] Detector additions have seed fixtures + recall lock + statute citation.
- [ ] External-call additions have `PrivacyGuard` gate + per-tenant opt-in + privacy-ledger entry.
- [ ] Changes that affect the wire contract (`ReviewResponse`, `ClassifyResponse`, etc.) update both the schema AND the corresponding tests.
- [ ] Commits are small, scoped, and follow the existing commit-message style (look at `git log` for examples).
- [ ] Architecture doc updated if you're shipping an item — strike through with `~~...~~` and add the shipped-date + module pointers, mirroring how items 1–53 are marked.

If the user asks you to commit, follow the CLAUDE.md commit rules: heredoc message, `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`, never push without explicit instruction.

---

## 9. When to ask the user vs proceed

**Proceed without asking when:**

- The task is in items 40 / 57 / 59 / 60 and acceptance criteria are clear in the architecture doc.
- A planned item has clear acceptance criteria in the architecture doc.
- A pre-existing test was failing before you started — leave it alone.
- A fixture / lock / detector follows the established pattern.

**Ask the user when:**

- Two items in the architecture doc could plausibly be done next (priority ambiguous).
- A change would violate any of the §4 standing principles.
- A statute citation is unclear or recently updated (per item 53 — check the regulator source first, then escalate).
- The cost / blast radius is high (training run, deletion of additional code, external service spend > $20).

---

Welcome to Kaypoh. Read the onboarding and architecture docs. Stage A candidate coverage is complete; SG, HK, AU, MY, ID, TH, PH, VN, JP, KR, IN, CN, and AE Stage B are owner-approved for internal benchmarking; SA/US Stage B are clean but pending owner approval; UK/EU remain Stage B-ready. Next work should be chosen from item 40 Stage B expansion/approval, item 82, items 87/89, item 33 remainder, or M3 depending on user priority.
