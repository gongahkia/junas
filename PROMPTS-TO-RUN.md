# PROMPTS-TO-RUN

Each fenced code block is a self-contained prompt you can copy verbatim
into a fresh Claude Code session that has been spawned inside this
repository. Every prompt assumes the agent has access to
`AGENT-RUNBOOK.md` and `GAPS-TO-REMEDY.md` — agents will read those
first as part of their work.

## How to use this doc

1. Pick a tier (top to bottom). Items within a tier can run in parallel
   unless an explicit dependency note says otherwise.
2. For each prompt, open a new Claude Code session inside this repo
   (or spawn an agent with `isolation: "worktree"`). Paste the prompt
   verbatim.
3. Run parallel agents in **separate worktrees** to avoid file-write
   conflicts. The runbook §7 documents the worktree convention.
4. Once the agent reports done, review the branch + tests + commit
   message, then merge to `main` yourself (the user is the merge
   authority; agents do not push to `origin/main`).

## Posture (2026-06-05 rewrite)

This file was re-tiered methodology-first on 2026-06-05. The previous
ordering chased launch numbers; the new ordering closes vendor-grade
defensibility gaps first. The thesis is **"use us for your evals"** —
SG legal-tech vendors and LLM teams running SG-LegalBench against
their own models. That positioning is contingent on the methodology
surviving scrutiny.

Every gap-closure prompt references its GAP ID in `GAPS-TO-REMEDY.md`.
Read that file alongside this one.

## Critical context (read before firing anything)

1. **Methodology fundamentals (Tier 1) precede every public claim.**
   No baseline, leaderboard, or launch asset is shippable until Tier 1
   lands. Specific blockers tracked in `GAPS-TO-REMEDY.md` as
   BLOCKER/HIGH severity.
2. **SGLB-05/06/07 are removed from the v0.1 leaderboard** until data
   lands (closed by `NEW-HONEST-LEADERBOARD`). The previous "8 tasks
   shipped" claim is replaced with "4 eligible tasks (SGLB-01, -02,
   -04, -08); 3 code-shipped awaiting data; 1 TOS-gated".
3. **SGLB-08 v0.1 status is conditional on `SOLO-17` κ result.** If
   any pairwise κ < 0.4, the task is reframed as
   "Inter-Judge-Alignment" sub-track for v0.1 (`NEW-08-REFRAME-IF-LOW-KAPPA`).
4. **Launch story is reframed.** Not "frontier models fail SG legal
   reasoning" (which requires verified baselines we don't yet have).
   Instead: "first SG legal benchmark with vendor-grade methodology —
   contamination analysis, bootstrap CIs, published dispute process".
5. **Anthropic + Gemini baseline gap.** Commits `414bb4b` + `9beb086`
   claim baselines that don't appear in `runs/baselines/`. Audited and
   either recovered or rerun via `NEW-VERIFY-BASELINES` + `NEW-BATCH-D`.
6. **License + name decision** (`SOLO-10`) is promoted to Tier 1.
   Affects PR acceptance policy + vendor adoption.
7. **Reference copilot demoted to Tier 5.** Not load-bearing for the
   benchmark thesis. The copilot demonstrates the benchmark; it does
   not headline.

---

## Fire order

| Tier | Why | Items |
|---|---|---|
| **Tier 1 — Methodology fundamentals** | Defensibility floor; gates every public number | `SOLO-17`, `SOLO-18`, `SOLO-10`, `SOLO-9`, `NEW-CI-RECEIPT`, `NEW-CONTAM`, `NEW-SAL-VALIDATION`, `NEW-EXTRACT-VERSION`, `NEW-HONEST-LEADERBOARD`, `NEW-NORM-SPEC`, `NEW-DISPUTE-PROCESS`, `NEW-VERIFY-BASELINES`, `NEW-BATCH-D`, `NEW-08-REFRAME-IF-LOW-KAPPA` (conditional) |
| **Tier 2 — Data hardening** | Closes empty tasks + scales N | Batch A, Batch B, `NEW-SSO-EXPAND`, `NEW-SGLB-04-PROD` |
| **Tier 3 — Vendor-facing infra** | Closes "use us for your evals" workflow | `NEW-VENDOR-GUIDE`, `NEW-LIB-PACKAGING`, `NEW-INDEPENDENT-REPRO`, Batch C, `SOLO-1`, `SOLO-2`, `SOLO-3`, `SOLO-4`, `SOLO-5`, `SOLO-6` |
| **Tier 4 — Launch** | arXiv + launch assets | `SOLO-8`, Batch E |
| **Tier 5 — Copilot + v0.2** | Post-launch | Batch G, Batch H, Batch F, `SOLO-7`, `SOLO-11`, `SOLO-12`, COPILOT-1..4 |

## Hard dependencies (do not violate)

- `NEW-VERIFY-BASELINES` before `NEW-BATCH-D` (audit informs which cells need rerun).
- `NEW-CI-RECEIPT` before `NEW-BATCH-D` (receipts must emit CIs).
- `NEW-CONTAM` before `NEW-BATCH-D` (receipts must record memorisation flags).
- `NEW-EXTRACT-VERSION` before `NEW-BATCH-D` (receipts must include dataset extraction-rule SHA).
- `SOLO-17` before `NEW-BATCH-D` (SGLB-08 needs κ-aware labels).
- `SOLO-17` before `NEW-08-REFRAME-IF-LOW-KAPPA` (decision is gated on κ values).
- `NEW-SAL-VALIDATION` before `NEW-SGLB-04-PROD` (production set assumes validated grammar).
- `NEW-HONEST-LEADERBOARD` before any leaderboard surface is exposed.
- `SOLO-9` before Tier 5 Batch G G3 (SGLB-14 needs Guidelines).
- Batch A A1 → A2 → A3; Batch A A1 → A4.
- Batch B B1 → B2 → B3; Batch B B1 → B4.
- Batch A before SGLB-05 baseline runs (data dependency).
- Batch B before SGLB-07 baseline runs (data dependency).
- `NEW-SSO-EXPAND` before SGLB-06 baseline runs.
- `NEW-CI-RECEIPT` + `NEW-CONTAM` + `NEW-NORM-SPEC` + `NEW-DISPUTE-PROCESS` before `NEW-VENDOR-GUIDE` (consolidating doc).

## Cost gates (read AGENT-RUNBOOK §8)

- `NEW-BATCH-D`: Azure gpt-5 reasoning-token billing 5-10x estimator quote. **Explicit user approval before firing each Azure cell.** Anthropic + Gemini + Ollama cells are cost-safe (~$0.005-$2/cell).
- `NEW-CONTAM` against Azure baselines: doubles LLM calls → could add $10-20 per task. Cost-safe against Anthropic / Gemini / Ollama.
- Batch H H2/H3 (Tier 5): same Azure gpt-5 cost class as `NEW-BATCH-D`.
- All Tier 1 doc-only prompts (`NEW-NORM-SPEC`, `NEW-DISPUTE-PROCESS`, `NEW-VERIFY-BASELINES`, `NEW-08-REFRAME-IF-LOW-KAPPA`) are zero-cost.

## Suggested fire sequence (paste-friendly)

Strict top-down also works — but leaves parallelism on the table. Below is the dependency-aware sequence that minimises wall-time while respecting every hard-dependency AND file-conflict identified by manual cross-check of the prompt bodies.

### Honest framing

- Tier 1 has **14 items** total: 12 "wave-eligible" + 1 gated coordinator (`NEW-BATCH-D`) + 1 conditional (`NEW-08-REFRAME-IF-LOW-KAPPA`).
- Within those 12 there are **4 real file-conflict pairs**. They are NOT all parallel-safe. The rounds below sequence them.
- "Parallel" means "fire in separate worktrees in the same wall-clock window"; not "race conditions on disk". Use `isolation: "worktree"` per agent.

### Tier 1 — Round 1 (6 in parallel, all disjoint files, all zero-cost)

Fire these together. Each agent in its own worktree. No file overlap; no API key dependency.

1. `SOLO-10` — name + license decision brief (zero cost; needs YOU at end)
2. `SOLO-9` — PDPC Advisory Guidelines scraper (network only)
3. `NEW-SAL-VALIDATION` — validate grammar against SAL Style Guide PDFs
4. `NEW-NORM-SPEC` — normalisation spec doc
5. `NEW-DISPUTE-PROCESS` — dispute/errata process docs
6. `NEW-VERIFY-BASELINES` — audit Anthropic/Gemini baseline gap

### Decision point (after Round 1)

- `SOLO-10` returns a 1-page brief — YOU pick name + licence. Gates `NEW-LIB-PACKAGING` (Tier 3).
- `NEW-VERIFY-BASELINES` returns `runs/baselines/PROVENANCE.md` telling you which Anthropic+Gemini cells need rerun under `NEW-BATCH-D`.

### Tier 1 — Round 2 (4 in parallel; mind the conflict pairs)

Fire after Round 1 lands. Two file-conflict pairs inside this round — sequence the loser to rebase after the winner lands.

7. `SOLO-17` — multi-judge κ for SGLB-08 (~$2.40; needs `ANTHROPIC_API_KEY` + `GEMINI_API_KEY`)
8. `SOLO-18` — 40-case human holdout for SGLB-08 (zero cost; needs YOU at end)
   - **Conflict with #7:** both touch `docs/sglb_specs/SGLB-08.md` (different sections of the Provisional-approval block). Land `SOLO-17` first; rebase `SOLO-18` if it landed earlier.
9. `NEW-CI-RECEIPT` — bootstrap CIs in receipt JSON
10. `NEW-HONEST-LEADERBOARD` — mark SGLB-05/06/07 ineligible
    - **Conflict with #9:** both touch `backend/benchmark/scripts/build_leaderboard.py` (different functions; usually rebases cleanly).
    - **Coordination flag:** ensure `NEW-HONEST-LEADERBOARD`'s footer-touch on `README2.md` does not collide with `NEW-EXTRACT-VERSION`'s in Round 3.

### Tier 1 — Round 3 (2 sequential; both touch files Round 2 modified)

Fire after Round 2 lands.

11. `NEW-CONTAM` — contamination probe scaffolding
    - **Conflict with `NEW-CI-RECEIPT`:** both modify `backend/benchmark/runner.py` `RunSummary`. `NEW-CI-RECEIPT` must land first; `NEW-CONTAM` rebases.
    - Scaffolding is zero cost; firing the probe against Azure baselines is cost-gated.
12. `NEW-EXTRACT-VERSION` — extraction-rule SHA in dataset metadata
    - **Conflict with `NEW-HONEST-LEADERBOARD`:** both touch `README2.md` reproducibility section. `NEW-HONEST-LEADERBOARD` already landed in Round 2; rebase.
    - Touches all ingestion modules; no overlap with `SOLO-9` (which creates a NEW file `pdpc_guidelines.py`).

### Tier 1 — Wave 2 (1 gated coordinator)

13. `NEW-BATCH-D` — frontier baselines coordinator.
    - **Hard prereqs (all must have landed):** `SOLO-17`, `NEW-CI-RECEIPT`, `NEW-CONTAM`, `NEW-EXTRACT-VERSION`, `NEW-VERIFY-BASELINES`.
    - Spawns up to 16 sub-agents (4 providers × 4 v0.1-eligible tasks). Azure cells inside are **cost-gated per cell** — explicit approval before each fire.

### Tier 1 — Conditional follow-up

14. `NEW-08-REFRAME-IF-LOW-KAPPA` — fire ONLY if `SOLO-17` reports any pairwise κ < 0.4. If all κ ≥ 0.4, skip entirely (zero work).

### Tier 2 — Data hardening (parallel with `NEW-BATCH-D`)

Can start once Round 3 lands; produces data, not methodology, so does not gate Wave 2.

15. Batch A (4 agents; internal A1→A2,A4; A2→A3) — MOM scraper for SGLB-05
16. Batch B (4 agents; internal B1→B2,B4; B2→B3) — CommonLII SG for SGLB-07
17. `NEW-SSO-EXPAND` — SSO ingest for EmA / ROC2021 / PC1871
    - **Gated on `NEW-EXTRACT-VERSION`** (the ingest path it touches now emits extraction-rule SHA).
18. `NEW-SGLB-04-PROD` — SGLB-04 1000+ production set
    - **Gated on `NEW-SAL-VALIDATION`** (the production set is only credible if the grammar is validated).

### Tier 3 — Vendor-facing infra (parallel; gated on Tier 1 closing)

Can start once `NEW-CI-RECEIPT` + `NEW-CONTAM` + `NEW-NORM-SPEC` + `NEW-DISPUTE-PROCESS` are all in.

19. `NEW-VENDOR-GUIDE` — the consolidating doc; all four prereqs must exist.
20. `NEW-LIB-PACKAGING` — **gated on `SOLO-10`** (licence header).
21. `NEW-INDEPENDENT-REPRO` — docs only; can start after Round 2.
22. Batch C (C1–C4 parallel-safe; non-overlapping files) — frontend audit fixes.
23. `SOLO-1` through `SOLO-6` — all mutually independent; parallel-safe.

### Tier 4 — Launch

24. `SOLO-8` — arXiv preprint draft (§§1-3 free now; §§4-5 gated on `NEW-BATCH-D` numbers).
25. Batch E (E1–E4 parallel-safe) — launch assets.

### Tier 5 — Copilot + v0.2

26+. Batch G (G1–G4 parallel), Batch H (H1–H3; H2/H3 cost-gated), Batch F (F1→F2,F3,F4), `SOLO-7`→`SOLO-11`, `SOLO-12`, COPILOT-1..4 (mostly parallel; per-prompt notes inline).

### Operational realities (must read)

- **Each prompt = fresh Claude Code session in its own worktree.** Spawn with `isolation: "worktree"`. Do not paste multiple prompts into one session — context collapses and the agent drifts.
- **API key prereqs.** `SOLO-17`, `NEW-CONTAM` (when fired), and `NEW-BATCH-D` Anthropic/Gemini cells need `ANTHROPIC_API_KEY` + `GEMINI_API_KEY` in `.env`. `NEW-BATCH-D` Azure cells need `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT`. Ollama needs the local server running.
- **Rate limits.** Firing `SOLO-17` (400 Anthropic + 400 Gemini calls) at the same wall-clock as `NEW-CONTAM`'s eventual probe (which doubles every per-case call) can hit per-minute rate caps. Stagger by ~5 minutes if both fire in the same hour.
- **Worktree disk overhead.** Each worktree is a full checkout. 6+ worktrees with `.venv` / `node_modules` is ~6× disk. Usually fine; flag if you're on a small SSD.
- **Cost gates are real.** Anthropic / Gemini / Ollama cells are cost-safe. Azure gpt-5 cells need explicit per-fire approval (5-10× the estimator quote due to reasoning-token billing).
- **Two items need YOU mid-run.** `SOLO-10` (you pick name + licence at the end), `SOLO-18` (you fill in the 40-case human review checklist offline).
- **You are the merge authority.** Agents commit on feature branches; never merge to `main` without your review.
- **Attention is the real bottleneck.** 12 agents reporting back simultaneously is harder to review well than 6 → 4 → 2 in waves. The round structure above is calibrated for review tractability, not just compute throughput.

---

# Tier 1 — Methodology fundamentals

_Defensibility floor. Until these land, no public baseline number is shippable. Items within Tier 1 may run in parallel except where hard-dependency notes apply._

## SOLO-17: SGLB-08 multi-judge ensemble pass (closes GAP-07)

```text
You are upgrading SGLB-08's labelling methodology from single-judge
(currently Azure gpt-5) to a ≥3-judge ensemble per coverage-matrix
§4.1. The 400-case reviewed dataset already exists at
backend/benchmark/datasets/sglb_08_clause_tone_reviewed/dataset.yaml.

Read AGENT-RUNBOOK.md, docs/sglb_specs/SGLB-08.md (the "Provisional-
approval caveat" section), docs/coverage-matrix.md §4.1, and
backend/benchmark/synthetic/sglb_08.py.

Goal: re-label each of the 400 cases with Anthropic + Gemini votes;
compute Cohen's κ per (generator, judge) pair AND per-cell agreement;
emit the artefacts that let the leaderboard publish "κ = X.XX
(n=400, 3 judges)".

Files you own:
- backend/benchmark/synthetic/multi_judge.py (new — runs the 2
  additional judges over the existing reviewed dataset)
- backend/benchmark/synthetic/agreement.py (new — Cohen's κ
  computation; pure stdlib + numpy where present)
- backend/benchmark/datasets/sglb_08_clause_tone_reviewed/judges.jsonl
  (new artefact — per-case vote per judge + κ summary)
- docs/sglb_specs/SGLB-08.md (update the "Provisional-approval"
  section once κ is known; if κ ≥ 0.4 across all judge pairs, bump
  version to "0.1-shipped"; if any pair drops below 0.4, file a
  follow-up issue per coverage-matrix §8)
- backend/tests/test_multi_judge.py + test_agreement.py

Files you must NOT touch:
- backend/benchmark/synthetic/sglb_08.py (existing pipeline)
- backend/benchmark/synthetic/generator.py (existing)
- The dataset.yaml itself — judges' votes live in judges.jsonl,
  alongside it. The gold label stays as-is in dataset.yaml; future
  v0.2 can flip a case if 2+ judges disagree with the gold.

Implementation:

1. For each case in dataset.yaml, dispatch the same prompt that
   benchmark.llm_runner.sglb_08_prompt_builder produces — i.e.
   re-use the existing prompt template; don't author a new one.
2. Send to both Anthropic (claude-sonnet-4.6 or whatever the user
   has) AND Gemini (gemini-2.0-flash).
3. Record per-case votes in judges.jsonl with the case_id +
   provider + model + raw output + parsed label + JSON-parse-success
   flag.
4. Compute pairwise Cohen's κ (gpt-5 ↔ Anthropic; gpt-5 ↔ Gemini;
   Anthropic ↔ Gemini). Also compute Fleiss' κ across all 3.
5. Per-cell breakdown: report κ for each (tone × clause_type)
   stratum so the user can see if any cell is below the 0.4 floor.

Cost gate: Anthropic ~$0.005/call × 400 = $2; Gemini ~$0.001/call
× 400 = $0.40. Total ~$2.40 — much cheaper than the original gpt-5
gen. Confirm with the user before firing if you're in any doubt; the
SGLB-08 synth gen already cost ~$20-50.

Provider environment: ANTHROPIC_API_KEY + GEMINI_API_KEY must be in
.env. If missing, --dry-run reports which keys are needed and stops.

Branch: feat/sglb-08-multi-judge.
Commit: `feat(sglb-08): multi-judge ensemble + κ for clause-tone
labels (advances #33; closes GAP-07)`.

Acceptance:
- judges.jsonl materialised with 400 × 2 vote rows.
- κ printed to stdout + persisted in a summary JSON.
- All κ pairs ≥ 0.4 (or, if any drop below, an issue is filed +
  spec doc updated to reflect retirement risk per coverage matrix §8).

Report back: the 3 pairwise κ values + Fleiss' κ + any cell where
agreement is dangerously low. Note any provider-specific JSON-parse
failures (those are a quality signal too).
```

## SOLO-18: SGLB-08 human-reviewed held-out subset (closes GAP-08)

```text
You are creating a human-reviewed held-out subset of SGLB-08 per
coverage-matrix §4.1 ("human-spot-checked held-out subset"). This
runs in PARALLEL with SOLO-17 (they touch different files).

Read AGENT-RUNBOOK.md, docs/sglb_specs/SGLB-08.md, the existing
reviewed dataset, CONTRIBUTING.md.

Goal: select 40 cases (10% sample, stratified across all 4 tones ×
6 clause types) for human review. Produce a checklist artefact the
user can fill in OFFLINE without touching the dataset YAML
structure. Once the user returns the checklist, you apply the
edits.

Files you own:
- backend/benchmark/datasets/sglb_08_clause_tone_reviewed/human_review_checklist.md
  (new — a markdown table with 40 rows, the user marks each
  "agree / disagree / unclear")
- scripts/select_sglb_08_holdout.py (new — selects the 40 cases
  deterministically with a seed)
- docs/sglb_specs/SGLB-08.md (update the "Provisional-approval"
  section once human checklist is returned; document the 40-case
  held-out subset and any cases the human reviewer flagged as
  incorrect)

Files you must NOT touch:
- The dataset.yaml itself — disputes from the human reviewer get
  recorded as errata in a separate file (mirror the CONTRIBUTING.md
  errata pattern).

Selection algorithm:
- Stratify: every (tone × clause_type) cell that has ≥1 case gets
  at least 1 in the holdout; remaining slots fill proportionally
  to cell size. seed=42.
- Each row in the checklist shows: case_id, tone, clause_type,
  first ~400 chars of clause_text, the gold label, an empty
  "human_decision" column, an empty "notes" column.

Branch: feat/sglb-08-human-holdout.
Commit (initial): `feat(sglb-08): generate 40-case human-review
checklist (advances #33; closes GAP-08 first half)`.
Commit (after user returns checklist): `feat(sglb-08): apply human
holdout decisions; flag disputes (closes GAP-08)`.

Acceptance:
- 40-row checklist generated, stratified across all cells.
- Spec doc references the file.
- A clear "user, please fill this in and report back" surfacing in
  your final message so the human-in-the-loop step doesn't get lost.

Report back: the stratification table (which cells got how many);
your hand-off message to the user.
```

## SOLO-10: Name + license decision (closes GAP-11)

```text
You are working on issue #40 in the junas repo. Read AGENT-RUNBOOK.md,
README2.md, the pivot history in git (commit a910403 and earlier),
CONTRIBUTING.md.

Goal: a 1-page decision record letting the user choose name +
license in <10 min.

Files you own:
- docs/decisions/dr-001-name-and-license.md (new)

Decision record sections:

1. **Name candidates** (3 options, pros/cons + discoverability check):
   - "SG-LegalBench" — clearest, matches LegalBench convention
   - "SingLegalBench" — more distinct but unwieldy
   - "LexSG-Eval" — academic-flavoured but loses brand
   - Any other you researched (Google "sg legal benchmark" to verify
     none collide)

2. **Code license** (4 options, with real legal-tech precedent):
   - MIT (LegalBench uses this)
   - Apache 2.0 (patent grant)
   - AGPL-3.0 (Mike OSS uses this; discourages closed-source forks)
   - GPL-3.0

3. **Dataset license** (4 options):
   - CC-BY-4.0
   - CC-BY-SA-4.0
   - CC-BY-NC-4.0
   - CC0

4. **Your recommendation** with one-sentence rationale.

Constraints:
- Research brief, NOT legal advice. No author legal opinions.
- Cite each license URL.
- Note what real legal-tech projects use each license (Mike OSS,
  LegalBench, Stanford CRFM benchmarks, OpenLegal, etc.).
- Surface the AGPL-vs-MIT trade-off explicitly: AGPL protects against
  closed-source competitor builds but reduces commercial-vendor
  uptake (some companies refuse AGPL).

Branch: docs/dr-001-name-license.
Commit: `docs(decision): name + license research brief (advances
#40; closes GAP-11)`. Co-Authored-By trailer.

Acceptance: 1-page brief in markdown; user can make the call without
asking follow-ups.
Report back: your one-sentence recommendation; any surprising
constraint you found.
```

## SOLO-9: PDPC Advisory Guidelines scraper (#60)

```text
You are implementing issue #60 in the junas repo: PDPC Advisory
Guidelines scraper (unblocks SGLB-14 Statutory-Entailment data;
v0.2 task).

Read AGENT-RUNBOOK.md, docs/sglb_specs/SGLB-14.md, and
backend/data/ingestion/pdpc.py (your structural template).

Source: https://www.pdpc.gov.sg/help-and-resources/2017/
(PDPC publishes Advisory Guidelines as PDF documents with text
extractable via pypdf).

Files in scope:
- backend/data/ingestion/pdpc_guidelines.py (new — separate from
  pdpc.py which handles enforcement decisions)
- backend/api/adapters/public/pdpc_guidance.py (existing stub;
  flesh out)
- backend/tests/fixtures/pdpc_guidelines/* (1-2 PDF samples)
- backend/tests/test_pdpc_guidelines.py
- Makefile: + ingest-pdpc-guidelines target

Schema (per JSONL row):
- doc_id, source_url, title, pdf_url, body_plain (extracted from
  PDF), section_headings (list of h1/h2-like markers), pub_date.

Branch: feat/pdpc-guidelines-scraper.
Commit: `feat(pdpc): Advisory Guidelines scraper (closes #60;
advances SGLB-14)`.

Acceptance: at least one PDF fully extracted; downstream SGLB-14
builder (not your concern; it'll be a follow-up) can be pointed at
the output.

Report back: PDF text-extraction fidelity; some PDPC PDFs are
scanned images — flag those.
```

## NEW-CI-RECEIPT: Bootstrap CIs in every receipt (closes GAP-02)

```text
You are implementing GAP-02 closure in the junas repo: bootstrap CIs
must land in every receipt JSON during the benchmark run, not as a
post-hoc leaderboard step.

Read AGENT-RUNBOOK.md, GAPS-TO-REMEDY.md §GAP-02,
backend/benchmark/runner.py, backend/benchmark/scripts/build_leaderboard.py
(specifically `_bootstrap()` at lines 125-142), backend/benchmark/llm_runner.py.

Goal: every receipt persisted by `benchmark.cli run --output ...`
includes per-evaluator `ci_low`, `ci_high`, and `n_bootstrap` fields
alongside the existing `per_evaluator_mean`. Move `_bootstrap()` to
a shared helper so the leaderboard builder and the runner share one
implementation.

Files you own:
- backend/benchmark/stats.py (NEW — extract `_bootstrap()` as
  `bootstrap_ci(values, *, seed, n=1000)` returning a dataclass with
  mean, ci_low, ci_high, n_bootstrap)
- backend/benchmark/runner.py (modify `RunSummary` and assembly path
  to call bootstrap_ci() per evaluator; persist into receipt)
- backend/benchmark/scripts/build_leaderboard.py (replace local
  `_bootstrap()` with import from `benchmark.stats`; behaviour-
  preserving)
- backend/benchmark/receipt_schema.md (NEW or updated — document the
  CI fields + n_bootstrap + seed)
- backend/tests/test_stats.py (NEW)
- backend/tests/test_runner_ci.py (NEW — receipt JSON contains
  ci_low + ci_high per evaluator after a mock run; seed determinism)

Files you must NOT touch:
- backend/benchmark/llm_runner.py prompt builders (out of scope)
- Any dataset YAML

Acceptance:
- pytest -x -q backend/tests/test_stats.py backend/tests/test_runner_ci.py
  passes.
- An existing receipt regenerated under the new code contains
  ci_low + ci_high + n_bootstrap per evaluator.
- Leaderboard builder produces identical CI values (refactor is
  behaviour-preserving).

Branch: feat/ci-in-receipts.
Commit: `feat(benchmark): bootstrap CIs in every receipt (closes
GAP-02)`. Co-Authored-By trailer.

Report back: receipt JSON schema diff before/after; any consumers
of receipts that need a schema migration.
```

## NEW-CONTAM: Contamination probe per (task, model) (closes GAP-01)

```text
You are implementing GAP-01 closure in the junas repo: contamination
probe per (task, model) so vendors can see which baselines memorised
labels vs. reasoned from facts.

Read AGENT-RUNBOOK.md, GAPS-TO-REMEDY.md §GAP-01,
docs/coverage-matrix.md §4.3, backend/benchmark/llm_runner.py.

Goal: a separate probe pass per labelled case that asks the model
to recall the labelled property verbatim WITHOUT giving it the input.
Per-case `memorisation_flag` recorded; per-task contamination
summary (mean memorisation rate, contamination-adjusted score)
emitted on the receipt.

Files you own:
- backend/benchmark/contamination.py (NEW — probe runner; per-task
  probe-prompt builder; flag scorer)
- backend/benchmark/runner.py (extend `RunSummary` with
  contamination_summary; gate behind `--contamination-probe` flag
  default-off)
- backend/benchmark/cli.py (add `--contamination-probe` flag)
- backend/tests/test_contamination.py (NEW)
- docs/methodology/contamination.md (NEW — vendor-facing doc
  explaining the probe + interpretation)

Files you must NOT touch:
- Existing prompt builders in backend/benchmark/llm_runner.py — the
  probe prompts are NEW + task-specific, defined in contamination.py.

Probe design per task:
- SGLB-01: "What was the outcome (obligation breached + penalty
  band) of PDPC case <case_name>?" — match against gold; flag
  per-case memorisation_score ∈ [0,1].
- SGLB-02: "What is the text of <statute> section <N>?" — match
  against gold answer fragment; flag accordingly.
- SGLB-04: skip — the citation grammar is deterministic; memorisation
  isn't the relevant question.
- SGLB-08: "What is the tone label of clause <clause_id>?" —
  memorisation here means the model has seen the synthetic dataset;
  flag accordingly.

Per-task summary fields persisted in receipt:
- mean_memorisation_rate: float in [0,1]
- contamination_adjusted_score: per-evaluator mean computed only on
  cases with memorisation_score < 0.5

Acceptance:
- `python -m benchmark.cli run --workflow sglb_01 --dataset ...
  --evaluator sglb_01_obligations_f1 --contamination-probe --output
  receipt.json` produces a receipt with contamination_summary +
  per-case memorisation_score.
- The probe adds <2x runtime over the base run.
- pytest passes.

Cost gate: the probe doubles LLM calls. For SGLB-01 (N=211) at
Anthropic pricing this is ~$1; at Azure gpt-5 with reasoning tokens
this could be $10-20. Get explicit approval before firing the probe
against Azure baselines.

Branch: feat/contamination-probe.
Commit: `feat(benchmark): contamination probe per task+model (closes
GAP-01)`.

Report back: which models showed the highest memorisation rate per
task; any task where the probe formulation feels insufficient.
```

## NEW-SAL-VALIDATION: SAL grammar tested against published examples (closes GAP-05)

```text
You are implementing GAP-05 closure: SAL citation grammar must be
validated against the SAL Style Guide's own published examples.

Read AGENT-RUNBOOK.md, GAPS-TO-REMEDY.md §GAP-05,
backend/api/services/sal_citation.py (the grammar implementation),
backend/tests/test_sal_citation.py (current tests, all synthetic).

Goal: extract every worked citation example from
SAL_Style_Guide_Quick_Reference_2007_Ed.pdf and
SLR_Style_Guide_2021.pdf (locate under asset/, docs/references/, or
similar — search first; flag if missing). Add a test that asserts
each published example is parsed + validated correctly by the
grammar. Any test failure is a grammar bug to fix before SGLB-04
can be defended publicly.

Files you own:
- backend/tests/test_sal_citation_published_examples.py (NEW)
- backend/tests/fixtures/sal_style_guide/examples.yaml (NEW — one
  row per extracted example: example_text, expected_kind,
  expected_components, source_section_in_guide)
- backend/api/services/sal_citation.py (only if a published-example
  test reveals a grammar bug; fix and document the bug in the
  commit)

Files you must NOT touch:
- The PDF files themselves.
- Existing tests in test_sal_citation.py (preserve as-is; this file
  is additive).

Process:
1. Locate the two PDFs in the repo. If not present, escalate to the
   user — do NOT fabricate examples.
2. Extract every worked example by section. Cite the page + section
   in the YAML.
3. Each example: classify the kind (neutral citation, SLR(R),
   statute Cap., etc.) and the expected validation result.
4. Run the test suite. Any failure → either a grammar bug (fix the
   grammar) or an extraction error (fix the YAML row, document why).

Acceptance:
- test_sal_citation_published_examples.py: all examples parse +
  validate correctly.
- At least 30 examples extracted from each guide.
- If the grammar required fixing, the fix is described in the
  commit message.

Branch: feat/sal-grammar-published-examples.
Commit: `test(sal): validate grammar against SAL Style Guide
published examples (closes GAP-05)`.

Report back: total examples extracted; any grammar bug found + fix
applied; any example the published guide flagged as edge-case where
v0.2 grammar work is warranted.
```

## NEW-EXTRACT-VERSION: Extraction-rule SHA in dataset metadata (closes GAP-06)

```text
You are implementing GAP-06 closure: extraction-rule SHA pinned in
every dataset row + dataset YAML header.

Read AGENT-RUNBOOK.md, GAPS-TO-REMEDY.md §GAP-06,
backend/data/ingestion/pdpc.py (lines 47-178 — taxonomy +
extraction + emit), backend/data/ingestion/sso.py.

Goal: every dataset row carries an `extraction_rule_sha` field
(git rev of the ingestion module file at build time); every dataset
YAML header carries an `extraction_rules` map enumerating the SHAs
per module touched during build. A CI validator confirms presence.

Files you own:
- backend/data/ingestion/_provenance.py (NEW — helper that returns
  the current git SHA of a given module file via `git log -n 1
  --pretty=%H -- <path>`)
- backend/data/ingestion/pdpc.py (modify emit path to include
  extraction_rule_sha per row + write top-level extraction_rules map)
- backend/data/ingestion/sso.py (same)
- backend/data/ingestion/mom.py (if landed via Batch A; same)
- backend/data/ingestion/commonlii_sg.py (if landed via Batch B; same)
- backend/benchmark/dataset_builders/sglb_*.py (each builder writes
  extraction_rules to the dataset YAML header)
- .github/workflows/ci.yml (add a validator step that fails if any
  dataset row lacks extraction_rule_sha)
- backend/benchmark/dataset_validator.py (NEW — CI check)
- backend/tests/test_provenance.py
- backend/tests/test_dataset_validator.py
- README2.md §Reproducibility (update to describe the new fields)

Files you must NOT touch:
- Live dataset YAMLs (regenerate via build, do not hand-edit).

Schema additions:
- Per row: `extraction_rule_sha: "<7-char git short SHA>"`
- Top of YAML: `extraction_rules: { pdpc: <sha>, sso: <sha>, ... }`

Acceptance:
- Every freshly-built dataset has the new fields.
- CI fails if a row is missing the field.
- pytest passes.

Branch: feat/extraction-rule-sha.
Commit: `feat(data): pin extraction-rule SHA in dataset metadata
(closes GAP-06)`.

Report back: any dataset that couldn't be rebuilt cleanly + why.
```

## NEW-HONEST-LEADERBOARD: Drop empty tasks from v0.1 leaderboard (closes GAP-04)

```text
You are implementing GAP-04 closure: SGLB-05/06/07 must not appear
on the v0.1 leaderboard with oracle-1.0 scores. Mirror the
`benchmark_eligible = False` pattern used by ElitigationAdapter at
backend/api/adapters/public/elitigation.py:36.

Read AGENT-RUNBOOK.md, GAPS-TO-REMEDY.md §GAP-04,
backend/api/adapters/public/elitigation.py:36,
backend/benchmark/scripts/build_leaderboard.py, README2.md task table.

Goal:
- Each of SGLB-05/06/07 carries `benchmark_eligible = False` on its
  task registration until the data lands.
- The leaderboard builder skips ineligible tasks.
- README2.md task table shows the three tasks with status
  "code-shipped, awaiting data" and a footnote per task linking to
  the data dependency (Batch A for SGLB-05, NEW-SSO-EXPAND for
  SGLB-06, Batch B for SGLB-07).
- When the data lands (downstream prompts), flipping the flag back
  to True is a one-line change.

Files you own:
- backend/benchmark/tasks/sglb_05.py
- backend/benchmark/tasks/sglb_06.py
- backend/benchmark/tasks/sglb_07.py
- backend/benchmark/registry.py (add `benchmark_eligible` to the
  Task registration; default True)
- backend/benchmark/scripts/build_leaderboard.py (filter by
  benchmark_eligible)
- backend/api/routers/benchmarks.py (leaderboard API endpoint also
  filters)
- README2.md (update §Tasks table)
- backend/tests/test_registry.py
- backend/tests/test_leaderboard_eligibility.py (NEW)

Files you must NOT touch:
- The dataset_builders/* for these tasks; the builders are correct,
  they just have no data to read.

Acceptance:
- The published leaderboard shows only SGLB-01, SGLB-02, SGLB-04,
  SGLB-08 (the v0.1 eligible set).
- README2 task table includes all 8 tasks with eligibility status.
- Tests pass.

Branch: feat/honest-leaderboard.
Commit: `feat(benchmark): mark SGLB-05/06/07 ineligible until data
lands (closes GAP-04)`.

Report back: the README2 table you produced; the eligibility filter
predicate; any place the harness silently swallowed an oracle 1.0
score that the user should know about.
```

## NEW-NORM-SPEC: Citation/statute normalisation spec (closes GAP-09)

```text
You are implementing GAP-09 closure: a published normalisation spec
covering citation + statute canonical forms.

Read AGENT-RUNBOOK.md, GAPS-TO-REMEDY.md §GAP-09,
backend/benchmark/evaluators.py:520-536 (current section normaliser),
backend/api/services/sal_citation.py (case citation parsing).

Goal: a vendor-facing document at docs/normalisation-spec.md that
describes (a) what gets normalised, (b) the canonical form, (c) the
test corpus that proves the implementation matches the spec.

Files you own:
- docs/normalisation-spec.md (NEW)
- backend/tests/fixtures/normalisation/corpus.yaml (NEW — labelled
  pairs: raw_form → canonical_form per kind)
- backend/tests/test_normalisation_spec.py (NEW — loads the corpus,
  runs each normaliser, asserts canonical match)

Files you must NOT touch:
- The normaliser implementations themselves, unless the test
  reveals a divergence (then fix the divergence and document in
  the commit).

Spec must cover:
1. Section citation: input forms accepted (`s 13`, `section 13`,
   `s. 13`, `Sec. 13 of the PDPA`, `Section 13 of the Personal Data
   Protection Act 2012`); canonical form (`s 13 of the personal data
   protection act 2012`); rationale.
2. Statute short name: PDPA, EmA, PC, ROC2021; long-form mapping;
   precedence rules.
3. Case neutral citation: `[YYYY] SGCA NNN` format; allowed court
   codes; year range.
4. SLR / SLR(R) citation: format spec + edge cases.

Each kind: list ≥10 canonical pairs in the test corpus, ≥3 negative
cases (inputs that should not normalise).

Acceptance:
- The spec doc is readable by a vendor in <10 min.
- Tests pass.
- Anyone can submit a corpus addition via PR.

Branch: docs/normalisation-spec.
Commit: `docs(normalisation): publish canonical-form spec + test
corpus (closes GAP-09)`.

Report back: any normaliser behaviour the spec couldn't describe
cleanly (those are bug-or-spec-gap candidates).
```

## NEW-DISPUTE-PROCESS: Published dispute/errata process (closes GAP-10)

```text
You are implementing GAP-10 closure: a published dispute/errata
process so vendors and labelled-case subjects have a path to file
disputes.

Read AGENT-RUNBOOK.md, GAPS-TO-REMEDY.md §GAP-10, CONTRIBUTING.md
(any existing errata mention).

Goal: a vendor-facing dispute process operationalised via GitHub.

Files you own:
- docs/dispute-process.md (NEW — vendor-facing; what to file, where,
  what happens next, SLA, corrigenda cadence)
- .github/ISSUE_TEMPLATE/label_dispute.yml (NEW — structured
  template: which case, which label, evidence, suggested correction)
- .github/ISSUE_TEMPLATE/methodology_concern.yml (NEW — separate
  from label disputes; for systematic concerns)
- CONTRIBUTING.md (link to docs/dispute-process.md from the existing
  errata mention; do not duplicate content)
- docs/versioning.md (NEW — dataset patch-version policy: every
  accepted dispute bumps patch; minor versions for taxonomy changes;
  major for methodology pivots)

Files you must NOT touch:
- Any dataset YAML (this prompt establishes the process; first
  disputes are handled in follow-up PRs).

Spec must cover:
1. Triage SLA: 14 days from filing to triage label
   (accepted/rejected/needs-evidence).
2. Resolution cadence: corrigenda land at next minor release (every
   ~4-8 weeks).
3. Versioning: dataset patch version (sglb-01-v0.1.1) for accepted
   disputes; minor version (sglb-01-v0.2) for taxonomy changes;
   major (sglb-01-v1.0) for methodology pivots.
4. Public errata log: link to data/sglb_NN/errata.md per task.
5. Reviewer disclosure: if a maintainer was involved in labelling
   the disputed case, they recuse from triage.

Acceptance:
- A vendor can find the dispute process in <2 clicks from the README.
- A GitHub issue filed via the template includes all required
  evidence fields.
- The versioning spec is unambiguous about which version-bump
  applies to which kind of change.

Branch: docs/dispute-process.
Commit: `docs(process): publish dispute + versioning process (closes
GAP-10)`.

Report back: any class of dispute the process doesn't cover; whether
a public corrigenda mailing list is worth setting up for vendors who
want push notifications.
```

## NEW-VERIFY-BASELINES: Audit Anthropic+Gemini baseline gap (closes GAP-03 audit half)

```text
You are implementing GAP-03 closure: audit the gap between commit
messages claiming Anthropic + Gemini baselines and the actual
contents of runs/baselines/.

Read AGENT-RUNBOOK.md, GAPS-TO-REMEDY.md §GAP-03.

Goal: investigate commits 414bb4b ("Gemini baselines across
SGLB-01/02/04") and 9beb086 (or the latest Anthropic baselines
commit). Locate the receipt JSON files if they exist (in a feature
branch, deleted accidentally, stored elsewhere). If unrecoverable,
explicitly document the gap and queue the rerun under NEW-BATCH-D.

Files you own:
- runs/baselines/PROVENANCE.md (NEW — documents what was claimed,
  what's on disk, what's recoverable, what needs rerunning)
- runs/baselines/<provider>/<task>/<timestamp>.json (only if
  recovering committed-but-missing receipts; do not fabricate)

Files you must NOT touch:
- Any existing receipt JSON.
- Any code (this is an audit, not a code change).

Process:
1. `git show 414bb4b --stat` — see what the commit actually added.
2. If the commit added receipt JSONs but they're missing from main:
   `git show 414bb4b:runs/baselines/...` to recover. Do not force a
   recovery if uncertain; document and escalate.
3. Same for the Anthropic baseline commit.
4. If receipts ARE on disk under a different path: locate them,
   document the path in PROVENANCE.md.
5. If receipts are NOT recoverable: explicitly note "rerun required;
   see NEW-BATCH-D".

Acceptance:
- runs/baselines/PROVENANCE.md exists and is honest. For each
  (provider × task) combination claimed by commit history, the doc
  states one of: { receipt-present-here, receipt-missing-rerun-via-
  BATCH-D }.
- No fabricated receipts.

Branch: docs/baseline-provenance-audit.
Commit: `docs(baselines): audit provenance gap (closes GAP-03 audit
half)`.

Report back: what was claimed; what's recoverable; what needs
rerunning. This output feeds directly into NEW-BATCH-D's task list.
```

## NEW-BATCH-D: Full frontier baseline run with new receipt format (closes GAP-03 + GAP-16)

```text
You are launching NEW-BATCH-D, the full frontier model baseline run
across SG-LegalBench v0.1 eligible tasks. This REPLACES the stubbed
"Batch D" from the pre-rewrite plan.

Read AGENT-RUNBOOK.md, GAPS-TO-REMEDY.md (especially §GAP-01, §GAP-02,
§GAP-03, §GAP-06 — all closures must be reflected in the receipts),
docs/coverage-matrix.md §4.4, backend/benchmark/cli.py, AGENT-RUNBOOK.md
§8 (cost gates).

NEW-BATCH-D is a coordinator prompt; it spawns one agent per
(provider × task) cell. Total cells: 4 providers × 4 v0.1-eligible
tasks = 16 agents at maximum. Some cells are cost-gated.

Eligible v0.1 tasks: SGLB-01, SGLB-02, SGLB-04, SGLB-08.
SGLB-05/06/07 remain `benchmark_eligible=False` until data lands
(per NEW-HONEST-LEADERBOARD).

Providers + cost class:
- anthropic (claude-opus-4-7 + claude-sonnet-4-6 + claude-haiku-4-5)
  — cost-safe per task
- google (gemini-2.0-flash + gemini-2.0-pro) — cost-safe
- openai (gpt-5 via Azure) — cost-gated; ~$2-50 per task depending
  on reasoning tokens
- ollama (qwen2.5vl:7b for local-baseline floor) — cost-safe

Pre-requisites (must land first):
- NEW-CI-RECEIPT — every receipt must include CI fields.
- NEW-CONTAM — every Batch D run uses --contamination-probe;
  receipts must include contamination_summary.
- NEW-EXTRACT-VERSION — receipts must include extraction_rule_sha.
- NEW-VERIFY-BASELINES — must complete first so this prompt knows
  which cells need rerunning vs which already have receipts.
- SOLO-17 — SGLB-08 receipts must record the κ-aware label set.

Coordination:
- One agent per (provider × task) cell.
- Each agent works in its own worktree (per AGENT-RUNBOOK §7).
- Branch naming: feat/batch-d-<provider>-<task> (e.g.,
  feat/batch-d-anthropic-sglb-01).
- Each agent commits its receipt JSON + a one-line entry in
  runs/baselines/INDEX.md.
- The coordinator (this prompt) tracks progress via INDEX.md.

Per-cell agent contract (the prompt to fire per cell):
"""
You are running baseline (provider=<P>, task=<T>) for NEW-BATCH-D.

Read AGENT-RUNBOOK.md, GAPS-TO-REMEDY.md §GAP-01/02/06, the
per-task spec at docs/sglb_specs/<T>.md, and the receipt schema at
backend/benchmark/receipt_schema.md.

Cost gate (per AGENT-RUNBOOK §8): if provider is azure-gpt5, STOP
and request explicit user approval before firing. Estimated cost
for this cell: $<X> (anthropic ~$1, gemini ~$0.40, azure ~$10-50,
ollama $0).

Run:
  python -m benchmark.cli run --workflow <task> --dataset \
    backend/benchmark/datasets/<task>.yaml --evaluator <eval> \
    --strict --contamination-probe \
    --output runs/baselines/<P>/<T>/$(date +%Y%m%dT%H%M%SZ).json

Verify the receipt includes:
- per_evaluator_mean
- ci_low, ci_high, n_bootstrap per evaluator (GAP-02)
- contamination_summary with mean_memorisation_rate +
  contamination_adjusted_score (GAP-01)
- extraction_rule_sha (GAP-06)
- prompt_sha + prompt_version (existing)

Append a one-line entry to runs/baselines/INDEX.md.

Branch: feat/batch-d-<provider>-<task>.
Commit: `feat(baselines): <provider> baseline for <task> (advances
NEW-BATCH-D)`.

Report back: per_evaluator_mean + ci range + contamination rate.
"""

Coordinator (this prompt) responsibilities:
1. Confirm pre-requisites have all landed.
2. Decide which cells need running (per NEW-VERIFY-BASELINES audit).
3. Fire cost-safe cells in parallel.
4. Request explicit user approval before firing Azure cells.
5. After all cells complete, run the leaderboard build:
   `python -m benchmark.scripts.build_leaderboard --out
   runs/leaderboard.csv`.
6. Update README2.md with the new leaderboard reference.

Acceptance:
- All eligible cells have receipts on disk.
- runs/baselines/INDEX.md is complete.
- Leaderboard reflects the new runs.

Report back: the leaderboard summary; any cell that failed or
produced an anomalous result; total spend.
```

## NEW-08-REFRAME-IF-LOW-KAPPA (conditional, gated on SOLO-17)

```text
You are implementing the conditional fallback for SGLB-08 if
SOLO-17's κ computation produces any judge-pair with κ < 0.4 (per
docs/coverage-matrix.md §4.1 + §8). This prompt is GATED on
SOLO-17 completing.

Read AGENT-RUNBOOK.md, GAPS-TO-REMEDY.md §GAP-07,
docs/coverage-matrix.md §4.1 + §8, docs/sglb_specs/SGLB-08.md,
the κ summary produced by SOLO-17.

Decision:
- If ALL pairwise κ ≥ 0.4 AND Fleiss' κ ≥ 0.4: this prompt is a
  no-op. Document the κ values in the spec doc; close the prompt.
- If ANY pair < 0.4: reframe SGLB-08 in v0.1 as
  "Inter-Judge-Alignment" sub-track (the metric measures judge
  agreement, not ground truth on tone). This is the honest framing
  under low κ.

If reframing:

Files you own:
- docs/sglb_specs/SGLB-08.md (rename task framing throughout; update
  title from "Clause-Tone" to "Inter-Judge-Tone-Alignment"; rewrite
  the §"What this measures" section to be explicit about the metric)
- README2.md (update the §Tasks table for SGLB-08; note the reframing)
- backend/benchmark/tasks/sglb_08.py (only docstrings; the metric
  itself is unchanged — F1 of model prediction against the
  ensemble-majority label)
- docs/preprint/sglb-preprint.md (if SOLO-8 has landed, update §3)

Files you must NOT touch:
- The dataset itself; the labels are unchanged.
- The evaluators; the F1 computation is unchanged.

The reframing language (use exactly):
"SGLB-08 measures alignment between a tested model's tone
classification and the majority label across a 3-judge ensemble
(Anthropic + Gemini + Azure gpt-5). It is NOT a measure of
ground-truth tone correctness; LLM-judges may share systematic
biases. Inter-judge Cohen's κ across all pairs is published with
every leaderboard row."

Branch: docs/sglb-08-reframe.
Commit: `docs(sglb-08): reframe as Inter-Judge-Alignment under low κ
(closes GAP-07 conditional half)`.

Acceptance: framing is consistent across spec + README + preprint;
no claim of ground-truth tone correctness remains.

Report back: the κ values that triggered the reframe; whether v0.2
should retire the task per coverage-matrix §8.
```

---

# Tier 2 — Data hardening

_Closes empty tasks (SGLB-05/06/07) + scales N where possible. Gated on Tier 1 closure._

# Batch A — MOM Scraper (#59), 4 parallel agents

**Goal:** unblock SGLB-05 Employment-Issue with real data.

**Coordination contract:** all four agents commit to the same branch
`feat/mom-scraper`. A1 lands first (it writes the network layer + the
shared JSONL schema), then A2/A3/A4 fan out off A1's branch in
separate worktrees. JSONL row schema is fixed by `docs/sglb_specs/
SGLB-05.md` — every agent reads that first.

## A1: MOM ingestion network layer

```text
You are working on issue #59 (MOM enforcement actions + guidance
scraper) in the junas repo.

Read AGENT-RUNBOOK.md first. Then read docs/sglb_specs/SGLB-05.md to
see the JSONL row schema this scraper must emit. Then read
backend/data/ingestion/sso.py — that's the canonical template you
should mirror for rate limiting, retry, and version pinning.

Your scope: implement the NETWORK layer only.

Files you own:
- backend/data/ingestion/mom.py (new)
- backend/ml/pipelines/ingest_mom.py (new; minimal entrypoint that
  calls into mom.py::run())
- Makefile: add an `ingest-mom` target + include in `ingest-all`
- backend/api/adapters/public/mom.py (existing stub; flesh out
  fetch_all / fetch_by_id only — leave parser concerns to A2)

Files you must NOT touch (they belong to A2/A3/A4):
- backend/data/parsers/mom_parser.py
- backend/tests/fixtures/mom/*
- backend/tests/test_mom_*.py

Implementation requirements:

1. Discover MOM's enforcement-action listing URL structure. Fetch one
   representative listing page + one detail page, save them to
   backend/tests/fixtures/mom/ for A2 to parse against. Do this BEFORE
   writing the scraper logic so A2 can start in parallel.
2. Rate limit: 3 seconds between requests minimum (mirror SSO's
   crawl_delay). Add jitter.
3. Retry with exponential backoff on 5xx + transport errors. MAX_RETRIES=4.
4. Stable doc_id derived from the source URL (hash; see how
   data/ingestion/pdpc.py stable_id() does it).
5. Idempotent rerun: track a `seen` set when appending to the JSONL.
6. Output path: vendor-data/mom/enforcement.jsonl (gitignored).
7. CLI entrypoint: `python -m data.ingestion.mom --output ... [--force]`.
8. The run() function returns the number of records written.

Network safety: if the user hasn't approved the live fetch, default
to a `--dry-run` mode that prints the planned URL set without firing
HTTP. Document this in the spec.

Branch: feat/mom-scraper (push to a feature branch, not main).
Commit message format: `feat(mom): network layer for MOM enforcement
scraper (advances #59)`. Conventional commits, Co-Authored-By trailer.

Acceptance:
- `python -m data.ingestion.mom --dry-run` prints planned URLs.
- Saved fixtures committed to backend/tests/fixtures/mom/.
- The Makefile target works.
- No new pytest failures (full run from runbook §4).

Report back: branch SHA, files added, the fixture URLs you fetched,
and any TOS observations from MOM's site that affect publication.
```

## A2: MOM HTML parser

```text
You are working on issue #59 (MOM scraper) in the junas repo.

Read AGENT-RUNBOOK.md, docs/sglb_specs/SGLB-05.md, and
backend/data/parsers/sso_parser.py (your structural template).

WAIT until agent A1 has landed feat/mom-scraper with at least one
fixture HTML in backend/tests/fixtures/mom/. Then rebase your worktree
onto that branch.

Your scope: parse MOM HTML into structured records.

Files you own:
- backend/data/parsers/mom_parser.py (new)
- backend/tests/test_mom_parser.py (new)

Files you must NOT touch:
- backend/data/ingestion/mom.py (A1 owns)
- backend/api/adapters/public/mom.py (A1 owns)
- backend/tests/fixtures/mom/* (A1 owns the fetch; you only read)

Implementation requirements:

1. BeautifulSoup-based, lxml backend. Same dependency set as
   sso_parser.py — no new deps.
2. Output dataclass `MomRecord` with EXACTLY these fields (matches
   the SGLB-05 spec):
   - doc_id: str
   - source_url: str
   - subsource: str  # "press_release" | "faq" | "advisory"
   - title: str
   - body_plain: str
   - stated_breaches: list[str]  # MOM's own categorisation tags
   - act_references: list[str]  # e.g. ["s 10 of the Employment Act"]
   - subject_organisation: str | None
   - pub_date: str  # ISO date when parseable
3. `stated_breaches` extraction: MOM publishes categorisation tags
   on enforcement pages (e.g. "Notice Period Breach", "CPF
   Non-Contribution"). Find the DOM markers + extract verbatim. Do
   NOT infer labels from prose — that violates mechanical extraction
   (coverage-matrix §4.1).
4. If a page lacks `stated_breaches`, return an empty list — let the
   builder (sglb_05.py) filter it out.

Tests (in test_mom_parser.py):
- Parse the A1 fixture → MomRecord with all fields populated.
- Empty stated_breaches → empty list, not None.
- Repealed / withdrawn pages → handled gracefully.
- HTML with unicode/whitespace edge cases → normalised.

Branch: feat/mom-scraper (same as A1; you commit to it after A1).
Commit format: `feat(mom): HTML parser for press releases + FAQs
(advances #59)`.

Acceptance:
- All tests pass (pytest -x -q backend/tests/test_mom_parser.py).
- Parser handles the A1 fixtures cleanly.

Report back: branch SHA, fields populated reliably vs heuristically,
any DOM-marker fragility you noticed.
```

## A3: SGLB-05 builder integration

```text
You are working on issue #59 (MOM scraper) in the junas repo.

Read AGENT-RUNBOOK.md, docs/sglb_specs/SGLB-05.md, and
backend/benchmark/dataset_builders/sglb_05.py.

WAIT until A1+A2 have landed feat/mom-scraper with parser + at least
one parsed fixture record.

Your scope: end-to-end integration smoke. The sglb_05 builder
already exists and reads vendor-data/mom/enforcement.jsonl. Your job
is to verify the pipeline works end-to-end on the fixtures and add
the integration test that proves it.

Files you own:
- backend/tests/test_mom_ingestion.py (new — end-to-end test that
  feeds the fixture through parser → JSONL writer → builder → harness)
- backend/benchmark/dataset_builders/sglb_05.py (only touch if a real
  bug surfaces; otherwise leave alone)
- docs/sglb_specs/SGLB-05.md (bump version line from
  "0.1-code-shipped" to "0.1-shipped (smoke)" if the end-to-end
  works against fixtures; add a CHANGELOG entry)

Files you must NOT touch:
- backend/data/ingestion/mom.py (A1)
- backend/data/parsers/mom_parser.py (A2)
- backend/api/adapters/public/mom.py (A1/A4)

Integration test:
1. Load the A1 fixture HTML.
2. Run it through A2's mom_parser.
3. Write the MomRecord(s) to a tmp_path JSONL.
4. Run sglb_05.build() against that JSONL.
5. Assert at least one case emits with the expected schema.
6. Run the harness end-to-end:
   `benchmark.runner.run(workflow="sglb_05", dataset_path=<yaml>,
   evaluators=["multi_label_f1"])`. Assert oracle score == 1.0.

Acceptance:
- `pytest -x -q backend/tests/test_mom_ingestion.py` passes.
- Spec doc bumped to reflect shipped-smoke status.

Report back: end-to-end test passing, number of MomRecords the
fixture yielded, any quality concerns about the gold labels.
```

## A4: MOM adapter contract + frontend wiring

```text
You are working on issue #59 (MOM scraper) in the junas repo.

Read AGENT-RUNBOOK.md, backend/api/adapters/base.py (the
LegalSourceAdapter protocol), and backend/api/adapters/public/sso.py
for the canonical adapter shape.

WAIT until A1 has landed the basic mom.py + Makefile.

Your scope: adapter conformance + frontend legal-sources page entry.

Files you own:
- backend/api/adapters/public/mom.py (existing stub; ensure
  metadata, extra_schema, fetch_all + fetch_by_id all match the
  LegalSourceAdapter contract once A1's mom.py is in place; this
  may be a one-line refactor or a re-wire)
- backend/tests/test_adapters.py (add a test_mom_adapter test
  mirroring the existing test_pdpc_adapter pattern)
- frontend/app/legal-sources/page.tsx (add an entry for MOM if not
  present)

Files you must NOT touch:
- backend/data/ingestion/mom.py (A1)
- backend/data/parsers/mom_parser.py (A2)
- backend/benchmark/dataset_builders/sglb_05.py (A3)

Tests:
- Adapter metadata fields populated.
- extra_schema keys match the MomRecord fields from A2.
- fetch_all() either works against the fixture or raises a clear
  SourceAdapterError when no fixture path is configured (mirror
  SsoAdapter behaviour).

Acceptance:
- `pytest -x -q backend/tests/test_adapters.py` passes.
- The frontend /legal-sources page lists MOM with the correct
  attribution + crawl_delay note.

Report back: any contract divergence between MomRecord and the
adapter's extra_schema (this is the kind of drift that causes future
bugs).
```

# Batch B — CommonLII SG Case Ingester (#34), 4 parallel agents

**Goal:** unblock SGLB-07 Jurisdiction-Routing with real data.

**Coordination contract:** branch `feat/commonlii-sg-ingester`. B1
lands first with the fixture + network layer. B2-B4 fan out. The
CRITICAL piece is B3 — the `jurisdiction_statements` regex extractor
that produces the SGLB-07 gold labels.

## B1: CommonLII SG listing + judgment fetcher

```text
You are working on issue #34 (CommonLII SG case ingester; SGLB-07
data dep) in the junas repo.

Read AGENT-RUNBOOK.md, docs/sglb_specs/SGLB-07.md, and
backend/data/ingestion/sso.py (your structural template for rate
limit + retry + idempotent rerun).

Your scope: fetch judgment HTML from CommonLII SG.

Source: http://www.commonlii.org/sg/cases/
The court structure: SGCA (Court of Appeal), SGHC (High Court),
SGDC (District Court), SGMC (Magistrate Court), SGSAC (Singapore
Special Appeal Court — rare). Each court has per-year listing pages.

Files you own:
- backend/data/ingestion/commonlii_sg.py (new)
- backend/ml/pipelines/ingest_commonlii_sg.py (new)
- backend/tests/fixtures/commonlii_sg/ (new — 1 listing page + 2
  judgment pages from different courts; SGCA + SGHC)
- Makefile: add `ingest-commonlii-sg` target + include in
  `ingest-all`

Files you must NOT touch:
- backend/data/parsers/commonlii_sg_parser.py (B2)
- backend/api/adapters/public/commonlii_sg.py (B4 finalises)
- backend/tests/test_commonlii_sg_*.py (B2/B3)

Requirements:
1. Same rate limit (5s per CommonliiSgAdapter.metadata.crawl_delay)
   + jitter as SSO.
2. Retry with exponential backoff.
3. Stable case_id derived from the canonical CommonLII URL.
4. Output schema (per row, JSONL):
   - case_id, citation (neutral form), court_code, year, case_no,
     decision_date (ISO), source_url, html_url, body_html (raw),
     body_plain (B2 will fill this).
5. Output path: vendor-data/sg_cases/judgments.jsonl.
6. CLI: `python -m data.ingestion.commonlii_sg --output ... [--court
   SGCA] [--year 2024] [--limit N] [--dry-run]`.

Tests (just for the fetcher behaviour, not parsing): mock httpx, verify
URL construction + rate-limit pacing + retry path.

Branch: feat/commonlii-sg-ingester. Commit:
`feat(commonlii): SG case judgment fetcher (advances #34)`.

Acceptance:
- Fixtures committed.
- Dry-run prints planned URLs.
- pytest passes.

Report back: which courts are in your fixture, any TOS observations
on CommonLII pages (look for crawl restrictions in robots.txt or
the page footer attribution requirement).
```

## B2: CommonLII judgment HTML parser

```text
You are working on issue #34 in the junas repo. Read AGENT-RUNBOOK.md
and backend/data/parsers/sso_parser.py for structural template.

WAIT until B1 has landed feat/commonlii-sg-ingester with at least 2
fixture judgment HTML files.

Your scope: parse a CommonLII SG judgment HTML page into a structured
record.

Files you own:
- backend/data/parsers/commonlii_sg_parser.py (new)
- backend/tests/test_commonlii_sg_parser.py (new)

Files you must NOT touch:
- backend/data/ingestion/commonlii_sg.py (B1)
- B3's jurisdiction-statement extractor module

CommonLII SG judgments are simple server-rendered HTML. The judgment
body is typically a sequence of paragraphs with paragraph numbers in
square brackets like [1] [2] [3]. Catchwords appear in italics near
the top.

Required output (extend the row B1 wrote with these fields):
- body_plain: str (full judgment text, paragraph markers preserved
  as " [N] " inline so the jurisdiction-statement extractor can
  attribute statements to paragraphs)
- catchwords: str
- judges: list[str]
- paragraphs: list[dict]  # [{"number": int, "text": str}]
- counsel: list[str] (optional, if reliably parseable)

Tests:
- Parse SGCA fixture → all fields populated.
- Parse SGHC fixture → likewise.
- Bracket paragraph numbering preserved.
- HTML edge cases (em-dashes, smart quotes, &nbsp;) normalised.

Branch + commit format: same as B1. Acceptance: pytest passes;
fixture round-trip yields a complete record.

Report back: paragraph extraction fidelity, anything the HTML
structure makes hard to extract.
```

## B3: Jurisdiction-statement regex extractor (load-bearing)

```text
You are working on issue #34 in the junas repo. **This task produces
the SGLB-07 gold labels** so it is the load-bearing piece. Read
AGENT-RUNBOOK.md, docs/sglb_specs/SGLB-07.md, and
docs/coverage-matrix.md §4.1 (mechanical extraction policy).

WAIT until B2 has landed the judgment parser so you have a structured
body_plain + paragraphs.

Your scope: detect explicit source-jurisdiction statements in SG
judgment bodies and emit them as `jurisdiction_statements` for
sglb_07 builder consumption.

Files you own:
- backend/data/parsers/jurisdiction_extractor.py (new)
- backend/tests/test_jurisdiction_extractor.py (new — DENSE tests;
  this is the methodology-critical piece)

Files you must NOT touch:
- backend/data/parsers/commonlii_sg_parser.py (B2) — call it, don't
  modify it.

Methodology constraint (READ CAREFULLY):

The SGLB-07 spec says the gold label is "derived from explicit court
statements about precedent applicability". You must extract these
mechanically. You may NOT classify "this case feels like UK
persuasive reasoning"; you must find a paragraph where the court
ITSELF says so. Examples of acceptable triggers:

- "applying the principle in [CASE], a decision of the [JURISDICTION] courts"
- "the [JURISDICTION] authority of [CASE] is persuasive"
- "this Court is bound by [CASE] of the Singapore Court of Appeal"
- "while [JURISDICTION] cases have considered this question..."

Build a regex pack (in jurisdiction_extractor.py) that matches these
phrasings. Each match should emit:
- label: one of sg_binding / uk_persuasive / au_persuasive /
  hk_persuasive / not_applicable
- quote: the matched sentence (or paragraph if the trigger
  context spans multiple sentences)
- paragraph: int (the [N] number from B2)

Output type: `list[JurisdictionStatement]`. Empty list if no
statement found. Multiple statements possible; SGLB-07 v0.1 builder
excludes multi-statement cases, but emit them anyway so v0.2 can use
them.

Tests (this is the heaviest test file in the PR):
- At least 12 hand-crafted synthetic paragraphs covering all 5
  labels.
- Negative tests: paragraphs that mention UK cases without
  explicit persuasive framing should NOT match.
- Negative tests: SG case names alone (e.g. "[2018] SGCA 14") should
  NOT match unless paired with a binding statement.
- Apply to the B1/B2 fixtures and assert the output is sensible
  (this is a smoke check — the gold labels are mechanical so we
  don't need to know the "right" answer ahead of time, only that
  the extractor produces output for the right paragraphs).

Update backend/data/ingestion/commonlii_sg.py to call the
jurisdiction_extractor and add `jurisdiction_statements` to each
JSONL row.

Branch + commit format: same as B1. Commit:
`feat(commonlii): jurisdiction-statement extractor for SGLB-07 gold
labels (advances #34)`.

Acceptance:
- Tests pass.
- The SGLB-07 builder, when pointed at vendor-data/sg_cases/
  judgments.jsonl, emits non-zero cases (`make build-sglb-07`).

Report back: regex coverage of each label class, any clearly missed
phrasings the regex pack should catch in v0.2, and which fixture
judgments triggered which labels.
```

## B4: CommonLII adapter contract + frontend wiring

```text
You are working on issue #34 in the junas repo. Read AGENT-RUNBOOK.md
and backend/api/adapters/public/sso.py.

WAIT until B1 has landed the basic ingester so the adapter's
fetch_all() / fetch_by_id() can delegate to it.

Your scope: align the CommonliiSgAdapter with the LegalSourceAdapter
contract; surface in legal-sources page.

Files you own:
- backend/api/adapters/public/commonlii_sg.py (existing stub;
  flesh out)
- backend/tests/test_adapters.py (add test_commonlii_sg_adapter)
- frontend/app/legal-sources/page.tsx (add CommonLII SG entry)

Files you must NOT touch:
- B1/B2/B3's files in data/ingestion + data/parsers.

Branch + commit: same as B1.

Report back: any contract divergence vs the JSONL schema agents
produced.
```

## NEW-SSO-EXPAND: SSO ingest beyond PDPA (closes GAP-04 partial)

```text
You are expanding SSO ingestion beyond PDPA to unblock SGLB-02
scaling + SGLB-06 data.

Read AGENT-RUNBOOK.md, GAPS-TO-REMEDY.md §GAP-04 + §GAP-13,
backend/data/ingestion/sso.py, docs/sglb_specs/SGLB-02.md +
docs/sglb_specs/SGLB-06.md, Makefile (existing `ingest-sso` target).

Goal: run SSO ingestion for EmA1968, ROC2021, and PC1871. Produce
JSONL output that the existing builders can consume.

Files you own:
- vendor-data/sso/EmA1968.jsonl (output)
- vendor-data/sso/ROC2021.jsonl (output)
- vendor-data/sso/PC1871.jsonl (output)
- backend/benchmark/datasets/sglb_02_statute_qa_full.yaml (NEW —
  full 500-target dataset; preserve sglb_02_statute_qa.yaml as the
  PDPA-only smoke for backward compat)
- backend/benchmark/datasets/sglb_06_roc_2021.yaml (NEW)
- docs/sglb_specs/SGLB-02.md (bump version + N once landed)
- docs/sglb_specs/SGLB-06.md (bump from code-shipped to
  0.1-shipped once landed)

Files you must NOT touch:
- backend/data/ingestion/sso.py (use as-is; if it has a bug, fix
  separately)

Process:
1. `make ingest-sso SSO_CODE=EmA1968` (cost: network only)
2. `make ingest-sso SSO_CODE=ROC2021`
3. `make ingest-sso SSO_CODE=PC1871`
4. Run the SGLB-02 builder against the combined JSONL.
5. Run the SGLB-06 builder against ROC2021.
6. Verify case counts approximately match the targets (SGLB-02: 500;
   SGLB-06: ~150).
7. Flip `benchmark_eligible=True` on SGLB-06 (per
   NEW-HONEST-LEADERBOARD's pattern).

Acceptance:
- Three JSONL outputs land.
- SGLB-02 dataset YAML is ~500 cases.
- SGLB-06 dataset YAML is ~150 cases and is benchmark-eligible.
- Existing PDPA-only SGLB-02 smoke remains unchanged for backward
  compat.

Branch: feat/sso-expand-non-pdpa.
Commit: `feat(sso): ingest EmA/ROC2021/PC1871 + expand SGLB-02 to
500 + enable SGLB-06 (closes GAP-04 partial)`.

Report back: actual case counts per source; any section the parser
struggled with; total network requests + duration.
```

## NEW-SGLB-04-PROD: SGLB-04 production set (closes #32 + GAP-13)

```text
You are expanding SGLB-04 from the 30-case smoke dataset to the
1000+ case production set (per the spec doc + issue #32).

Read AGENT-RUNBOOK.md, GAPS-TO-REMEDY.md §GAP-13,
docs/sglb_specs/SGLB-04.md, backend/benchmark/dataset_builders/
sglb_04.py, backend/api/services/sal_citation.py (the grammar).

Prerequisite: NEW-SAL-VALIDATION must land first. The production
set is only credible if the grammar has been validated against the
SAL Style Guide's published examples.

Goal: generate ≥1000 stratified test cases mechanically from the
grammar with the perturbation taxonomy (year_off, volume_off,
page_off, case_name_swap, court_swap, wholesale_fabrication,
composite) per the spec.

Files you own:
- backend/benchmark/datasets/sglb_04_citation_verify_full.yaml (NEW
  — production set; preserve the 30-case smoke as sglb_04_citation_
  verify_smoke.yaml for fast local testing)
- backend/benchmark/dataset_builders/sglb_04.py (extend with
  stratification by perturbation kind + N per stratum)
- docs/sglb_specs/SGLB-04.md (bump from "0.1-shipped (smoke)" to
  "0.1-shipped"; document per-error breakdown)

Files you must NOT touch:
- backend/api/services/sal_citation.py (no grammar changes here;
  any bugs surface as NEW-SAL-VALIDATION concerns)
- The smoke dataset (preserve for fast local testing)

Stratification:
- ≥100 cases per perturbation kind (year_off, volume_off, page_off,
  case_name_swap, court_swap, wholesale_fabrication, composite).
- ≥200 negative-cases (valid citations that should NOT be flagged).
- Train/dev/test split: 80/10/10 by hash of the case.

Acceptance:
- 1000+ cases in the production YAML.
- Per-error breakdown is reportable from the evaluator.
- pytest passes.

Branch: feat/sglb-04-production-set.
Commit: `feat(sglb-04): expand to 1000+ case production set (closes
#32; advances GAP-13)`.

Report back: per-stratum N; any perturbation kind that was hard to
generate; whether v0.2 should add more perturbation kinds.
```

---

# Tier 3 — Vendor-facing infrastructure

_Closes the "use us for your evals" workflow. Gated on Tier 1; runs in parallel with Tier 2._

## NEW-VENDOR-GUIDE: Vendor self-eval guide (closes GAP-14)

```text
You are writing GAP-14 closure: the vendor self-eval guide.

Read AGENT-RUNBOOK.md, GAPS-TO-REMEDY.md §GAP-14, backend/benchmark/
cli.py, backend/benchmark/receipt_schema.md (must exist post-
NEW-CI-RECEIPT), docs/normalisation-spec.md (must exist post-
NEW-NORM-SPEC), docs/methodology/contamination.md (must exist post-
NEW-CONTAM), docs/dispute-process.md (must exist post-
NEW-DISPUTE-PROCESS).

Prerequisites: NEW-CI-RECEIPT, NEW-CONTAM, NEW-NORM-SPEC, and
NEW-DISPUTE-PROCESS must all have landed. This is the consolidating
doc that ties them together for a vendor audience.

Goal: docs/vendor-self-eval-guide.md takes a SG legal-tech vendor's
ML engineer from zero to "I have receipts I can paste into a slide
deck" in <10 minutes.

Files you own:
- docs/vendor-self-eval-guide.md (NEW)
- docs/vendor-self-eval-guide/sample-receipt.json (NEW —
  walkthrough fixture)
- docs/vendor-self-eval-guide/sample-leaderboard-row.md (NEW —
  what the published row looks like for the vendor's model)

Files you must NOT touch:
- backend/* (this is a doc-only prompt).

Guide structure:
1. Who this is for (SG legal-tech vendors / LLM-team engineers /
   academic researchers).
2. Install (`pip install -e .` or equivalent).
3. Configure your provider (BYOK: Anthropic / OpenAI / Google /
   Ollama).
4. Select tasks. Note v0.1 eligible: SGLB-01, SGLB-02, SGLB-04,
   SGLB-08. SGLB-05/06/07 are code-shipped, data pending.
5. Run with `--strict` mode (rejects weak evaluators).
6. Read the receipt: walk through the sample receipt's CI fields,
   contamination summary, prompt_sha.
7. Submit (optional): how to add your model to the leaderboard.
8. If you disagree with a label: link to docs/dispute-process.md.

Acceptance:
- A vendor's ML engineer can follow the guide cold.
- Sample receipt is accurate and current.
- Cross-references to the methodology docs work.

Branch: docs/vendor-self-eval-guide.
Commit: `docs(vendor): self-eval guide for SG legal-tech vendors
(closes GAP-14)`.

Report back: which step is most likely to trip a vendor; what they
ask in office hours.
```

## NEW-LIB-PACKAGING: Extract reusable components into sub-package (closes GAP-15)

```text
You are implementing GAP-15 closure: extract reusable components
into an installable sub-package so SG legal-tech engineers can
`pip install` parts of the stack.

Read AGENT-RUNBOOK.md, GAPS-TO-REMEDY.md §GAP-15, backend/api/
services/sal_citation.py, backend/benchmark/evaluators.py:520-536
(section normaliser), backend/api/adapters/public/base.py
(LegalSourceAdapter protocol).

Goal: a sub-package (working name: `sglb-tools`) installable via
PyPI containing the SAL citation grammar, citation/statute
normalisers, and the adapter base interface. Same licence as the
main repo (decided in SOLO-10).

Files you own:
- packages/sglb-tools/ (NEW directory at repo root)
- packages/sglb-tools/pyproject.toml (NEW — independent build config)
- packages/sglb-tools/sglb_tools/__init__.py
- packages/sglb-tools/sglb_tools/citation.py (re-export of
  sal_citation; module path is rewritten so the consumer sees
  `from sglb_tools.citation import validate_citation`)
- packages/sglb-tools/sglb_tools/normalisation.py (extract from
  benchmark/evaluators.py:520-536)
- packages/sglb-tools/sglb_tools/adapters/base.py (extract the
  LegalSourceAdapter protocol)
- packages/sglb-tools/README.md (NEW — usage examples for engineers)
- packages/sglb-tools/tests/ (mirror the relevant tests)
- backend/api/services/sal_citation.py (replace implementation with
  re-export from sglb_tools.citation; backward-compat)
- backend/benchmark/evaluators.py (use sglb_tools.normalisation;
  backward-compat)

Files you must NOT touch:
- Any dataset YAML.
- The benchmark cli — it continues to work unchanged.

Constraints:
- No breaking changes to the main repo's import paths.
- Sub-package is namespace-clean (only what's safe to expose as a
  public API).
- Tests in the sub-package run independently of the main repo.

Acceptance:
- `cd packages/sglb-tools && pip install -e . && pytest` works.
- Main repo imports continue to work.
- A consumer can `from sglb_tools.citation import validate_citation`
  in their own project after installing.

Branch: feat/sglb-tools-package.
Commit: `feat(packaging): extract sglb-tools sub-package (closes
GAP-15)`.

Report back: PyPI publish path; any service that wanted to be in
the package but couldn't be cleanly extracted (those go in a v0.2
follow-up).
```

## NEW-INDEPENDENT-REPRO: Outreach kit for institutional reproduction (closes GAP-12)

```text
You are implementing GAP-12 closure: outreach kit + technical
contract for an institutional partner to run the benchmark
independently.

Read AGENT-RUNBOOK.md, GAPS-TO-REMEDY.md §GAP-12, README2.md.

This is a docs+outreach prompt; no code.

Goal: produce a kit that lets SMU SOLID, NUS TRAIL, or SAL data
services run the suite, record the receipts, and publish them as an
"independent reproduction" alongside ours.

Files you own:
- docs/outreach/independent-reproduction-kit.md (NEW)
- docs/outreach/cover-letter-template.md (NEW — short letter to
  attach to an email)
- docs/outreach/three-targets.md (NEW — short briefs for SMU SOLID
  / NUS TRAIL / SAL: who they are, what they care about, why
  reproducing this benchmark serves their mandate, what we ask)

Files you must NOT touch:
- backend/* (this is outreach-only).

Kit contents:
1. Background (2 paragraphs).
2. What we're asking for: run the v0.1 benchmark against the
   institution's model of choice (or a frontier model); publish
   the receipt + CI + contamination summary to runs/
   external/<institution>/.
3. Technical contract: install, run command, receipt format pointer
   (NEW-VENDOR-GUIDE).
4. What they get: co-authorship on the v0.2 preprint (if substantive
   contribution); link from leaderboard; visibility.
5. Compute estimate: token cost + wall-time per task.
6. Timeline: 4-6 weeks from outreach to published receipt.

Acceptance:
- Three personalised outreach briefs.
- Kit is sendable as a single PDF or markdown bundle.

Branch: docs/independent-reproduction-kit.
Commit: `docs(outreach): independent reproduction kit + three-target
briefs (closes GAP-12)`.

Report back: any obstacle that would make the institutional partner
say no (institutional MOU? data-handling concerns?); whether the
v0.2 timeline aligns with their academic year.
```

# Batch C — Frontend Audit Fixes, 4 parallel agents

**Goal:** address the critical findings from `docs/audit/00_EXECUTIVE_AUDIT.md`
that remain unfixed. These four areas have **non-overlapping file targets** so
they can run in parallel without rebase pain.

## C1: GET → POST on sensitive textareas

```text
You are addressing the audit finding #2 in docs/audit/00_EXECUTIVE_AUDIT.md
(sensitive legal text submitted via URL query params). Read
AGENT-RUNBOOK.md first.

Current state (verified 2026-06-04): three pages still use
`<form method="get">` to submit user-pasted legal text:
- frontend/app/research/page.tsx:151
- frontend/app/statutes/page.tsx:67
- frontend/app/glossary/page.tsx:71

Privacy implications: pasted contract text / case facts end up in
the user's browser history, server access logs, and shareable URLs.
Unacceptable for a legal tool.

Your scope: convert these three forms to POST with an in-memory state
handler (no URL params), preserve the existing UX (results render
inline below the form).

Files you own:
- frontend/app/research/page.tsx
- frontend/app/statutes/page.tsx
- frontend/app/glossary/page.tsx

Files you must NOT touch:
- frontend/app/contracts/page.tsx (already fixed earlier; verify
  it's clean)
- frontend/app/search/page.tsx (likewise)
- frontend/app/ner/page.tsx (likewise)
- frontend/components/* (C2 owns CommandPalette)
- frontend/lib/api-* (C3 owns)

Implementation: use a client component with `useState` for the
textarea + a button that calls the backend via the existing
`api-client.ts`. Don't introduce SWR / React Query if it's not
already present — this is a fix, not a rearchitecture.

Tests: write a Playwright (or React Testing Library, whichever is
already in the repo) test for at least one of the three pages
asserting the textarea content does NOT appear in window.location
after submit.

Branch: fix/frontend-get-to-post-textareas.
Commit format: `fix(frontend): switch sensitive textareas from GET to
POST (audit finding #2)`. Co-Authored-By trailer.

Acceptance: the three pages no longer post via GET; `npm run build`
in frontend/ succeeds; existing pages still render the result inline.

Report back: any UX regressions, any backend endpoint that didn't
accept POST (those are router bugs to file separately).
```

## C2: Command palette dead links

```text
You are addressing audit findings #3 + #4 in docs/audit/00_EXECUTIVE_AUDIT.md
(command palette has broken nav for Home, commands listed but not
implemented). Read AGENT-RUNBOOK.md.

Files you own:
- frontend/components/chat/CommandPalette.tsx
- frontend/components/chat/CommandSuggestions.tsx
- frontend/lib/commands/command-handler.ts

Files you must NOT touch:
- frontend/app/* (C1, C3, C4 own pages)
- frontend/lib/api-* (C3 owns)

Concrete bugs:
1. `nav-home` resolves to `/home` which is not a route (the home
   route is `/`). Fix the mapping.
2. CommandSuggestions advertises commands not implemented in
   command-handler.ts. Audit the suggestion list against the
   handler's switch; either implement the missing ones or remove
   them from the suggestion list (prefer remove — easier to
   re-add when needed).

Tests: add a test that asserts every entry in CommandSuggestions
maps to an existing case in command-handler.ts. Prevent regression.

Branch: fix/command-palette-deadlinks.
Commit format: `fix(frontend): repair command palette dead links
(audit findings #3, #4)`.

Acceptance: no command in CommandSuggestions silently no-ops; nav
links resolve to real routes.

Report back: which commands you removed vs implemented, and any
copy-paste residue you noticed (the chat command system looks
like it accreted in layers).
```

## C3: Consolidate frontend data access

```text
You are addressing audit finding #5 in docs/audit/00_EXECUTIVE_AUDIT.md
(duplicated API wrappers + direct fetch in pages). Read
AGENT-RUNBOOK.md.

Files you own:
- frontend/lib/api-client.ts (browser-side wrapper)
- frontend/lib/api-server.ts (server-side wrapper)
- All frontend/app/**/page.tsx files that currently call `fetch`
  directly (audit lists clauses, templates, chat, compliance)

Files you must NOT touch:
- frontend/components/chat/CommandPalette.tsx (C2)
- frontend/app/{research,statutes,glossary}/page.tsx (C1)

Goal: a single typed API surface. There should be exactly one place
to add an endpoint. The split between api-client and api-server is
fine IF the contract is identical — likely the server-side wrapper
is for SSR/RSC and the client-side is for browser. If so, document
that boundary in a comment block at the top of each file.

Audit your finding list:
- frontend/app/clauses/page.tsx:14
- frontend/app/templates/page.tsx:14
- frontend/app/chat/page.tsx:126
- frontend/app/compliance/page.tsx:18

Replace each direct `fetch(...)` with a call to the unified API
client. Keep the network surface the same.

Tests: existing tests must still pass; if the test suite mocks
fetch globally, you'll need to update the mocks to mock the API
client instead.

Branch: refactor/frontend-api-consolidation.
Commit format: `refactor(frontend): consolidate API data access via
api-client (audit finding #5)`.

Acceptance: `grep -rn "fetch(" frontend/app/ | grep -v node_modules`
returns only fetch calls that go through the unified client; the
build succeeds; runtime behaviour unchanged.

Report back: any backend endpoints that had inconsistent
request/response shapes between callers.
```

## C4: Sanitize dangerouslySetInnerHTML

```text
You are addressing audit finding #7 in docs/audit/00_EXECUTIVE_AUDIT.md
(unsafe HTML rendering paths). Read AGENT-RUNBOOK.md.

DOMPurify is already in package.json (audit confirmed). Use it.

Files you own:
- frontend/app/statutes/section/[number]/page.tsx (line 47:
  `dangerouslySetInnerHTML={{ __html: section.text_html }}` — this
  is user-influenceable through what we ingest from SSO; sanitise.)
- frontend/app/glossary/[phrase]/page.tsx (line 60: same risk)

Files you must NOT touch:
- frontend/app/layout.tsx (theme-injection script is known-safe
  inline JS; the audit flagged it for CSP review, not sanitisation;
  out of scope for this fix).
- frontend/components/* (C2 owns)

Implementation:

1. Wrap each `__html` source in a DOMPurify.sanitize() call. Default
   config is fine; if the existing HTML uses any inline event
   handlers (it shouldn't from SSO/glossary source), they will be
   stripped — that's the right behaviour.
2. Add a comment block above each sanitise call referencing this
   audit finding so future contributors don't undo it.

Tests:
- Add a test (RTL or similar) that passes hostile HTML (a
  <script>alert(1)</script> injection or onerror= attribute) through
  the rendering pipeline and asserts the script does not execute.
- If the test runner doesn't have a DOM environment configured for
  the relevant test, add jsdom.

Branch: fix/frontend-html-sanitisation.
Commit format: `fix(frontend): sanitise dangerouslySetInnerHTML
sources (audit finding #7)`.

Acceptance: tests pass; XSS payload blocked; existing valid HTML
still renders correctly.

Report back: any HTML features sanitisation accidentally strips
that we relied on.
```

## SOLO-3: Auth gate for hosted /benchmarks demo (#79)

```text
You are implementing issue #79 in the junas repo: launch blocker.

The /benchmarks route in the frontend is publicly visible. Before
the user puts a hosted demo behind a public URL, it needs an auth
gate so we don't expose the harness to anonymous fuzzers.

Read AGENT-RUNBOOK.md and backend/api/security.py (the existing
auth shape).

Decision required from the user before you start: which auth
mechanism?

Option A: simple shared-secret header (existing API_KEYS env
list; cheapest).
Option B: GitHub OAuth (better UX for researchers, more setup).
Option C: a basic auth proxy at the deploy edge (Vercel password
protection; zero code change).

If the user doesn't specify, default to Option A + add a clearly
visible comment that this is the launch-day minimum and Option C
(Vercel password) is recommended for the hosted demo specifically.

Files in scope (Option A):
- backend/api/security.py (likely already supports this; just
  enforce on /benchmarks routes)
- frontend/app/benchmarks/page.tsx (gate the page; on 401, render
  a "this demo requires an access key" message with the env-var
  name the user should set)

Branch: feat/auth-gate-benchmarks.
Commit: `feat(auth): gate /benchmarks behind shared secret (closes
#79)`.

Acceptance: hitting /benchmarks without the header returns 401; with
it returns 200; the existing CLI eval path is unaffected (only the
HTTP surface gates).

Report back: which option you chose, any auth boilerplate the
existing codebase has that we should consolidate around.
```

## SOLO-1: Retrieval R1 + R2 audit fixes (#75)

```text
You are fixing issue #75 in the junas repo. Read AGENT-RUNBOOK.md +
docs/retrieval-audit.md.

#75 references two audit findings from retrieval-audit.md:
- R1: dedupe results by legis_id (currently can return duplicate
  rows for the same statute across different revision dates)
- R2: replace `from`/`size` pagination with `search_after` cursor
  (avoid the 10k result-window cliff)

Files likely in scope:
- backend/api/services/retrieval_orchestrator.py
- backend/api/services/case_retrieval.py
- backend/api/services/statute_lookup.py
- backend/api/indices.py
- backend/tests/test_indices.py

Read docs/retrieval-audit.md §R1 + §R2 for the exact remediation
shape. Implement; add tests; commit on a feature branch.

Branch: fix/retrieval-r1-r2.
Acceptance: pytest passes; the audit doc's "before/after" examples
work.

Report back the API surface change (if any) so frontend can be
updated.
```

## SOLO-2: Receipt drill-down endpoint (#78)

```text
You are implementing issue #78 in the junas repo: a per-case
results endpoint at `/benchmarks/runs/{run_id}` that returns the
RunSummary as JSON plus per-case details (input, expected, actual,
per-evaluator score).

Read AGENT-RUNBOOK.md and backend/api/routers/benchmarks.py for the
existing endpoint shape.

Files in scope:
- backend/api/routers/benchmarks.py (add the new route)
- backend/api/models/* (if a Pydantic model is needed for the
  response)
- backend/tests/test_benchmarks_router.py (add a test that creates
  a run, persists a receipt, retrieves it via the endpoint)
- frontend/app/benchmarks/runs/[runId]/page.tsx (NEW — server
  component that fetches the endpoint and renders a sortable table)

Storage: receipts currently land at `runs/baselines/<provider>/...`.
For the API to find one by run_id, define the run_id format
(e.g. `<provider>__<task>__<unixtime>` derived from the receipt
filename) and have the endpoint glob the directory. Don't introduce
a database for this.

Branch: feat/receipt-drilldown.
Commit: `feat(benchmarks): drill-down endpoint + UI for run receipts
(closes #78)`.

Acceptance: the backend endpoint returns 200 with the expected shape
for an existing receipt; the frontend page renders.

Report back: any UX concerns (large per-case tables for 200+ case
runs need pagination — call it out if so).
```

## SOLO-5: Synthetic candidates CI guard (#76)

```text
You are implementing issue #76 in the junas repo: prevent synthetic
candidates from being accidentally promoted to the reviewed corpus.

Read AGENT-RUNBOOK.md, backend/benchmark/synthetic/README.md, and
backend/benchmark/synthetic/promoter.py.

Files in scope:
- .github/workflows/ci.yml (add a step that fails if any
  *_candidates/*.yaml row has review_status != "approved" but is
  also referenced by a reviewed-tier YAML)
- backend/benchmark/synthetic/validator.py (new module that
  the CI step calls)
- docs/synthetic-policy.md (new; document the gate)

Acceptance: a deliberate "promote a pending candidate" PR fails CI.
A correctly-promoted candidate passes.

Branch: ci/synthetic-promotion-guard.
Commit: `ci(synthetic): block accidental promotion of pending
candidates (closes #76)`.

Report back: any synth-pipeline edge cases.
```

## SOLO-6: Synthetic-tier API marking (#77)

```text
You are implementing issue #77 in the junas repo: surface the
synthetic-tier flag in API responses and receipt metadata so the
frontend can label results as "synthetic data" vs "regulator data".

Read AGENT-RUNBOOK.md and backend/api/routers/benchmarks.py.

Files in scope:
- backend/api/routers/benchmarks.py (add data_tier to the response
  shape; the RunSummary already carries it)
- frontend/app/benchmarks/page.tsx (display the tier as a badge per
  task)
- backend/tests/test_benchmarks_router.py (assert the new field is
  present)

Branch: feat/data-tier-api-marking.
Commit: `feat(benchmarks): expose data_tier in API + UI (closes #77)`.

Acceptance: synthetic tasks (SGLB-08/12/15) render with a "synthetic"
badge; regulator tasks (SGLB-01/02/04/05/06/07) render with a
"regulator" badge.

Report back: any task whose data_tier is ambiguous.
```

## SOLO-4: Cold-start guide (#74)

```text
You are implementing issue #74 in the junas repo: a cold-start guide
showing a new agent how to register an LLM-backed task + run the
first real baseline.

Read AGENT-RUNBOOK.md, backend/benchmark/LLM_RUNNER.md, CONTRIBUTING.md.

Files you own:
- docs/cold-start-guide.md (new)

Content: a 200-line walkthrough that takes the agent from
"I am dropped into this repo" to "I have produced a receipt JSON
with provenance fields for SGLB-04 via gpt-4o-mini". Use the
existing SGLB-04 smoke dataset; mock the LLM client first; then show
how to swap in a real provider.

Branch: docs/cold-start-guide.
Commit: `docs(#74): cold-start guide for new agent + first baseline`.

Acceptance: another agent following the guide produces a working
receipt JSON without asking the user any questions.

Report back: any step that surprised you.
```

---

# Tier 4 — Launch

_arXiv preprint + launch assets. Gated on Tier 1 (methodology) + Tier 2 (data) + Tier 3 (vendor infra) closing._

## SOLO-8: arXiv preprint draft (#37)

```text
You are starting issue #37 in the junas repo: SG-LegalBench preprint
draft. Read AGENT-RUNBOOK.md, docs/coverage-matrix.md,
GAPS-TO-REMEDY.md, and all of docs/sglb_specs/SGLB-NN.md.

Scope: produce the preprint outline + draft §§1-3 (Introduction,
Methodology, Tasks). Leave §§4-5 (Results, Limitations) as
TODO-blocks gated on NEW-BATCH-D baselines.

Files you own:
- docs/preprint/sglb-preprint.tex (new; LaTeX, NLLP/EMNLP-friendly
  template) OR docs/preprint/sglb-preprint.md (markdown if LaTeX is
  too heavyweight for v0 — the user can convert later)
- docs/preprint/figures/ (gitignored placeholders)

Constraints (READ CAREFULLY):
- The methodology section MUST lead with: "We make no legal
  interpretive claims. We mechanically reformulate published
  regulator and court outputs as evaluation tasks." This is
  load-bearing for the doc's defensibility (pivot §11).
- No "beats GPT-X" framing anywhere (coverage-matrix §5).
- §1 leads with the vendor-defensibility narrative: contamination
  analysis, bootstrap CIs, published dispute process. NOT "frontier
  models fail SG legal reasoning" — that framing is replaced.
- Each task gets its own subsection in §3, citing source +
  extraction rule + scoring + limitations from the spec doc.
- Related work: cite LegalBench, LexGLUE, LawBench, SARA, CUAD,
  IFEval, FActScore, HaluEval per coverage-matrix §9.

Target venue: NLLP workshop @ EMNLP 2026 (deadlines typically
July-August 2026).

Branch: docs/preprint-outline.
Commit: `docs(#37): SG-LegalBench preprint outline + §§1-3 draft`.

Acceptance: a reviewer reading the draft can answer "what does this
benchmark test, on what data, how is it scored, and what's
explicitly NOT tested" without asking.

Report back: which sections you couldn't draft yet (it should be
just §§4-5), any prior-work claims you'd like a second pair of eyes
on, any spec-doc inconsistencies you noticed while writing.
```

# Batch E — Launch Assets (#39), 4 parallel agents

**Goal:** produce ship-ready launch assets so the moment NEW-BATCH-D
lands, the launch can fire same-day.

**Coordination contract:** branch `feat/launch-assets-v0.1`. All four
agents commit to the same branch; user reviews each commit
independently. Where copy depends on baseline numbers, agents leave
`<PLACEHOLDER>` tokens that a follow-up PR fills.

## E1: HN Show HN post + landing-page hook

```text
You are working on issue #39 (launch assets) in the junas repo. Read
AGENT-RUNBOOK.md, README2.md, GAPS-TO-REMEDY.md, docs/coverage-matrix.md
§5 (anti-snake-oil checklist), and the existing landing page at
frontend/app/page.tsx.

Goal: HN Show HN submission draft + the landing-page <h1> hook that
aligns with the recommended headline variant.

Files you own:
- docs/launch/hn-show-hn.md (new — the post draft)
- docs/launch/headline-options.md (new — 3 candidate headlines with
  evidentiary basis and which require baseline numbers)
- frontend/app/page.tsx (only the <h1>; align with your recommended
  variant in headline-options.md)

Files you must NOT touch:
- docs/launch/twitter-thread.md (E2)
- docs/launch/linkedin-post.md (E3)
- docs/launch/outreach-templates.md (E3)
- docs/launch/press-kit.md (E4)
- docs/launch/press-emails.md (E4)

Constraints (read coverage-matrix §5 first):
- No "beats GPT-X" framing. Use the substitute phrasings.
- Lead with vendor-defensibility methodology: "first SG legal
  benchmark with contamination analysis + bootstrap CIs + published
  dispute process". NOT "frontier models fail" (that's only one
  optional sub-claim, and it's gated on NEW-BATCH-D).
- The SG-uniqueness gap is the secondary hook (LegalBench=US,
  LexGLUE=US+EU, LawBench=CN; SG is a clean gap).
- "We make no legal interpretive claims" must appear.
- 3 headline candidates: methodology variant (no number needed),
  capability-gap variant (no number needed), surprising-number
  variant (gated on NEW-BATCH-D). Mark which need baselines.

Post structure (suggested):
- Title (≤80 chars)
- Opening hook (2 sentences)
- What it is (3 bullets, link to repo + spec dir)
- What it isn't (1-2 bullets, defuses scope-overclaim)
- Reproducibility (1 bullet — `make eval` and you get the same
  numbers; receipts include CIs + contamination flags)
- Links section

Branch: feat/launch-assets-v0.1.
Commit: `docs(launch): HN Show HN draft + headline candidates
(advances #39)`. Co-Authored-By trailer.

Acceptance: 3 headline variants + 1 ready-to-paste HN draft + landing
<h1> aligned. Each <PLACEHOLDER> token is documented.

Report back: which headline you recommend and why; any claim you
couldn't substantiate without baselines.
```

## E2: Twitter thread

```text
You are working on issue #39 in the junas repo. Read AGENT-RUNBOOK.md
and the SGLB spec docs under docs/sglb_specs/.

Goal: 8-12 tweet thread for launch day. Mark every `<PLACEHOLDER>`
that depends on NEW-BATCH-D baseline numbers.

Files you own:
- docs/launch/twitter-thread.md (new)

Files you must NOT touch:
- E1/E3/E4's files.

Thread structure:
1. Hook tweet — why this matters (no number needed)
2. The gap (LegalBench=US, LexGLUE=US+EU, LawBench=CN, gap=SG)
3. Methodology — mechanical extraction; contamination probe;
   bootstrap CIs; dispute process (the credibility substitute)
4-8. One surprising finding per tweet (each gated on NEW-BATCH-D;
   mark <PLACEHOLDER>)
9. Reproducibility — "anyone can rerun: make eval && cat receipt"
10. Where to learn more (links)

Constraints:
- No emojis (user's CLAUDE.md disallows them).
- No "beats GPT-X" framing.
- Each tweet ≤270 chars (Twitter limit minus padding).
- Numbered "n/N" prefixes for thread readability.

Branch + commit: same as E1.
Acceptance: 8-12 numbered tweets, ≤270 chars each.
Report back: any claim you couldn't make in ≤270 chars; whether the
thread reads cohesively without baselines (i.e. is the no-numbers
variant viable).
```

## E3: LinkedIn SG legal-tech post + outreach templates

```text
You are working on issue #39 in the junas repo. Read AGENT-RUNBOOK.md
and README2.md.

Goal: LinkedIn launch post + 6 DM templates targeted at SG
legal-tech institutions.

Files you own:
- docs/launch/linkedin-post.md (the post)
- docs/launch/outreach-templates.md (DM templates)

Files you must NOT touch:
- E1/E2/E4's files.

Targets for DM templates (one each):
1. SMU SOLID team (Singapore Open Legal Informatics Database project)
2. NUS TRAIL (Tech and Responsible AI lab)
3. SAL (Singapore Academy of Law) tech committee
4. INTELLLEX (SG legal-tech company)
5. Lupl (SG legal-tech company)
6. LawTech.Asia (publication)

Constraints:
- LinkedIn post 200-400 words. Frame: "I built X because Y was
  missing". Cite the LegalBench/LexGLUE/LawBench gap.
- DMs ≤150 words each. State who they are + what we built + the
  one-sentence ask. NO name-drops we can't substantiate (the user has
  no prior contact unless evidence is in repo history).
- Treat SAL as institutional (phone/email better than DM); flag this
  in your report.
- The institutional DMs (SMU SOLID, NUS TRAIL, SAL) should reference
  NEW-INDEPENDENT-REPRO as the ask if it has landed.

Branch + commit: same as E1.
Acceptance: 1 post + 6 personalised DMs.
Report back: which targets warrant a phone call vs DM.
```

## E4: Press kit + journalist outreach

```text
You are working on issue #39 in the junas repo. Read AGENT-RUNBOOK.md,
README2.md, and (for tone reference) any coverage Mike OSS got from
the same outlets.

Goal: press kit + 5 personalised pitch emails.

Files you own:
- docs/launch/press-kit.md (1-page background + key facts + quote
  block + contact)
- docs/launch/press-emails.md (5 pitches: LawTech.Asia, Artificial
  Lawyer, Legal IT Insider, Legal Futures, Straits Times Tech)

Files you must NOT touch:
- E1/E2/E3's files.

Press kit must include:
- 2-paragraph background suitable for direct quotation
- Key facts (4 v0.1-eligible tasks, public-domain sources, mechanical
  labels, contamination-aware methodology, multi-model baselines with
  CIs and contamination flags)
- 50-80 word attributable quote from the solo dev (Gabriel) about the
  SG-uniqueness gap + vendor-grade methodology
- Where to find screenshots / demo GIF (placeholder paths)
- Contact (TBD; surface to user)

Each pitch email ≤200 words. Differentiate from Mike OSS coverage
angle (benchmark, not product; SG, not generic; methodology-rigorous,
not just shipping).

Branch + commit: same as E1.
Acceptance: 1 press kit + 5 personalised pitches.
Report back: which outlets covered Mike OSS recently and how we
differentiate.
```

---

# Tier 5 — Copilot + v0.2

_Post-launch. Reference copilot polish + v0.2 task expansion. Gated on Tier 4 (launch)._

# Batch G — v0.2 Task Wave 1 (#50, #54, #55, #57), 4 parallel agents

**Goal:** ship 4 new SGLB v0.2 tasks (SGLB-09, SGLB-13, SGLB-14,
SGLB-16). These four are NOT blocked on a shared data source so they
parallelise cleanly.

**Coordination contract:** branch `feat/sglb-v0.2-wave-1`. Each agent
owns its own dataset_builder + task file. Touchpoints with
conflict-risk: `backend/benchmark/tasks/__init__.py` (each appends one
import) and `backend/benchmark/llm_runner.py::PROMPT_BUILDERS` (each
appends one entry). Resolve via simple rebase; ordering G1 < G2 < G3
< G4 by issue number works.

**Methodology constraint for LLM-judge tasks:** any v0.2 task that
uses LLM-judges (G1 SGLB-09 explicitly) MUST follow the same κ
discipline as SGLB-08 — ≥3-judge ensemble, pairwise κ reported,
human-validated holdout per coverage-matrix §4.1. Single-judge
"acceptable with disclosure" is v0.1 smoke posture only; v0.2 is
post-launch and held to higher standard.

## G1: SGLB-09 Summary-Faithfulness

```text
You are working on issue #50 (SGLB-09 Summary-Faithfulness).

Read AGENT-RUNBOOK.md, docs/sglb_specs/SGLB-09.md, CONTRIBUTING.md
"Adding a new task", GAPS-TO-REMEDY.md §GAP-07/08, and the FActScore
paper (Min et al., EMNLP 2023, https://arxiv.org/abs/2305.14251).

Files you own:
- backend/benchmark/dataset_builders/sglb_09.py
- backend/benchmark/tasks/sglb_09.py
- backend/benchmark/llm_runner.py (+ sglb_09 prompt builder)
- backend/benchmark/tasks/__init__.py (+ register)
- backend/benchmark/evaluators.py (add AtomicFactScore if not
  present)
- backend/benchmark/datasets/sglb_09_summary_faithfulness.yaml
- backend/data/benchmarks/sglb_09_summary_faithfulness/{train,dev,
  test}.jsonl
- docs/sglb_specs/SGLB-09.md (bump version)
- backend/tests/test_sglb_09_task.py
- Makefile: + build-sglb-09 target

Files you must NOT touch:
- G2/G3/G4's sglb_NN files.

Task contract:
- Input: `{"source_text": str, "summary": str}` — source from a PDPC
  decision; summary is what the model evaluates.
- Output: JSON object `{"atomic_facts": [{"fact": str, "supported":
  bool}]}`.
- Score: precision over `supported=true` facts that actually appear
  in source_text (deterministic substring or entailment check).

Methodology contract (v0.2, NOT v0.1 smoke posture):
- ≥3-judge ensemble for label generation (Anthropic + Gemini +
  Azure gpt-5), matching SOLO-17's pattern for SGLB-08.
- Pairwise κ + Fleiss' κ reported.
- 20-case human-validated holdout (smaller than SOLO-18's 40-case
  but same discipline).

Smoke seed (v0.2 launch): ~20 cases built from existing PDPC JSONL,
labelled via the 3-judge ensemble. Generate 3 candidate summaries
per source (faithful / mild hallucination / wholesale fabrication)
via an LLM call.

Branch: feat/sglb-v0.2-wave-1.
Commit: `feat(sglb-09): Summary-Faithfulness task (closes #50)`.

Acceptance: 20-case smoke; oracle scores 1.0; tests pass; κ
published.
Report back: κ values; how to scale to N=200 in v0.2.1.
```

## G2: SGLB-13 Counterfactual-Outcome

```text
You are working on issue #54 (SGLB-13 Counterfactual-Outcome).

This task PIGGYBACKS on the SGLB-01 PDPC corpus — no new ingest.

Read AGENT-RUNBOOK.md, docs/sglb_specs/SGLB-13.md,
backend/data/ingestion/pdpc.py,
backend/benchmark/dataset_builders/sglb_05.py (similar pattern).

Files you own:
- backend/benchmark/dataset_builders/sglb_13.py
- backend/benchmark/tasks/sglb_13.py
- backend/benchmark/llm_runner.py (+ prompt builder)
- backend/benchmark/tasks/__init__.py (+ register)
- backend/benchmark/datasets/sglb_13_counterfactual.yaml
- backend/data/benchmarks/sglb_13_counterfactual/{train,dev,test}.jsonl
- docs/sglb_specs/SGLB-13.md (bump version)
- backend/tests/test_sglb_13_task.py
- Makefile: + build-sglb-13

Files you must NOT touch:
- G1/G3/G4's sglb_NN files.

Methodology constraint (READ CAREFULLY):
The gold label here is inherently judgment-adjacent. To stay in line
with coverage-matrix §4.1, ONLY generate perturbations where a
deterministic rule clearly applies. Example: remove the "DPO appointed"
fact from a case that explicitly states "the appointment of a DPO was
considered a mitigating factor". The gold label "outcome changes" /
"outcome unchanged" derives from the PDPC's own published reasoning
about whether that fact was material.

If you find your perturbation generation requires legal judgment
beyond what PDPC has already published, STOP, document the case, and
exclude it.

Task contract:
- Input: `{"fact_pattern": str, "perturbation": str}`
- Output: `{"outcome_changes": bool}`
- Score: accuracy

Branch: feat/sglb-v0.2-wave-1.
Commit: `feat(sglb-13): Counterfactual-Outcome on PDPC perturbations
(closes #54)`.

Acceptance: deterministic perturbation rule documented; tests pass.
Report back: how many PDPC decisions fit the rule; legal-judgment
risk profile.
```

## G3: SGLB-14 Statutory-Entailment

```text
You are working on issue #55 (SGLB-14 Statutory-Entailment).

BLOCKED on SOLO-9 (PDPC Advisory Guidelines scraper, #60). If
SOLO-9 has not landed, you ship code-only; data comes later.

Read AGENT-RUNBOOK.md, docs/sglb_specs/SGLB-14.md, the SARA paper
(Holzenberger et al., 2020, https://arxiv.org/abs/2005.05257),
backend/benchmark/dataset_builders/sglb_02.py.

Files you own:
- backend/benchmark/dataset_builders/sglb_14.py
- backend/benchmark/tasks/sglb_14.py
- backend/benchmark/llm_runner.py (+ prompt builder)
- backend/benchmark/tasks/__init__.py (+ register)
- docs/sglb_specs/SGLB-14.md (bump version)
- backend/tests/test_sglb_14_task.py
- Makefile: + build-sglb-14

Files you must NOT touch:
- G1/G2/G4's sglb_NN files.

Task contract:
- Input: `{"statute_section": str, "conduct": str}`
- Output: JSON object `{"entailment": "contravenes" | "complies" |
  "indeterminate"}`
- Score: exact_match over the 3-label space

Mechanical extraction: PDPC Advisory Guidelines contain worked
examples ("the conduct described contravenes section X"). The gold
label is verbatim from the regulator's framing; we never infer it.

If SOLO-9 has landed: 50-100 case smoke seed.
If SOLO-9 has not landed: code-shipped with a fixture-based smoke
test; spec marked "0.1-code-shipped; data pending #60".

Branch: feat/sglb-v0.2-wave-1.
Commit: `feat(sglb-14): Statutory-Entailment task (closes #55)`.

Acceptance: code-shipped or smoke depending on #60 status; tests pass.
Report back: entailment-pattern coverage of the PDPC Advisory
Guidelines.
```

## G4: SGLB-16 Review-Redflag-Recall

```text
You are working on issue #57 (SGLB-16 Review-Redflag-Recall).

This task PIGGYBACKS on the existing SG clause/template library at
backend/api/services/{clause_service,template_service}.py.

Read AGENT-RUNBOOK.md, docs/sglb_specs/SGLB-16.md, CUAD paper
(Hendrycks et al., NeurIPS 2021).

Files you own:
- backend/benchmark/dataset_builders/sglb_16.py
- backend/benchmark/tasks/sglb_16.py
- backend/benchmark/llm_runner.py (+ prompt builder)
- backend/benchmark/tasks/__init__.py (+ register)
- backend/benchmark/datasets/sglb_16_review_redflag.yaml
- docs/sglb_specs/SGLB-16.md (bump version)
- backend/tests/test_sglb_16_task.py
- Makefile: + build-sglb-16

Files you must NOT touch:
- G1/G2/G3's sglb_NN files.

Task contract:
- Input: `{"contract_text": str}` — a SG contract with planted
  defects.
- Output: JSON array `[{"defect_type": str, "span_start": int,
  "span_end": int}]`
- Score: F1 over (defect_type, span) matches with ±10-char tolerance.

Closed defect taxonomy (document explicitly):
- missing_limitation_of_liability
- governing_law_non_singapore
- missing_pdpa_data_protection_clause
- missing_notice_period
- missing_dispute_resolution_clause
- missing_termination_clause

Defect injection (mechanical, no legal judgment):
1. Start from a clean SG-context contract template.
2. Inject 3-5 defects deterministically (e.g. delete the limitation
   clause; swap "Singapore" to "New York" in governing law).
3. Each injection logged in metadata.

Smoke seed: 30 cases.

Branch: feat/sglb-v0.2-wave-1.
Commit: `feat(sglb-16): Review-Redflag-Recall (closes #57)`.

Acceptance: 30-case smoke; tests pass.
Report back: defect-type coverage; any clause type where injection
is hard.
```

# Batch H — v0.2 Task Wave 2 (#51, #53, #56), 3 parallel agents

**Coordination contract:** branch `feat/sglb-v0.2-wave-2`.

**Synth-gen cost warning:** H2 and H3 need synthetic candidates.
Get explicit user approval before kicking off new synth jobs.

## H1: SGLB-10 Citation-Generation

```text
You are working on issue #51 (SGLB-10 Citation-Generation).

Depends on the SAL citation grammar (backend/api/services/sal_citation.py)
and ideally the CommonLII SG corpus (Batch B). If Batch B has landed,
use real citations; otherwise generate from grammar + a curated SG
case list.

Read AGENT-RUNBOOK.md, docs/sglb_specs/SGLB-10.md.

Files you own:
- backend/benchmark/dataset_builders/sglb_10.py
- backend/benchmark/tasks/sglb_10.py
- backend/benchmark/llm_runner.py (+ prompt builder)
- backend/benchmark/tasks/__init__.py (+ register)
- docs/sglb_specs/SGLB-10.md (bump)
- backend/tests/test_sglb_10_task.py
- Makefile: + build-sglb-10

Files you must NOT touch:
- H2/H3's sglb_NN files.

Task contract:
- Input: `{"fact_pattern": str}` — a SG legal scenario.
- Output: JSON array of citation strings ordered by relevance.
- Score: exact-match top-1 + top-3 accuracy.

Mechanical extraction: gold citation derived from cases where the
published headnote matches the input fact pattern. Headnotes come
from CommonLII; if Batch B has not landed, use a hand-curated set of
~30 well-known SG cases (e.g. Spandeck Engineering, RBC Properties,
Tan Cheng Bock) and synthesise fact patterns matching them — but the
synthesis prompt is documented and the case-to-fact mapping is
mechanical.

Branch: feat/sglb-v0.2-wave-2.
Commit: `feat(sglb-10): Citation-Generation (closes #51)`.

Acceptance: 30-50 case smoke; tests pass.
Report back: dependence on Batch B; quality concerns with curated
case set.
```

## H2: SGLB-12 Multi-Issue-Spotting (complete existing stub)

```text
You are working on issue #53 (SGLB-12 Multi-Issue-Spotting). A
synthetic runner already exists at backend/benchmark/synthetic/sglb_12.py
and backend/benchmark/tasks/sglb_12.py; your job is to complete data +
verify the harness end-to-end.

Read AGENT-RUNBOOK.md, docs/sglb_specs/SGLB-12.md, the existing
synth files (taxonomy.yaml, compositions.yaml, sglb_12.py),
backend/benchmark/synthetic/README.md.

Files you own:
- backend/benchmark/dataset_builders/sglb_12.py
- backend/benchmark/tasks/sglb_12.py (extend if needed)
- backend/benchmark/llm_runner.py (refine sglb_12 prompt if needed)
- backend/benchmark/datasets/sglb_12_multi_issue_reviewed/
- docs/sglb_specs/SGLB-12.md (bump to 0.1-shipped if you reach ≥50
  reviewed cases)
- backend/tests/test_sglb_12_task.py (extend coverage)

Files you must NOT touch:
- H1/H3's sglb_NN files.
- backend/benchmark/synthetic/sglb_12.py (used by the existing synth
  pipeline; do not modify unless a real bug surfaces).

Cost gate: if reviewed candidates don't exist yet, you'd need to run
`make synth-gen TASK=sglb_12 N=200 ...`. The SGLB-08 synth gen
costs ~$0.05/example via Azure gpt-5. A 200-case SGLB-12 run would
cost ~$10-20. STOP and get user approval before firing synth-gen.

Branch: feat/sglb-v0.2-wave-2.
Commit: `feat(sglb-12): Multi-Issue-Spotting complete dataset (closes
#53)`.

Acceptance: ≥50 reviewed cases promoted; tests pass; harness runs
end-to-end.

Report back: actual synth cost; any taxonomy categories producing
low-quality candidates.
```

## H3: SGLB-15 Draft-Constraint-Sat (complete existing stub)

```text
You are working on issue #56 (SGLB-15 Draft-Constraint-Sat). A
synthetic runner exists at backend/benchmark/synthetic/sglb_15.py
and backend/benchmark/tasks/sglb_15.py; complete the data + add
SG-context constraints.

Read AGENT-RUNBOOK.md, docs/sglb_specs/SGLB-15.md, IFEval paper
(Zhou et al., 2023, https://arxiv.org/abs/2311.07911),
backend/benchmark/constraints.py.

Files you own:
- backend/benchmark/dataset_builders/sglb_15.py
- backend/benchmark/tasks/sglb_15.py (extend)
- backend/benchmark/llm_runner.py (refine prompt)
- backend/benchmark/constraints.py (add SG-context constraints)
- backend/benchmark/datasets/sglb_15_draft_constraints_reviewed/
- docs/sglb_specs/SGLB-15.md (bump)
- backend/tests/test_sglb_15_task.py

Files you must NOT touch:
- H1/H2's sglb_NN files.
- backend/benchmark/synthetic/sglb_15.py (existing synth pipeline).

SG-context constraints to add (at minimum 6 kinds):
- must_cite_pdpa_section (regex against SAL grammar)
- must_include_governing_law_singapore
- must_reference_employment_act
- must_specify_notice_period_min_days
- must_include_dispute_resolution_clause
- must_have_pdpa_data_processor_designation

Same synth cost gate as H2; get approval before firing synth-gen.

Branch: feat/sglb-v0.2-wave-2.
Commit: `feat(sglb-15): Draft-Constraint-Sat complete dataset (closes
#56)`.

Acceptance: ≥30 reviewed cases; ≥6 SG constraint kinds; tests pass.
Report back: which constraint kinds are easy vs hard to verify
deterministically.
```

# Batch F — MCP Server (#48), 4 parallel agents

**Goal:** expose junas as an MCP server so Claude Desktop / Claude
Code users can run benchmarks + query SG legal sources without
leaving chat.

**Coordination contract:** branch `feat/mcp-server`. F1 lands first;
F2/F3/F4 fan out off F1's branch.

## F1: MCP server scaffolding + transport

```text
You are working on issue #48 in the junas repo. Read AGENT-RUNBOOK.md
and the MCP spec at https://modelcontextprotocol.io. Use the official
python-sdk pattern.

Goal: scaffold the MCP server. Tools come in F2.

Files you own:
- backend/mcp/__init__.py (new)
- backend/mcp/server.py (new — server entry, stdio + http transports)
- backend/pyproject.toml: add `mcp` Python SDK
- Makefile: + `make mcp` target (defaults to stdio)
- README2.md: append a short "Run as MCP server" section

Files you must NOT touch:
- backend/mcp/tools/* (F2)
- docs/mcp/* (F3)
- backend/tests/test_mcp_*.py (F4)

Server requirements:
- Name: "junas-mcp"
- Transports: stdio default; --http flag for HTTP on port 3344
- Tool registry: empty in F1; expose a single `health` tool that
  returns repo version + git SHA + python version so F3's setup doc
  can verify the install
- Graceful shutdown on SIGTERM

Branch: feat/mcp-server.
Commit: `feat(mcp): server scaffolding + transport (advances #48)`.

Acceptance: `make mcp` boots without error; `health` tool responds.

Report back: MCP SDK version pinned; transport latency observations.
```

## F2: Tool implementations

```text
You are working on issue #48 in the junas repo. WAIT until F1 has
landed feat/mcp-server. Read AGENT-RUNBOOK.md, F1's server.py,
backend/api/services/sal_citation.py, statute_lookup.py,
case_retrieval.py, compliance_service.py.

Goal: implement 5 MCP tools that delegate to existing copilot services.

Files you own:
- backend/mcp/tools/__init__.py
- backend/mcp/tools/run_benchmark.py
- backend/mcp/tools/verify_citation.py
- backend/mcp/tools/lookup_statute.py
- backend/mcp/tools/retrieve_cases.py
- backend/mcp/tools/check_compliance.py

Files you must NOT touch:
- backend/mcp/server.py (F1)
- backend/api/services/* (consumer code only)
- docs/mcp/* (F3)
- backend/tests/test_mcp_*.py (F4)

Tools:
1. `run_benchmark(task: str, model: str) -> dict` — invokes
   `benchmark.cli` against `task`; validates `task` in TASKS; model
   in {azure, anthropic, gemini, ollama}; returns receipt summary.
2. `verify_citation(citation: str) -> dict` — wraps
   `api.services.sal_citation.validate_citation`.
3. `lookup_statute(query: str) -> dict` — wraps statute_lookup.
4. `retrieve_cases(query: str, k: int = 5) -> dict` — wraps
   case_retrieval.
5. `check_compliance(text: str, regime: str) -> dict` — regime ∈
   {pdpa, employment_act, roc_2021}.

Each tool: declare JSON input schema; return JSON-serializable dict;
surface errors via an `error` field (do not raise).

Branch: feat/mcp-server.
Commit: `feat(mcp): 5 tools delegating to copilot services (advances
#48)`.

Acceptance: F1's `list_tools` returns 5 tools after import; each
callable via the MCP test client.

Report back: any service that lacked a clean entry point.
```

## F3: Claude Desktop config + setup docs

```text
You are working on issue #48 in the junas repo. WAIT until F1 has
landed. Read AGENT-RUNBOOK.md.

Goal: end-user setup so a Claude Desktop user can install + use
junas-mcp in <5 min.

Files you own:
- docs/mcp/setup.md
- docs/mcp/example-prompts.md (10 prompts exercising each tool)
- docs/mcp/troubleshooting.md

Files you must NOT touch:
- backend/mcp/* (F1/F2)
- backend/tests/test_mcp_*.py (F4)

Setup doc:
- Cover macOS / Linux / Windows.
- Exact JSON snippet for `~/Library/Application Support/Claude/
  claude_desktop_config.json` (macOS path; equivalent paths for the
  other two OSes).
- BYOK env-var-setting step (Azure or Anthropic).
- Verification: ask Claude Desktop to call the `health` tool.

Example prompts: 10 covering each tool individually + 2 chained
workflows.

Branch: feat/mcp-server.
Commit: `docs(mcp): setup + example prompts + troubleshooting
(advances #48)`.

Acceptance: a fresh user can install + use junas-mcp within 5 min.

Report back: brittle setup steps; OS-specific gotchas.
```

## F4: MCP tests + integration

```text
You are working on issue #48 in the junas repo. WAIT until F1+F2
have landed. Read AGENT-RUNBOOK.md, F1's server, F2's tools.

Goal: tests for the MCP server + tools.

Files you own:
- backend/tests/test_mcp_server.py
- backend/tests/test_mcp_tools.py

Files you must NOT touch:
- backend/mcp/* (F1/F2)
- docs/mcp/* (F3)

Requirements:
- Mock the underlying api.services calls; do NOT make real LLM calls.
- For run_benchmark, use the existing MockLLMClient pattern.
- Test the JSON-schema validation per tool input.
- One integration test: spawn the server in a subprocess, send a
  `list_tools` request, assert 5 tools enumerated.

Branch: feat/mcp-server.
Commit: `test(mcp): server + tool tests (advances #48)`.

Acceptance: pytest passes; no network calls in test mode.

Report back: any tool hard to test deterministically.
```

## SOLO-7: Reference copilot scope cleanup (#35)

```text
You are addressing issue #35 in the junas repo: keep only SG
retrieval, citation, and compliance surfaces in the reference
copilot. Read AGENT-RUNBOOK.md and the pivot history in git.

Audit which frontend routes and backend routers are still
non-SG-relevant. The audit doc lists what should have been removed
(predictions/, rome-statute/, compare-jurisdictions/). Verify those
are gone; flag any that aren't.

This is an audit-then-fix task. Step 1: list every page + router +
service that doesn't fit the minimal copilot scope (BYOK chat, SG
retrieval, citation verifier, PDPA+EA compliance, SG clauses +
templates, document parsing). Step 2: produce a PR that removes
them or marks them as out-of-scope-but-kept.

Don't be over-eager. The chat surface, batch-analysis, contracts,
ner pages are arguably in scope. Apply the pivot-doc §5 "minimal
scope" test: does this surface demonstrate the benchmark? If not,
flag it.

Branch: refactor/copilot-scope.
Commit: `refactor(copilot): keep only SG retrieval/citation/
compliance surfaces (closes #35)`.

Acceptance: the user can ship a smaller copilot landing without
dead links.

Report back: a numbered audit list (this is the deliverable) +
the actual cuts you made. If you want the user to make a
keep-vs-cut call, surface the question.
```

## SOLO-11: Port SG-applicable contract templates (#42)

```text
You are working on issue #42 in the junas repo.

This task is GATED on SOLO-7 (#35 copilot scope cleanup). If scope
is still in flux, write the audit list of templates you'd port and
stop. Otherwise proceed to implementation.

Read AGENT-RUNBOOK.md, backend/api/services/template_service.py (the
existing 6 SG seed), CONTRIBUTING.md.

Files in scope (if implementing):
- backend/api/services/template_service.py (extend)
- backend/data/templates/sg/ (new — markdown templates)
- backend/tests/test_template_service.py (extend)
- frontend/app/templates/page.tsx (verify it renders the additions)

Templates to add (target 10-12 total; the existing 6 are already in):
1. Confidentiality / NDA (mutual)
2. Employment contract (SG Employment Act compliant)
3. Service agreement (B2B SG)
4. Data processing agreement (PDPA compliant)
5. Independent contractor agreement
6. Non-compete + restraint of trade (per Smile Inc Dental Surgeons
   v Lui Andrew Stewart [2012] 4 SLR 308)
7. Shareholder agreement (basic)
8. SaaS terms of service
9. Loan agreement (basic, SG governing law)
10. Power of attorney (general)

Constraints:
- All templates derivable from publicly-available SG drafting-guide
  sources (cite each in template frontmatter).
- No proprietary forms.
- Each template carries a limitation disclaimer block referencing the
  README §"Legal Disclaimer".

Branch: feat/sg-contract-templates.
Commit: `feat(templates): port SG-applicable contract templates
(closes #42)`.

Acceptance: 10-12 templates total; the /templates frontend route
lists them; tests pass.
Report back: any template where SG-source publicly-available
drafting was thin.
```

## SOLO-12: Logfire observability (#43)

```text
You are working on issue #43 in the junas repo. Read AGENT-RUNBOOK.md
and Pydantic Logfire docs (https://docs.pydantic.dev/logfire/).

Goal: opt-in Logfire integration for benchmark contributors who want
to inspect their own runs.

Files in scope:
- backend/api/telemetry.py (new — Logfire setup, gated behind
  LOGFIRE_TOKEN env var)
- backend/api/main.py (instrument the FastAPI app; opt-in via env)
- backend/benchmark/runner.py (instrument the runner; record per-case
  spans)
- backend/pyproject.toml: `logfire` to optional dev deps (NOT runtime)
- docs/contributor-observability.md (new)

Constraints:
- Default off. If LOGFIRE_TOKEN unset, Logfire is a no-op (zero
  network).
- NEVER log API keys, model outputs verbatim, or user-provided text.
  Only structural metadata: workflow name, evaluator name, score,
  duration, error class. The harness's existing receipt JSON contains
  outputs; that's the right place for them, not telemetry.

Branch: feat/logfire-observability.
Commit: `feat(observability): opt-in Logfire instrumentation (closes
#43)`.

Acceptance: opt-in works; nothing leaks in CI; doc walks a contributor
through 2-min setup.
Report back: any signal Logfire surfaced that we should add as a
permanent metric in our own receipts.
```

## COPILOT-1: Sessions + history persistence

```text
You are working on copilot product polish in the junas repo. Read
AGENT-RUNBOOK.md, frontend/app/chat/page.tsx,
backend/api/routers/chat.py.

Current state: chat is in-memory only; reload loses history.

Goal: persistent chat sessions surviving reload and accessible across
browser tabs. Local-only data per README2 disclaimer.

Files in scope:
- backend/api/models/sessions.py (new — Pydantic)
- backend/api/routers/sessions.py (new — CRUD: LIST/GET/CREATE/RENAME
  /DELETE)
- backend/api/services/session_storage.py (new — SQLite via the
  existing alembic migration setup)
- backend/migrations/versions/<timestamp>_sessions.py (new alembic
  migration)
- frontend/app/chat/page.tsx (consume sessions API)
- frontend/components/SessionSidebar.tsx (new — left-rail list)
- frontend/lib/api-client.ts (extend; coordinate with Batch C C3 if
  not landed)
- backend/tests/test_sessions_router.py
- frontend/tests/SessionSidebar.test.tsx

Constraints:
- Local-only storage. No data leaves the user's machine.
- Schema: id, title (auto-from-first-user-message), created_at,
  updated_at, message_count, deleted_at (soft delete).
- Optional user_id field (NULL in v0.1) for future multi-user
  copilot.
- Sidebar collapsible; keyboard shortcut ⌘B (coordinate with
  COPILOT-4).

Branch: feat/copilot-sessions.
Commit: `feat(copilot): persistent chat sessions with local storage`.

Acceptance: reload preserves history; rename/delete works; sidebar
renders all sessions; tests pass.
Report back: storage choice (SQLite vs IndexedDB vs LocalStorage) +
rationale.
```

## COPILOT-2: Batch-analysis polish for real workflows

```text
You are working on copilot product polish. Read AGENT-RUNBOOK.md,
frontend/app/batch-analysis/*, backend/api/routers/contracts.py.

A real legal-tech engineer running this against a portfolio wants:
- Drag-drop multi-doc upload (≤50 at once)
- Per-doc progress, cancelable
- Sortable results table, CSV export
- Per-doc drill-down into LLM reasoning + flagged clauses

Files in scope:
- frontend/app/batch-analysis/page.tsx (rebuild)
- frontend/app/batch-analysis/[batchId]/page.tsx (new — drill-down)
- backend/api/routers/contracts.py (extend for batch + SSE progress)
- backend/api/models/batch.py (new — BatchJob + BatchResult)
- backend/api/services/batch_service.py (new — orchestrates per-doc
  contract_classifier + tos_scanner calls; cancellable via asyncio
  cancellation tokens)
- backend/tests/test_batch_analysis.py
- frontend/tests/batch-analysis.test.tsx

Constraints:
- SSE for progress, not polling.
- Cancel TRULY cancels the backend work (asyncio task cancellation
  propagates through to the LLM client). Test this with a 10-doc
  batch + a cancel mid-run.
- 50-doc cap enforced server-side.
- Results survive reload (use sessions API from COPILOT-1 if landed).

Branch: feat/copilot-batch-polish.
Commit: `feat(copilot): batch-analysis polish for production
workflows`.

Acceptance: 10-doc upload completes with live progress; mid-run
cancel works; CSV export works; tests pass.
Report back: throughput characteristics; backend bottleneck if any.
```

## COPILOT-3: DOCX export

```text
You are working on copilot product polish. Read AGENT-RUNBOOK.md.

Lawyers live in Word. Markdown export is for developers; DOCX is the
minimum for the legal user. Implement DOCX export for benchmark
receipts AND chat sessions.

Files in scope:
- backend/api/services/docx_export.py (new — python-docx based)
- backend/api/routers/exports.py (new — /exports/receipt/{run_id}.docx
  and /exports/session/{session_id}.docx endpoints)
- backend/pyproject.toml: + `python-docx`
- frontend/components/ExportButton.tsx (new)
- frontend/app/chat/page.tsx (mount ExportButton)
- frontend/app/benchmarks/runs/[runId]/page.tsx (mount ExportButton;
  coordinate with SOLO-2 if not landed)
- backend/tests/test_docx_export.py

DOCX content shape:
- Receipt: header (task, model, date), per-evaluator means, per-case
  table.
- Session: header (title), messages with role/timestamp, code blocks
  in Courier New.
- Footer: auto-inject the README.md §"For Informational Purposes
  Only" disclaimer on EVERY export.

Constraints:
- A 200-message session must export in <3s.
- Markdown tables / nested lists / code blocks round-trip cleanly.
- File-naming: `junas-receipt-<run_id>.docx` and
  `junas-session-<session_id>-<slugified-title>.docx`.

Branch: feat/copilot-docx-export.
Commit: `feat(copilot): DOCX export for receipts + chat sessions`.

Acceptance: tests pass; manual export of a 200-message session
produces a clean .docx.
Report back: any markdown construct that didn't round-trip.
```

## COPILOT-4: Keyboard shortcuts + power-user palette

```text
You are working on copilot product polish. Read AGENT-RUNBOOK.md,
frontend/components/chat/CommandPalette.tsx,
frontend/lib/commands/command-handler.ts.

This builds on Batch C C2 (command palette dead-link fix); if C2
hasn't landed, fix the deadlinks first as part of this PR.

Files in scope:
- frontend/lib/keyboard.ts (new — global keymap + per-page bindings)
- frontend/components/KeyboardHelpDialog.tsx (new — `?` opens cheat
  sheet)
- frontend/components/chat/CommandPalette.tsx (extend)
- frontend/app/layout.tsx (mount global keyboard listener)
- frontend/tests/keyboard.test.tsx

Shortcuts:
- ⌘K — open command palette
- ⌘/ or ? — keyboard help dialog
- ⌘L — focus chat input
- ⌘⇧L — new chat
- ⌘B — toggle session sidebar (works with COPILOT-1 SessionSidebar)
- ⌘⇧E — export current view to DOCX (works with COPILOT-3)
- ⌘⇧C — copy last assistant response
- ⌘P — jump-to-page palette
- ⌘⇧K — re-run last benchmark

Constraints:
- All shortcuts discoverable from the help dialog.
- Do NOT override OS-reserved shortcuts (⌘W, ⌘T, ⌘N).
- Provide a Mac vs Windows/Linux variant table in the help dialog
  (⌘ → Ctrl).
- Palette commands match the help-dialog list 1:1 (regression-tested
  per C2's invariant).

Branch: feat/copilot-keyboard.
Commit: `feat(copilot): keyboard shortcuts + command palette polish`.

Acceptance: ≥9 shortcuts working; help dialog enumerates them; the
palette includes them all.
Report back: any shortcut that conflicted with the browser; any
chord suggested but not implementable.
```

---

# Dropped from the rewrite

These items appeared in the previous PROMPTS-TO-RUN.md but were
removed during the 2026-06-05 methodology-first rewrite. Reopen
only if the underlying premise changes.

| Item | Reason for drop |
|---|---|
| **SOLO-13 region-per-index design doc (#45)** | SG-only scope per memory + project goals; multi-jurisdiction (MY adjacency) is not a v0.1 or v0.2 concern. Reopen if/when MY adjacency is concretely planned. |
| **SOLO-15 jurisdiction selector UI (#47)** | Depends on SOLO-13; same drop rationale. A single-option dropdown is forward-investment with no current payoff. |
| **SOLO-14 PydanticAI migration (#46)** | Low priority by author's own admission; off-thesis (orchestration refactor doesn't serve the benchmark or the vendor-eval thesis). Reopen as a separate refactor issue if needed. |
| **SOLO-16 branching policy consolidation (#73)** | Doc hygiene only; not load-bearing. Merge into Tier 1 CONTRIBUTING.md updates if relevant during NEW-DISPUTE-PROCESS work. |

---

# Truly backlog (still not prompt-ready)

These are items left without prompts. They need user decisions or
external dependencies before they can be specified:

- **#58** — meta-tracking issue for the v0.2 expansion. All sub-issues
  (#50, #51, #53, #54, #55, #56, #57) are specified above (Batches G
  + H). When all close, this one closes too.
- **Future user-driven issues** — if you find a need that isn't in
  this doc:
  1. Open a GitHub issue; write a prompt for it here in a follow-up PR.
  2. Surface to the user directly if it's a one-off operational concern.

