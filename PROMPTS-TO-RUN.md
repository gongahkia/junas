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

<!-- END_OF_FILE_PLACEHOLDER -->
