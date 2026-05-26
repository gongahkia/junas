# Agent Onboarding — Kaypoh

You are an independent coding agent picking up work on Kaypoh. **Read this file first**, then the two documents it points at, before touching any code. Do not skim. Every section below is load-bearing.

Date this onboarding was written: **2026-05-26**.

---

## 1. What Kaypoh is in one paragraph

Kaypoh is a pre-send document safety layer for legal-corporate workflows where client/issuer confidentiality is a procurement blocker for GenAI adoption. It detects PII and MNPI evidence in documents before they're pasted into ChatGPT / Claude / Gemini, anonymises sensitive spans reversibly, and produces an HMAC-sealed reviewer-attributed audit trail. It is **not** a horizontal DLP replacement (Purview / Netskope / Nightfall already compete on detector breadth). The wedge is SG/SEA-native local-ID + legal-MNPI detection, reversible local anonymisation, and an offline-default desktop SKU.

---

## 2. The two documents you must read before coding

In this order, end-to-end:

1. **`ARCHITECTURE-PIVOT-24-MAY.md`** — the authoritative product / architecture / roadmap doc. Items 1–89 + M1–M6 + items 90–91. Items in `~~strikethrough~~` are shipped; un-struck items are open. The `## First-Principles Statutory Analysis` section is the ground truth for what's defensible per jurisdiction.

2. **`ARCHITECTURE_26_MAY.txt`** — ASCII diagram of the current + planned runtime flow. Shows what's shipped vs planned, where each new feature slots in, and what changed in the 2026-05-26 surgery.

Older docs (`ARCHITECTURE_25_MAY.txt` does not exist — it was renamed) are historical only.

---

## 3. The state of the codebase as of 2026-05-26

**Just landed (commits `fdf448d` + `3361512`):**

- Legacy 9-layer classifier (`src/kaypoh/workflow/layer1_lexicon` through `layer6_regression` + `layer5_mosaic`) **deleted from the repo**. `/classify` is now a thin wrapper over `engine.review()` returning a flat findings shape. See item 63.
- 13 new expansion items (54–68) covering: LLM symmetric findings, matter-scoped inheritance, latency SLO, reviewer identity binding, local-daemon ACL, subject-erasure (PDPA s16 / GDPR Art 17 / etc.), per-tenant citations, container coverage, image scanning (Tesseract / OpenAI Vision / Google / AWS / Azure), fail-closed everywhere, additive signals (classifier + similarity + transparent aggregator).
- 13 more items (69–86) derived from first-principles statutory analysis of every in-scope jurisdiction. Plus procurement-substrate items 87–89.
- Two explicit next-todos: items 90 (HK/AU/JP/KR fixture seeding) and 91 (autolabel sweep on the 233-fixture synthetic corpus).

**Tests:**

- `268 passing` on core review / anonymize / tenant / source-verification surfaces.
- `8 modules skipped` pending rewrite for the new `/classify` thin-wrapper shape. They are explicitly marked with `pytest.skip(allow_module_level=True, ...)` and a clear reason. They are: `test_classify_contract`, `test_window_inference_payloads`, `test_redis_integration`, `test_preflight_validation`, `test_logging`, `test_observability`, `test_startup_paths`, `test_distillation_pipeline`.
- Pre-existing env-issue failures unrelated to the surgery: `test_anonymize::test_anonymize_accepts_docx_base64_document` (xml.etree expat missing on Python 3.14), `test_document_hardening` (same expat issue), `test_benchmark_*` (latency targets), `test_accuracy_doc::test_accuracy_doc_matches_locks` (stale — needs regeneration after corpus growth). These are not your problem unless explicitly asked.

**Repo state:**

```
src/kaypoh/
├── anonymize/         # placeholder rewriting + mapping store
├── backend/           # FastAPI app: main.py, schemas.py, auth.py, ...
├── client.py          # Python SDK
├── configs/           # runtime + artifacts config
├── helper/            # determinism
├── review/            # engine.py + jurisdictions/ + detectors
├── training/          # distillation pipeline (item 29)
└── workflow/
    ├── layer0_parser
    ├── layer7_public_evidence   # Tinyfish / Exa retrieval
    ├── layer8_llm_adjudicator   # LLM tier (vLLM / Ollama / OpenAI)
    └── privacy_guard.py
```

Note the absence of `layer1` through `layer6` — those are deleted, on purpose.

---

## 4. Standing principles (do not violate without explicit user sign-off)

These are project-wide invariants. Every PR is measured against them.

1. **The deterministic engine is the source of truth.** LLM tier is advisory. LLM can downgrade medium → low *only* when public evidence supports it; cannot suppress a deterministic-high. The same invariant binds the planned classifier (item 66), similarity (item 67), and aggregator (item 68). A change that violates this needs explicit user approval.

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

The user has explicitly flagged two items as immediate next-todos in the architecture doc. **Do these first** unless the user has redirected you to something else:

### Item 91 — Run the autolabel pipeline against the 233-fixture corpus

**State of the world:** 233 synthetic fixtures (118 default + 115 adversarial) exist under `test/fixtures/legal-corpus/` and `test/fixtures/legal-corpus-adversarial/`. Each has a stub `labels.json` from `scripts/generate_legal_fixture.py` carrying `_generation_note: "AUTO-GENERATED STUB"`. The recall gate cannot use them until `must_detect` / `must_not_detect` are filled.

**Tools already built (do not re-implement):**

- `scripts/autolabel_fixture.py` — single-fixture auto-labeler. Default model `o1`. Validates that every `matched_text` appears verbatim in the body, drops hallucinations, writes provenance fields `_label_source`, `_label_model`, `_label_warnings`, `_label_note`. Protects existing human labels (only re-labels stubs or other auto-labels unless `--force`).
- `scripts/autolabel_batch.py` — walks both corpora, calls `autolabel_fixture.autolabel()` per file.

**Execution order:**

1. **Validation run** — auto-label 5 fixtures first to confirm o1 works through the API path: `OPENAI_API_KEY=$(grep OPENAI_API_KEY .env | cut -d= -f2) scripts/autolabel_batch.py --model o1 --limit 5`. Spot-check the output by hand. [Inference] Each fixture should produce ~5–15 `must_detect` entries + ~2–5 `must_not_detect` entries. Hallucinated text (not in body) gets filtered with a warning surfaced in `_label_warnings`.

2. **Full sweep** — once spot-check passes: `OPENAI_API_KEY=... scripts/autolabel_batch.py --model o1`. [Inference] ~$12 at o1 prices for 233 fixtures, ~30 min wall clock.

3. **Spot-check ≥10% of auto-labels** before promoting any baseline. Pick ~25 random fixtures, eyeball the labels, fix any systematic miss the validator didn't catch.

4. **Refresh recall lock** with provenance: `python3 scripts/recall_gate.py --update --reason "auto-label sweep with o1 on 2026-05-26 (item 91); manual spot-check of 25 fixtures completed"`. The history file `test/fixtures/legal-corpus/recall.lock.history.jsonl` records actor + commit SHA + reason per item 16.

**Caveat the user must understand before you do step 4:** auto-labeled fixtures + auto-derived recall lock = circular gate. The recall gate measures the engine against labels the engine's teacher generated. Promotion is only safe after the spot-check. Surface this in the lock-update reason explicitly so an auditor can reconstruct the provenance.

### Item 90 — HK / AU / JP / KR fixture seeding

**Depends on:** item 86 (curated jurisdiction packs for HK / AU / JP / KR — TOML detector + statute citations under `src/kaypoh/review/jurisdictions_data/`).

**Execution order:**

1. **Land detectors first.** Each pack needs at minimum: local national-ID regex, local company-ID regex, statute-citation strings. Detector patterns:
    - HK: HK ID `^[A-Z]{1,2}[0-9]{6}\(?[0-9A]\)?$`; CR No. `^[0-9]{7,9}$` (with context anchor)
    - AU: TFN `^[0-9]{9}$` (algorithm-validated); ABN `^[0-9]{11}$`; ACN `^[0-9]{9}$`
    - JP: MyNumber `^[0-9]{12}$` (algorithm-validated); corporate number `^[0-9]{13}$`
    - KR: RRN `^[0-9]{6}-[0-9]{7}$` (strictly regulated under PIPA Art 24-2 — needs explicit handling docs); business registration number `^[0-9]{3}-[0-9]{2}-[0-9]{5}$`
    - **Validate digit-algorithm correctness for TFN / MyNumber.** Pure-regex without checksum will false-positive on serial numbers.
2. **Seed fixtures.** One fixture per jurisdiction hand-validated by you (engine should fire detectors against it). Place under `test/fixtures/legal-corpus-hk-au-jp-kr/{hk,au,jp,kr}/`.
3. **Grow corpus.** Run `scripts/generate_legal_fixture_batch.py` with jurisdiction-scoped prompts (you'll need to extend the script to take `--jurisdiction` — currently SG-hardcoded in the prompt). 30 docs per jurisdiction.
4. **Auto-label** via item 91's tools.
5. **Seed lock baseline.** `legal-corpus-hk-au-jp-kr.lock.json` with `baseline_recall = 1.0` + `baseline_precision = 1.0` for each new detector.
6. **Statute citations.** Per item 85: SG findings cite SFA s218-221; HK findings cite SFO Part XIV s270-281; AU findings cite Corporations Act s1042A-1043O; JP findings cite FIEA Art 166-167; KR findings cite FSCMA Art 174-179. The first-principles section has the full citation table.

### After 90 + 91

Pick the next highest-leverage open item by ICP impact:

- **Item 78** (pseudonymised IDs) — high recall lift on PII without new training data.
- **Item 80** (contingent MNPI language) — closes the textbook MNPI recall hole the first-principles analysis surfaced.
- **Item 84** (calendrical reasoning for quiet periods) — high signal for IR / corporate-secretarial ICP segment.
- **Item 59** (subject erasure) — procurement blocker for PDPA / GDPR pilots.
- **Item 60** (per-tenant citations) — explicit ASAP per architecture doc.
- **Item 57** (reviewer identity binding) — security hole per the doc.

Always check the architecture doc for the latest user prioritisation before picking. If unsure, ask the user.

---

## 6. Things you must not do without explicit user sign-off

- **Revive any of the deleted legacy layers.** Items 66/67/68 are *new code* implementing the *conceptual heirs* of layer4 / layer2-3 / layer5. Do not copy the deleted layer1-6 source as a starting point.
- **Push to remote.** Commit locally; the user pushes. No `git push` without explicit instruction.
- **Modify `recall.lock.json` without `--reason`.** Item 16 requires attribution.
- **Add new top-level deps to `kaypoh-local` extras.** Item 26 contract is enforced by `test/test_local_sku_runtime.py`. Heavy deps go in `[server]` / `[ocr]` / `[ml]` extras.
- **Skip the spot-check on auto-labeled fixtures** before promoting them to a recall baseline. See item 91 caveat.
- **Mix maintenance refactors (M1–M6) into feature PRs.** Schedule them separately per the doc.
- **Add unsolicited markdown docs.** CLAUDE.md rule. Architecture additions go *in* `ARCHITECTURE-PIVOT-24-MAY.md`, not in new files.
- **Confuse build-time and runtime LLM use.** Build-time = synthetic data only, unrestricted. Runtime = privacy-gated, tenant opt-in, ledger-logged.

---

## 7. Where to find things

| You want to... | Look here |
|---|---|
| Understand the product wedge + ICP | `ARCHITECTURE-PIVOT-24-MAY.md` § Positioning and ICP |
| Find what's shipped vs planned | `ARCHITECTURE-PIVOT-24-MAY.md` § Expansion Sequence (strikethrough = shipped) |
| Understand the runtime flow | `ARCHITECTURE_26_MAY.txt` |
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

- The task is in items 90 / 91 / 57 / 59 / 60 (explicit ASAP per doc).
- A planned item has clear acceptance criteria in the architecture doc.
- A pre-existing test was failing before you started — leave it alone.
- A fixture / lock / detector follows the established pattern.

**Ask the user when:**

- Two items in the architecture doc could plausibly be done next (priority ambiguous).
- A change would violate any of the §4 standing principles.
- A statute citation is unclear or recently updated (per item 53 — check the regulator source first, then escalate).
- The cost / blast radius is high (training run, deletion of additional code, external service spend > $20).

---

Welcome to Kaypoh. Read the two architecture docs. Then work on item 91, then item 90, then check back with the user.
