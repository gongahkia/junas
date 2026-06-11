# AGENT-RUNBOOK

You are a Claude Code agent dropped into the `gongahkia/junas` repository.
This file is the 5-minute orientation that gets you producing useful PRs
without burning context on rediscovery.

If you have already read this in a prior session, skim §5 and §10 for
anything that may have changed.

## 1. What this repo is

**SG-LegalBench** — the first open benchmark for Singapore legal
reasoning in LLMs, plus a minimal reference copilot. Eight tasks
(SGLB-01..08) grounded in public-domain SG sources (PDPC, SSO, MOM,
ROC 2021). Mechanical label extraction from regulator outputs; **we
make no legal interpretive claims**. The repo holds a Python backend
(FastAPI + benchmark harness + ingestion pipelines), a Next.js
frontend (landing + leaderboard + copilot routes), and per-task
specs.

Read once for context:

- `README.md` — public-facing thesis and current repo overview.
- `docs/coverage-matrix.md` — methodology bar. Non-negotiable.
- `CONTRIBUTING.md` — task contribution flow + adapter rules.
- `docs/sglb_specs/` — per-task spec docs (SGLB-01 through SGLB-16).

## 2. Repo layout

```
backend/
├── api/                       FastAPI app
│   ├── adapters/              public-source + user-credentialed adapters
│   │   ├── public/            SSO, PDPC, MOM, IRAS, CommonLII, Hansard
│   │   └── user_credentialed/ LawNet (Phase 3, official APIs only)
│   ├── routers/               HTTP endpoints
│   └── services/              business logic (citation, retrieval, …)
├── benchmark/                 SG-LegalBench harness
│   ├── dataset_builders/      builder per task (SSO/PDPC JSONL → cases)
│   ├── tasks/                 oracle runner per task
│   ├── synthetic/             LLM-judge synth gen pipeline (SGLB-08/12/15)
│   ├── datasets/              YAML datasets the harness consumes
│   ├── evaluators.py          strong + weak scorers (strict mode rejects weak)
│   ├── llm_runner.py          generic LLM client → task runner shim
│   ├── registry.py            TASKS + PROVENANCE registries
│   └── cli.py                 `python -m benchmark.cli` entrypoint
├── data/
│   ├── ingestion/             scrapers (pdpc, sso, mom-pending, commonlii-pending)
│   ├── parsers/               HTML → structured-record parsers
│   ├── benchmarks/            JSONL splits per task (train/dev/test)
│   └── raw/                   vendored upstream data (pdpc_decisions.xlsx)
├── ml/pipelines/              ingestion entrypoints (ingest_pdpc, ingest_sso, ...)
├── tests/                     pytest; fixtures under tests/fixtures/
├── vendor-data/               output dir for ingested JSONL (gitignored)
└── pyproject.toml             Python 3.11+; deps listed here
frontend/
├── app/                       Next.js 14 App Router pages
├── components/                shared React components
└── lib/                       api-client, command-handler, hooks
docs/
├── coverage-matrix.md         methodology bar (READ THIS)
├── sglb_specs/                per-task specs
├── retrieval-audit.md
└── audit/                     UX + engineering audit findings
.github/workflows/             CI
Makefile                       all common operations (make help…)
CONTRIBUTING.md                contribution flow
PROMPTS-TO-RUN.md              prompts for parallel agents (this is where you came from)
AGENT-RUNBOOK.md               this file
```

## 3. Setup

```sh
# 1. Python venv — use python.org 3.13 (Homebrew 3.13/3.14 ship a
# broken libexpat that breaks openpyxl. The user's working venv is at
# repo-root/.venv pointing at /Library/Frameworks/Python.framework/3.13.
# If .venv already exists, use it; do NOT recreate it.
ls .venv/bin/python || uv venv .venv --python /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13

# 2. Install runtime + dev deps (uv is the package manager; pip works too)
uv pip install --python .venv/bin/python -e backend
uv pip install --python .venv/bin/python pytest pytest-asyncio ruff openpyxl beautifulsoup4 lxml httpx pyyaml pydantic pydantic-settings openai anthropic

# 3. Sanity check
cd backend && ../.venv/bin/python -m pytest tests/test_benchmark_harness.py -q
```

**Do not use system `python3`**. Homebrew's 3.12+ has a libexpat ABI
mismatch on this Mac that breaks `openpyxl`. The `.venv` is the only
reliable interpreter.

## 4. Commands you will use constantly

| Need | Command |
|---|---|
| Run all benchmark tests | `cd backend && ../.venv/bin/python -m pytest tests/ -q --ignore=tests/integration` |
| Run one test file | `cd backend && ../.venv/bin/python -m pytest tests/test_<name>.py -x -q` |
| Lint | `cd backend && ../.venv/bin/python -m ruff check <path>` |
| Run a benchmark task end-to-end | `cd backend && ../.venv/bin/python -m benchmark.cli run --workflow <name> --dataset <path> --evaluator <ev> --strict` |
| Materialise SGLB-NN data | `make build-sglb-<NN>` (or run `python -m benchmark.dataset_builders.sglb_NN`) |
| Ingest PDPC | `make ingest-pdpc` |
| Ingest SSO | `make ingest-sso [SSO_CODE=ROC2021]` (network call to AGC) |
| Synthetic gen | `make synth-gen TASK=sglb_08 N=400 PROVIDERS=azure MAX_COST_USD=8 ENV_FILE=../.env` |

## 5. Coding conventions

Source of truth: `~/.claude/CLAUDE.md` (user's global) + project root
`CLAUDE.md` symlink. Key rules:

- **Extreme terseness.** Min tokens. No apologies.
- **Fail fast.** No defensive try/except around code that "shouldn't"
  fail. Catch at boundaries (HTTP, file IO), not in the middle.
- **No auto-refactor.** Stick to the diff of the requested task.
- **Comments: in-line only, lowercase by default.** Capitalize tech
  names only (`# use Docker`). Don't write multi-line docstrings
  unless the function is a public API surface.
- **Spacing: vertical density.** Minimise blank lines.
- **No emojis** unless the user explicitly asks.
- **Labels for unverified claims.** Start sentences with `[Inference]`,
  `[Speculation]`, or `[Unverified]` if not directly sourced. This is
  user preference; respect it in commit messages and PR descriptions
  too.

## 6. Methodology bar (do not violate)

`docs/coverage-matrix.md` §4 is binding. Summary:

1. **Mechanical label extraction only.** Gold labels must come from a
   regulator or court output by an extractable rule. Author legal
   judgement is not a label source.
2. **Public-domain sources only** for the benchmark. Paywalled (LawNet,
   Practical Law) is copilot-only via user-supplied credentials.
3. **Strong evaluators in `--strict` mode.** Weak-tier (keyword
   presence, length thresholds) are flagged + rejected.
4. **Post-cutoff held-out split** (2026-Q1) for contamination
   resistance.
5. **Receipt provenance** for every LLM-backed run (prompt_version,
   prompt_sha, provider_label, max_tokens). Use
   `benchmark.llm_runner.register_llm_task(...)` to get it automatically.

If your task can't satisfy these, stop and surface it — don't try to
hand-author labels to fit.

## 7. Git workflow

Canonical branching policy: `CONTRIBUTING.md#branching-policy` (single
source of truth — SOLO-16 consolidates the rest). Summary:

- **Branch naming:** `feat/<short>`, `fix/<short>`, `docs/<short>`,
  `refactor/<short>`, `ci/<short>`, `test/<short>`. Small low-risk
  changes can land on `main` direct; anything touching the scorer
  registry, dataset format, or shared interfaces must branch + PR.
- **Worktrees** for parallel agents: the user runs each agent in
  `/Users/gongahkia/Desktop/coding/projects/junas/.claude/worktrees/agent-<id>/`.
  If you are spawned with `isolation: "worktree"`, your CWD is set up.
- **Commits:** Conventional Commits. End every commit with
  `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
- **Never** `git push --force` to main. Never `git push` unless the
  user explicitly asks.
- **Pre-commit hook may fail.** Don't `--no-verify`; fix the failure
  instead. If you absolutely cannot resolve it, surface to the user.

## 8. Background processes you must not kill

At time of writing (2026-06-04 15:25 SGT):

No long-running background processes. The SGLB-08 synth gen finished
at 400/400 (~4 hours elapsed); all candidates have been bulk-approved
+ promoted to the reviewed dataset. Methodology caveat in
`docs/sglb_specs/SGLB-08.md` — see SOLO-17 / SOLO-18 in
`PROMPTS-TO-RUN.md` for the multi-judge κ + human-holdout follow-up.

If you fire any of these you MUST not kill them mid-flight:
- Any `benchmark.synthetic generate ...` run (cost-sensitive)
- Any `benchmark.scripts.run_baselines_*` run (cost-sensitive)
- Any live ingestion against AGC, MOM, CommonLII (rate-limited;
  killing wastes the user's network budget on already-fetched pages)

**Critical risk note for any future synth gen:** the Azure deployment
is a reasoning model (gpt-5 by config). Reasoning tokens are billed
separately from output tokens but the harness's cost estimator
(`backend/benchmark/synthetic/planner.py::ESTIMATED_COST_PER_EXAMPLE_USD`
= $0.015 for Azure) does NOT account for reasoning-token cost.
**Actual spend will be 5-10x the estimate.** The previous 400-case
SGLB-08 run cost an estimated $40-80 against an estimator quote of $6.
Get explicit user approval BEFORE firing any synth-gen on Azure;
Anthropic + Gemini judges are 5-10x cheaper per call.

## 9. Test requirement

Every PR must pass `pytest -x -q` on the affected test files. If you
add a feature, you add tests. If you change a scorer, you add a test
that would have failed before the change. Mocking is acceptable for
LLM clients (`benchmark.llm_runner.MockLLMClient`); we never mock
scorers.

Existing test files are the canonical templates:

- `backend/tests/test_sglb_01_task.py` — full task (builder + scorer + runner + prompt)
- `backend/tests/test_sso_parser.py` — parser + fixture pattern
- `backend/tests/test_llm_runner.py` — LLM runner pattern
- `backend/tests/test_receipt_provenance.py` — provenance contract

## 10. What is shipped vs pending

As of 2026-06-04:

| Task | Status | Data | Code |
|---|---|---|---|
| SGLB-01 PDPA-Outcome | shipped | 211 cases | ✅ |
| SGLB-02 Statute-QA | shipped (PDPA seed) | 78 cases | ✅ |
| SGLB-03 Case-Holding | deferred to v0.2 | — | — |
| SGLB-04 Citation-Verify | shipped (smoke) | 30 cases | ✅ |
| SGLB-05 Employment-Issue | code-shipped | pending #59 | ✅ |
| SGLB-06 Rules-of-Court-2021 | code-shipped | pending live SSO ingest | ✅ |
| SGLB-07 Jurisdiction-Routing | code-shipped | pending #34 | ✅ |
| SGLB-08 Clause-Tone | shipped (single-judge provisional) | 400 cases | ✅ |

**No baselines run yet.** No frontier-model scores exist; the launch
narrative ("frontier models fail PDPA at X%") is impossible without
that. Tracking issue: #36.

## 11. Open ship-blockers (you may be assigned one)

v0.1 launch path (in order of criticality):

- #36 baselines — needs Azure / OpenAI / Anthropic API budget (Batch D)
- #59 MOM scraper (unblocks SGLB-05 data) (Batch A)
- #34 CommonLII SG case ingester (unblocks SGLB-07 data) (Batch B)
- #60 PDPC Advisory Guidelines (unblocks SGLB-14) (SOLO-9)
- #37 arXiv preprint (SOLO-8)
- #39 launch assets (Batch E)
- #40 final benchmark name + license decision (SOLO-10 produces brief;
  USER decides)
- #75 retrieval R1/R2 dedupe + cursor (SOLO-1)
- #78 receipt drill-down endpoint (SOLO-2)
- #79 auth gate for hosted /benchmarks demo (SOLO-3)
- Frontend audit findings (Batch C): GET-with-sensitive-text (3 pages),
  unsanitised dangerouslySetInnerHTML (2 pages), duplicated API client,
  command-palette dead links.

v0.2 task expansion (after v0.1 ships):

- #50/SGLB-09 Summary-Faithfulness (G1)
- #51/SGLB-10 Citation-Generation (H1)
- #53/SGLB-12 Multi-Issue-Spotting (H2 — synthetic, cost-gated)
- #54/SGLB-13 Counterfactual-Outcome (G2)
- #55/SGLB-14 Statutory-Entailment (G3 — depends on #60)
- #56/SGLB-15 Draft-Constraint-Sat (H3 — synthetic, cost-gated)
- #57/SGLB-16 Review-Redflag-Recall (G4)
- #58 — meta-tracking; closes when all above close

Infra + product (parallel-safe with v0.1 work):

- #42 SG contract templates (SOLO-11; gated on #35)
- #43 Logfire observability (SOLO-12)
- #45 region-per-index design (SOLO-13 — design first; impl later)
- #46 PydanticAI migration (SOLO-14 — honesty-check first)
- #47 jurisdiction selector UI (SOLO-15 — gated on #45)
- #48 MCP server (Batch F)
- #73 branching policy consolidation (SOLO-16)
- #35 copilot scope cleanup (SOLO-7)

SGLB-08 methodology upgrade (lifts task from provisional to fully-
compliant per coverage-matrix §4.1):

- SOLO-17: multi-judge ensemble (Anthropic + Gemini votes; κ)
- SOLO-18: human-reviewed 40-case held-out subset

Copilot product polish (uplifts real legal-tech-buyer experience):

- COPILOT-1: persistent sessions
- COPILOT-2: batch-analysis polish
- COPILOT-3: DOCX export
- COPILOT-4: keyboard shortcuts + power-user palette

See `PROMPTS-TO-RUN.md` for the ready-to-paste prompt blocks; each
issue maps to a specific batch ID or SOLO-N / COPILOT-N entry. The
doc is sorted top-down by execution priority (Tier 1 = launch path,
Tier 4 = post-launch). Hard dependencies are listed inline.

## 12. Output etiquette when reporting back

After you finish a task, send the user a tight summary:

- Branch + commit SHA
- Files created/modified (1 line per group)
- Tests added + tests passing
- Anything you couldn't do + why
- Anything you saw that the user should know (security, cost, etc.)

Keep this under 300 words. The user reads many of these.
