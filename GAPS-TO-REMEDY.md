# GAPS-TO-REMEDY

Written 2026-06-05. Scope: SG-LegalBench v0.1 + v0.2.
Posture: **vendor scrutiny defence**. Review cadence: per minor release.

Companion to `PROMPTS-TO-RUN.md` — every gap with severity BLOCKER or HIGH maps to a Tier 1 prompt that closes it. Lower-severity gaps map to Tier 2/3 prompts.

## How to read this

Gaps are bucketed by severity. Each gap states (a) evidence with `file:line` or claim-source citation, (b) the risk a vendor would discount the benchmark over, (c) the remediation strategy, and (d) the closing prompt in `PROMPTS-TO-RUN.md` (existing `SOLO-N` / `Batch-X` or new `NEW-*` identifier).

## Severity definitions

- **BLOCKER** — any baseline number cannot be defended publicly without closing this. A careful vendor would refuse to cite SGLB scores until resolved.
- **HIGH** — vendors running the benchmark for real model selection would discount scores or write a disclaimer around them. Acceptable in pre-release with disclosure; not acceptable in v0.1 launch.
- **MEDIUM** — degrades long-term credibility but is acceptable in v0.1 with explicit caveat. Should land before v0.2.
- **LOW** — quality-of-life or operational gap. Not load-bearing for the eval-infrastructure thesis.

---

## Cross-cutting methodology gaps

### GAP-01 [BLOCKER] No contamination probe across baselines

- **Evidence:** `docs/coverage-matrix.md` §4.3 commits to "training-era vs post-cutoff" dual reporting; no per-model memorisation probe exists in `backend/benchmark/`. PDPC decisions, SSO sections, RoC 2021, MOM guidance are all public and indexed pre-cutoff for Opus 4.7 (Jan 2026), Gemini 2.x, gpt-5.
- **Risk:** every leaderboard score is suspect until vendors can see which models recall labels from training data vs. reason from facts. A model that scores 0.92 on SGLB-01 may have memorised PDPC's own findings text; without a probe, we cannot distinguish recall from reasoning.
- **Remediation:** implement a contamination probe per (task, model). For each labelled instance, ask the model in a separate prompt to recall the labelled property (e.g., "what was the outcome of PDPC case `<case_name>`?"). Mark per-case `memorisation_flag` in the receipt; emit per-task contamination summary (mean memorisation rate, contamination-adjusted score). Run against existing baselines.
- **Closes via:** `NEW-CONTAM` (Tier 1).

### GAP-02 [BLOCKER] Bootstrap CIs computed but not emitted in receipts

- **Evidence:** `backend/benchmark/scripts/build_leaderboard.py:125-142` implements `_bootstrap(values, seed, n=BOOTSTRAP_N)` returning `{mean, ci_low, ci_high, n}`, but this only runs as a post-hoc leaderboard step. Receipts at `runs/baselines/azure/sglb_01/20260604T081947Z.json` carry `per_evaluator_mean` only — no CI fields.
- **Risk:** vendors running the CLI receive scalar scores with no uncertainty quantification. Community submissions cannot publish CIs without re-running bootstrap off-line. At current N (SGLB-01: 211, SGLB-02: 78, SGLB-04: 30 smoke), F1 differences <5pp between frontier models are likely within bootstrap CI overlap — but the leaderboard cannot signal that without CIs in the receipt.
- **Remediation:** move `_bootstrap()` to a shared helper. Modify `backend/benchmark/runner.py` `RunSummary.from_results()` (or equivalent) to compute bootstrap over per-case scores at run time and persist `ci_low`, `ci_high`, `n_bootstrap` per evaluator in the receipt JSON. Update receipt schema doc. Add receipt-validation test that fails if CI fields are missing.
- **Closes via:** `NEW-CI-RECEIPT` (Tier 1).

### GAP-03 [BLOCKER] Anthropic + Gemini baselines claimed in commits, no receipts on disk

- **Evidence:** commits `414bb4b feat(baselines): Gemini baselines across SGLB-01/02/04` and `9beb086 feat(baselines): Anthropic baselines` exist in `git log`, but `runs/baselines/` only contains `azure/` and `ollama/` directories. The exploration audit confirmed: "Anthropic + Gemini baselines claimed in commit messages but **not found in runs/ directory**".
- **Risk:** any launch story that says "frontier models score X on SGLB" cannot reference Anthropic / Gemini until receipts exist. The discrepancy itself is a credibility risk if a reader diffs the commit message against the repo state.
- **Remediation:** investigate the commits — receipts may be in a worktree branch, deleted accidentally, or stored elsewhere. If unrecoverable, rerun the baselines under the new receipt format (post-`NEW-CI-RECEIPT`). Either outcome must be documented in `runs/baselines/PROVENANCE.md`.
- **Closes via:** `NEW-VERIFY-BASELINES` (Tier 1) + `NEW-BATCH-D` (Tier 1, full rerun under new receipt format).

### GAP-04 [HIGH] Three v0.1 tasks have no data but score 1.0 via oracle

- **Evidence:** `PROMPTS-TO-RUN.md` (pre-rewrite) §"Critical context" item 4 admits SGLB-05/06/07 score 1.0 via oracle because they have no real instances. Code is shipped per `backend/benchmark/dataset_builders/sglb_{05,06}.py` but `backend/benchmark/datasets/` has no corresponding YAML. SGLB-07 builder exists but no dataset.
- **Risk:** any vendor running the v0.1 suite sees three perfect-1.0 scores and either (a) believes the model scored perfectly (false), or (b) discovers it's oracle scoring (loss of trust). The claim "8 tasks shipped" is misleading until data lands.
- **Remediation:** mirror the `ElitigationAdapter` pattern at `backend/api/adapters/public/elitigation.py:36` (`benchmark_eligible = False`) for SGLB-05/06/07's dataset registrations. Update the leaderboard builder to skip ineligible tasks. Update `README2.md` task table to show "code-shipped, awaiting data" with a footnote per task. Restore eligibility per task as its data dependency closes (Batch A → SGLB-05, `NEW-SSO-EXPAND` → SGLB-06, Batch B → SGLB-07).
- **Closes via:** `NEW-HONEST-LEADERBOARD` (Tier 1).

### GAP-05 [HIGH] SAL citation grammar untested against the SAL Style Guide's own published examples

- **Evidence:** `backend/tests/test_sal_citation.py:14-23` uses hardcoded synthetic citations (e.g., `parse_elitigation_url("https://www.elitigation.sg/gd/s/2023_SGCA_5")`). The grammar source is asserted as `SAL_Style_Guide_Quick_Reference_2007_Ed.pdf` + `SLR_Style_Guide_2021.pdf` at `backend/api/services/sal_citation.py:10-12`, but no test loads worked examples from those guides.
- **Risk:** SGLB-04 (Citation-Verify) is the cleanest task by methodology *only if* the grammar matches the published guide. Without published-example tests, models are being scored against a possibly-buggy reimplementation of the grammar. A grammar bug = systematically wrong labels.
- **Remediation:** locate the SAL Style Guide PDFs (likely under `asset/` or `docs/references/`); extract every worked citation example (each is a labelled positive); add `backend/tests/test_sal_citation_published_examples.py` that asserts each example parses and validates correctly. Any test failure is a grammar bug to fix before SGLB-04 can be defended publicly.
- **Closes via:** `NEW-SAL-VALIDATION` (Tier 1).

### GAP-06 [HIGH] No extraction-rule version pinned in dataset metadata

- **Evidence:** `backend/data/ingestion/pdpc.py:154-178` writes `dataset_version: "sglb-01-v0.1"` and `label_provenance: "mechanical-extraction-from-pdpc-published-row"`, but no hash or version of the extraction rule itself (redaction patterns at `pdpc.py::_REDACTORS`, taxonomy mapping at lines 47-86). If a redactor changes, re-running the ingest silently produces a different dataset under the same `dataset_version` string.
- **Risk:** vendors cannot verify they're scoring against the same labels as the published baselines. Reproducibility is brittle. A silent change in redactor regex could flip outcomes on dozens of cases without bumping the version.
- **Remediation:** emit `extraction_rule_sha` (git rev of the ingestion module file) on every dataset row, plus a top-level `extraction_rules` map in the dataset YAML header listing the SHA per rule module. Validator in CI to confirm presence and consistency. Update `README2.md` reproducibility section.
- **Closes via:** `NEW-EXTRACT-VERSION` (Tier 1).

### GAP-07 [HIGH] SGLB-08 single-judge labels, κ undefined

- **Evidence:** `docs/sglb_specs/SGLB-08.md` discloses "single judge (Azure gpt-5-2); κ pending"; dataset metadata at `backend/benchmark/datasets/sglb_08_clause_tone_reviewed/dataset.yaml` carries `generator_provider: azure, generator_model: azure:gpt-5-2`; no multi-judge artefacts exist in `backend/benchmark/synthetic/`.
- **Risk:** LLM judges scoring LLM outputs without κ is the canonical "researcher-circularity" failure mode. A vendor will discount SGLB-08 entirely until κ exists across ≥3 frontier judges (per `docs/coverage-matrix.md` §4.1).
- **Remediation:** `SOLO-17` (existing, Tier 1) implements Anthropic + Gemini votes and computes pairwise + Fleiss' κ. Confirm `SOLO-17` stays in Tier 1 of the rewrite. Add explicit follow-up: if any κ pair < 0.4, reframe SGLB-08 in v0.1 as "judge-alignment sub-track" not "tone-correctness task" — the metric is then defensible as "inter-judge agreement on tone", not "ground truth on tone".
- **Closes via:** `SOLO-17` (Tier 1) + `NEW-08-REFRAME-IF-LOW-KAPPA` (conditional, Tier 1 follow-up).

### GAP-08 [HIGH] No human-validated held-out subset on any LLM-judged task

- **Evidence:** `docs/coverage-matrix.md` §4.1 mandates "human-spot-checked held-out subset" for LLM-judge tasks. SGLB-08's reviewed dataset metadata records `_human_review: { bulk approval }` with an explicit self-disclosed note that this is *not* a held-out subset.
- **Risk:** even with multi-judge κ (GAP-07 fix), the gold labels remain LLM-derived. A vendor will want at least N=40 human-verified cases per LLM-judged task as ground-truth anchor.
- **Remediation:** `SOLO-18` (existing, old Tier 2) does the 40-case selector + human review checklist for SGLB-08. Promote to Tier 1 alongside `SOLO-17`.
- **Closes via:** `SOLO-18` (promoted to Tier 1).

### GAP-09 [HIGH] No citation/statute normalisation spec document

- **Evidence:** `backend/benchmark/evaluators.py:520-536` implements `_normalise_section_citation()` as regex substitutions (`section` → `s`, `s.` → `s `, `Act,` → `Act `, whitespace collapse, lowercase, trailing-punct strip). `backend/api/services/sal_citation.py` implements case-citation parsing. There is no published spec naming the canonical forms or the test corpus.
- **Risk:** exact-match metrics on SGLB-02 reflect both model behaviour *and* normaliser behaviour. Vendors cannot audit the normaliser without reading the implementation, and cannot disprove a "the normaliser disagrees with my model output" complaint.
- **Remediation:** write `docs/normalisation-spec.md` enumerating canonical forms for: (1) section citations (e.g., `s 13 of the Personal Data Protection Act 2012`), (2) statute short names (e.g., `PDPA` for `Personal Data Protection Act 2012`), (3) case neutral citations (e.g., `[2023] SGCA 5`), (4) SLR / SLR(R) citations. Include the test corpus that proves the normaliser matches the spec.
- **Closes via:** `NEW-NORM-SPEC` (Tier 1).

### GAP-10 [HIGH] No published dispute / errata process

- **Evidence:** `CONTRIBUTING.md` mentions `errata.md` per dataset. `AGENT-RUNBOOK.md` references "PRs accepted against `data/sglb_NN/errata.md`; applied at next minor release". No GitHub issue template exists, no triage criteria, no errata release cadence published anywhere visible to a vendor.
- **Risk:** the first credible complaint about a label (e.g., "this PDPA case was misclassified") has no operational path. The benchmark loses authority on first dispute. A vendor's legal team may refuse to rely on a benchmark with no published dispute process.
- **Remediation:** write `docs/dispute-process.md` (vendor-facing); create `.github/ISSUE_TEMPLATE/label_dispute.yml` (operationalises filing); define triage SLA (target: <14 days to triage, corrigenda at next minor release); define versioned-dataset release flow (every accepted dispute bumps dataset patch version).
- **Closes via:** `NEW-DISPUTE-PROCESS` (Tier 1).

### GAP-11 [MEDIUM] License + name decision unresolved

- **Evidence:** `README2.md` §Licensing marks `[Unverified] License decision pending (issue #40); likely AGPL-3.0 for code, CC-BY 4.0 for datasets`.
- **Risk:** vendors will not commercially adopt against "likely". PR acceptance policy is undefined (does the project accept PRs under what licence? what about dataset contributions?). Issue #40 blocks Tier 3 + 4 outreach.
- **Remediation:** `SOLO-10` (existing, old Tier 2) — promote to Tier 1. Decision-only prompt; user picks in <10 minutes.
- **Closes via:** `SOLO-10` (promoted to Tier 1).

### GAP-12 [MEDIUM] No independent reproduction

- **Evidence:** every baseline in `runs/baselines/` is self-run by the project author. No third-party run exists.
- **Risk:** vendors will discount self-reported scores by default. Coverage-matrix mentions "community runbooks" but no plan to seed one.
- **Remediation:** outreach kit + technical contract for SMU SOLID, NUS TRAIL, and SAL data services to run the suite jointly. Even a single external reproduction (with κ recorded in the receipt) is a large credibility delta. Tier 3 placement: not Tier 1, because the methodology must be defensible *first* before asking an institution to reproduce.
- **Closes via:** `NEW-INDEPENDENT-REPRO` (Tier 3).

### GAP-13 [MEDIUM] N too small for stable F1 differentials

- **Evidence:** SGLB-01 N=211 (5 in test split), SGLB-02 N=78 (target 500), SGLB-04 N=30 smoke (production 1000+ deferred to #32), SGLB-05/06/07 N=0. At these sizes, F1 differences <5pp between frontier models are likely within bootstrap CI overlap.
- **Risk:** the leaderboard implies precision that the data cannot support. Even with CIs in receipts (GAP-02), the headline numbers will be hard to distinguish.
- **Remediation:** combined fix:
  - GAP-02 (CIs in receipts) makes the uncertainty visible.
  - GAP-04 (drop empty tasks) removes the misleading 1.0 oracle scores.
  - Tier 2 data work (Batch A, Batch B, `NEW-SSO-EXPAND`, `NEW-SGLB-04-PROD`) scales N where possible.
- **Closes via:** `NEW-CI-RECEIPT` (Tier 1) + `NEW-HONEST-LEADERBOARD` (Tier 1) + Tier 2 data prompts.

### GAP-14 [MEDIUM] No vendor-facing self-eval guide

- **Evidence:** `python -m benchmark.cli run ...` works (per `backend/benchmark/cli.py:14-96`) for someone who can read the code. There is no "if you're a SG legal-tech vendor and want to score your model in 10 minutes, here's the path" document.
- **Risk:** even if methodology is solid, distribution to the actual target user segment ("use us for your evals") is bottlenecked by missing onboarding. The benchmark gets cited by researchers but not run by vendors.
- **Remediation:** write `docs/vendor-self-eval-guide.md` covering: install / configure provider (BYOK) / select tasks / run with `--strict` / read receipts (including CI + contamination fields) / optional submission to leaderboard. Include a sample receipt walkthrough.
- **Closes via:** `NEW-VENDOR-GUIDE` (Tier 3).

### GAP-15 [MEDIUM] Library packaging absent (engineer audience)

- **Evidence:** the SAL citation grammar (`backend/api/services/sal_citation.py`), normalisers (`backend/benchmark/evaluators.py:520-536`), and adapter base interfaces (`backend/api/adapters/public/base.py`) are reusable but currently only as repo-internal imports. No `pyproject` extras, no sub-package, no PyPI publish path.
- **Risk:** SG legal-tech engineers (the strongest "real users" segment for an eval thesis) cannot `pip install` parts of the stack into their own products. The project's reach is capped by the monorepo's full-clone adoption surface.
- **Remediation:** extract `sal_citation`, normalisers, and adapter base interfaces into an installable sub-package (working name: `sglb-tools` or namespace inside `sglb`). Configure `pyproject` extras. Publish to PyPI under the same licence as the benchmark.
- **Closes via:** `NEW-LIB-PACKAGING` (Tier 3).

### GAP-16 [LOW] Batch D ("frontier baselines") has no detailed prompt

- **Evidence:** `PROMPTS-TO-RUN.md` (pre-rewrite) Tier 1 lists "Batch D" but no per-agent prompts are provided. Implicit dependency on issue #36. The agent firing Batch D would have zero guidance on model selection, receipt format, cost gates, or contamination split.
- **Risk:** the launch story is gated on Batch D, but Batch D cannot fire without contract details. Agents may run incoherent baselines that need to be redone.
- **Remediation:** write a full Batch D prompt — one agent per (provider × task) for {Anthropic, OpenAI, Google, Ollama-local} × {SGLB-01, -02, -04, -08}. Receipt format must include CI fields (GAP-02 closure) and contamination flags (GAP-01 closure) and extraction-rule SHA (GAP-06 closure). Cost gates per `AGENT-RUNBOOK.md` §8. Parallel-safe in separate worktrees.
- **Closes via:** `NEW-BATCH-D` (Tier 1, replaces stub Batch D).

---

## Per-task gaps (carry-forward from spec audit)

### SGLB-01 (PDPA-Outcome)

- **Multi-label treatment:** confirm per-case obligation list is treated as multi-label by `sglb_01_obligations_f1` (`backend/benchmark/evaluators.py:608-639`). Many PDPC decisions cite multiple obligations breached; single-label F1 would silently throw away information.
- **Protection-filter bias:** dataset is ~100% Protection-obligation cases (and ~13% also Accountability). Document in `docs/sglb_specs/SGLB-01.md` §Caveats so users don't read SGLB-01 score as "general PDPA reasoning".
- **Penalty MAE conceptual confusion:** clarify whether `penalty_band_mae` measures "predict the regulator's actual penalty" (current; conflates model reasoning with regulator decision) or "predict the legally-justified penalty band" (a different metric). Recommend renaming to `penalty_band_match_observed` and documenting that the metric reflects regulator behaviour, not legal correctness.

### SGLB-02 (Statute-QA)

- **N=78 PDPA-only vs 500 target:** gated on SSO ingest for EmA1968, ROC2021, PC1871. Tracked as Tier 2 (`NEW-SSO-EXPAND`).
- **ROUGE-L on legal answers is weak:** two correct legal answers can have near-zero lexical overlap. Add a strong supplementary evaluator (exact citation match weighted higher than ROUGE-L, or contains-key-phrase).
- **Question-generation methodology:** spec asserts template-derived from section headings (`"Under the {short_name}, what does the section on "{heading}" provide?"`), confirmed mechanical. Document explicitly in `docs/sglb_specs/SGLB-02.md` §Methodology so vendors don't suspect LLM-generated questions.

### SGLB-03 (Case-Holding)

- **TOS-gated.** Keep `benchmark_eligible=False` at `backend/api/adapters/public/elitigation.py:36`. Defer to v0.2 or remove from v0.1 entirely.
- **If pursued in v0.2:** distractor generation needs the same κ discipline as SGLB-08. Document methodology before any release.

### SGLB-04 (Citation-Verify)

- **Production set deferred (issue #32):** SGLB-04 currently has 30-case smoke; full 1000+ production set is deferred. Per-error breakdown claim in `docs/sglb_specs/SGLB-04.md` is not actually testable at N=30. Tracked as Tier 2 (`NEW-SGLB-04-PROD`).
- **Grammar validation:** GAP-05 is the load-bearing methodology fix.

### SGLB-05 (Employment-Issue)

- **Data-pending (#59):** MOM adapter is stubbed at `backend/api/adapters/public/mom.py`. Closes via Tier 2 Batch A.
- **After data lands:** multi-label F1 needs per-class N ≥ 20 for stable per-class P/R reporting. Document the minimum in the spec.

### SGLB-06 (Rules-of-Court-2021)

- **Data-pending:** SSO ROC2021 ingestion not yet materialised. Builder at `backend/benchmark/dataset_builders/sglb_06.py` is ready. Closes via Tier 2 `NEW-SSO-EXPAND`.
- **Scenario authoring:** confirm scenarios are mechanically derived from rule scope text (per spec), not LLM-generated. Document explicitly.

### SGLB-07 (Jurisdiction-Routing)

- **Data-pending (#34):** CommonLII SG corpus ingestion not yet implemented. Closes via Tier 2 Batch B.
- **B3 jurisdiction extractor is the load-bearing methodology piece:** its regex output is the gold label. Test coverage on B3 must be exceptional (≥12 synthetic cases per label class, per the existing Batch B B3 prompt).

### SGLB-08 (Clause-Tone)

- GAP-07, GAP-08 are the load-bearing fixes.
- If `SOLO-17` produces any κ pair < 0.4, reframe as "Inter-Judge-Alignment" sub-track for v0.1 — the metric is then defensible (it measures judge agreement, not ground truth on tone) and reduces overclaim risk.

---

## Closure-mapping table

| Gap | Severity | Closing prompt(s) | Tier |
|---|---|---|---|
| GAP-01 No contamination probe | BLOCKER | `NEW-CONTAM` | T1 |
| GAP-02 CIs not in receipts | BLOCKER | `NEW-CI-RECEIPT` | T1 |
| GAP-03 Anthropic+Gemini receipts missing | BLOCKER | `NEW-VERIFY-BASELINES` + `NEW-BATCH-D` | T1 |
| GAP-04 Empty tasks score 1.0 | HIGH | `NEW-HONEST-LEADERBOARD` | T1 |
| GAP-05 SAL grammar unvalidated | HIGH | `NEW-SAL-VALIDATION` | T1 |
| GAP-06 No extraction-rule version | HIGH | `NEW-EXTRACT-VERSION` | T1 |
| GAP-07 SGLB-08 κ undefined | HIGH | `SOLO-17` + `NEW-08-REFRAME-IF-LOW-KAPPA` | T1 |
| GAP-08 No human-validated holdout | HIGH | `SOLO-18` (promoted) | T1 |
| GAP-09 No normalisation spec | HIGH | `NEW-NORM-SPEC` | T1 |
| GAP-10 No dispute process | HIGH | `NEW-DISPUTE-PROCESS` | T1 |
| GAP-11 License/name unresolved | MEDIUM | `SOLO-10` (promoted) | T1 |
| GAP-12 No independent reproduction | MEDIUM | `NEW-INDEPENDENT-REPRO` | T3 |
| GAP-13 N too small | MEDIUM | `NEW-CI-RECEIPT` + `NEW-HONEST-LEADERBOARD` + T2 data | T1+T2 |
| GAP-14 No vendor self-eval guide | MEDIUM | `NEW-VENDOR-GUIDE` | T3 |
| GAP-15 No library packaging | MEDIUM | `NEW-LIB-PACKAGING` | T3 |
| GAP-16 Batch D unspecified | LOW | `NEW-BATCH-D` | T1 |

---

## Defensibility scorecard (current vs. post-Tier-1)

| Vendor scrutiny question | Pre-Tier-1 answer | Post-Tier-1 answer |
|---|---|---|
| "What's the N per task and the CI?" | N visible; CI requires post-processing the leaderboard | N + 95% bootstrap CI in every receipt (`NEW-CI-RECEIPT`) |
| "How do I know my model isn't memorising the labels?" | Date-based split only; no probe | Per-case `memorisation_flag` + per-task contamination summary (`NEW-CONTAM`) |
| "How is the SAL citation grammar validated?" | Hardcoded synthetic tests | Tested against every worked example in SAL Quick Ref 2007 + SLR Style Guide 2021 (`NEW-SAL-VALIDATION`) |
| "Can I reproduce a published baseline exactly?" | `dataset_version` string; extraction rule changes silent | `dataset_version` + `extraction_rule_sha` per row (`NEW-EXTRACT-VERSION`) |
| "What if I disagree with a label?" | Unwritten errata process | Public dispute process + issue template + triage SLA (`NEW-DISPUTE-PROCESS`) |
| "Why does SGLB-08 use LLM-judges?" | Single Azure gpt-5 judge, κ undefined | 3-judge ensemble + pairwise + Fleiss' κ, plus 40-case human-validated holdout (`SOLO-17` + `SOLO-18`) |
| "What does the citation/statute normaliser do?" | Read the code | `docs/normalisation-spec.md` with canonical forms + test corpus (`NEW-NORM-SPEC`) |
| "Has anyone else run this benchmark?" | No | Independent reproduction outreach to SMU SOLID / NUS TRAIL / SAL (`NEW-INDEPENDENT-REPRO`, Tier 3) |
| "Why are SGLB-05/06/07 scored at 1.0?" | They have no data | Marked `benchmark_eligible=False`; excluded from leaderboard with explicit footnote (`NEW-HONEST-LEADERBOARD`) |
| "What's the licence and contribution policy?" | "Likely AGPL-3.0 / CC-BY 4.0" | Decided + documented (`SOLO-10`) |
