# SG-LegalBench Coverage Matrix

> Source of truth for what SG-LegalBench evaluates, what it does not, and why
> each task is in scope. This document is the §2 of the planned arXiv preprint
> and the reviewer-rebuttal cheat sheet.

Version: 0.2-draft (2026-06-03). Tracks intended v0.2 scope. Items not marked
"shipped" are spec-only until issue resolution.

---

## 1. Purpose

SG-LegalBench measures whether an LLM can do the work that practising
Singapore legal AI tools claim to do, on public-domain Singapore legal
material, using evaluators that resist gaming by surface-form matching.

We do not claim to evaluate "legal reasoning" in the abstract. We evaluate
concrete behaviours on bounded datasets with documented limitations.

## 2. Capability surface

The benchmark's coverage target is the set of legal-reasoning capabilities
exposed by production SG-focused legal AI assistants. Drawing the surface from
deployed tools (not from a wishlist) keeps the benchmark grounded in things
vendors actually ship.

Nine capabilities form the in-scope surface:

| # | Capability | What the model must do |
|---|---|---|
| C1 | Statute QA | Answer a question grounded in a SG statute section; return the answer and the citation |
| C2 | Case-law retrieval | Surface relevant SG judgments for a query, with citations resolvable to public sources |
| C3 | Citation handling | Generate or verify SAL-format citations correctly; detect hallucinated citations |
| C4 | Outcome prediction from facts | Given a fact pattern and a regulatory frame, predict the obligation breached and the band of penalty |
| C5 | Issue spotting | Multi-label identification of which legal issues a fact pattern triggers |
| C6 | Drafting under constraints | Produce SG-context legal text that satisfies enumerable hard requirements |
| C7 | Document review | Identify planted defects in a contract or document |
| C8 | Faithful summarisation | Summarise SG legal material without introducing claims absent from the source |
| C9 | Multi-step planning | Decompose a compound legal request into an ordered tool sequence |

**Out of scope** (documented to bound credibility claims):

- Tactical legal strategy, settlement valuation, oral advocacy.
- Subjective writing quality (IRAC structure grading, persuasiveness).
- Fact-finding under adversarial conditions, witness assessment.
- Billing, conflicts, matter management, KYC.
- Non-English material, pre-2010 enforcement decisions, classified material.
- Practice areas where SG public sources are thin: arbitration awards (most
  unpublished), private mediation, tax rulings before IRAS publication.

## 3. The 3-axis coverage matrix

A task is in scope if it occupies a defensible cell across three axes drawn
from the legal NLP literature:

- **Task type:** `retrieval | classification | extraction | generation | reasoning`
- **Source type:** `statute | case | regulation | procedure | contract | guidance`
- **Difficulty layer** (from Guha et al., LegalBench, NeurIPS 2023, IRAC
  decomposition): `recall | application | interpretation | conclusion |
  multi-rule synthesis`

| Task ID | Task type | Source type | Difficulty | Capability |
|---|---|---|---|---|
| SGLB-01 PDPA-Outcome | classification | guidance | conclusion | C4 |
| SGLB-02 Statute-QA | retrieval + extraction | statute | recall + application | C1 |
| SGLB-03 Case-Holding | classification | case | interpretation | C2 |
| SGLB-04 Citation-Verify | classification | citation grammar | recall | C3 |
| SGLB-05 Employment-Issue | classification (multi-label) | regulation | application | C5 |
| SGLB-06 ROC-2021 | classification | procedure | application | C5 |
| SGLB-07 Jurisdiction-Routing | classification | case | interpretation | C2 |
| SGLB-08 Clause-Tone | classification | contract | interpretation | (weak) C6 proxy |
| SGLB-09 Summary-Faithfulness | generation + reasoning | case + guidance | application | C8 |
| SGLB-10 Citation-Generation | generation | case + statute | recall + application | C3 |
| SGLB-11 Citation-Hallucination | classification | case | recall | C3 |
| SGLB-12 Multi-Issue-Spotting | classification (multi-label) | case + contract + guidance | multi-rule synthesis | C5 |
| SGLB-13 Counterfactual-Outcome | reasoning | guidance | multi-rule synthesis | C4 |
| SGLB-14 Statutory-Entailment | classification | statute | interpretation | C1 |
| SGLB-15 Draft-Constraint-Sat | generation | contract | application | C6 |
| SGLB-16 Review-Redflag-Recall | extraction + classification | contract | application | C7 |

Empty cells in the matrix are intentional. We do not test free-form "legal
reasoning" with no ground truth, we do not test C9 in v0.2 (deferred —
see §7), and we do not test multi-turn dialogue.

## 4. Methodology pillars

Four commitments load-bear the benchmark's credibility. Each is enforced at
the task level.

### 4.1 Mechanical label extraction

Every label derives from a public regulator or court output by an
extractable rule, not by author legal judgment. Worked examples:

- PDPA outcome (C4): label = the obligation named in PDPC's published
  finding; penalty band = log-bucketed SGD figure from the same finding.
- Statute citation (C3): label validity = grammar match against the SAL
  citation rules (a deterministic parser).
- Statutory entailment (C1): label = the entailment relation explicitly
  stated in PDPC/MOM/IRAS published worked examples ("the conduct described
  contravenes section X"). We exclude examples that require judgment.

This is the load-bearing methodological commitment. It substitutes for the
absent lawyer-credentials review board. The paper's §2 reads: **"We make no
legal interpretive claims. We mechanically reformulate published regulator
and court outputs as evaluation tasks."**

Where mechanical extraction is impossible (faithfulness, tone, hallucination
detection), we use LLM-as-judge **only** with the following discipline:
ensemble of ≥3 frontier judges, disclosed prompts, reported inter-judge
agreement (Cohen's κ), and a human-spot-checked held-out subset.

### 4.2 Evaluator strength

We do not use the following evaluators that appear in adjacent SG legal-AI
tooling:

- "Output contains the keyword X" — satisfied by hallucinated answers.
- "Output contains any of `[Act, Section, [, ], SGHC, SGCA, Cap., s.]`" —
  trivially passes on any plausible string.
- "Output length > N characters" — non-evaluative.

We use:

- Exact-match on extracted spans (regex-bounded).
- SAL citation grammar parsing (deterministic).
- Multi-label F1 with reported per-class precision/recall.
- LLM-judge ensembles with disclosed agreement metrics.
- Constraint satisfaction via verifiable Python functions (IFEval-style;
  Zhou et al., 2023).
- FActScore-style atomic-fact decomposition with source-grounded support
  (Min et al., EMNLP 2023).

### 4.3 Contamination resistance

A held-out test split uses only material published after a fixed cutoff
(2026-Q1 for PDPC decisions, 2026-Q1 for new SGHC/SGCA judgments). Each
leaderboard row reports two scores: training-era and post-cutoff. A model
whose post-cutoff score is materially lower than training-era is memorising,
not reasoning. This single result is the strongest defensible claim the
benchmark makes about generalisation.

### 4.4 Reproducibility receipts

Every leaderboard row records: dataset version, model version (date or
checkpoint), inference temperature + seed, prompt template, scorer code git
SHA, batch size, max tokens. Receipts are stored as JSON next to the
leaderboard CSV and are submission requirements for community runs.

## 5. Anti-snake-oil checklist

Claims we will not make in the README, paper, or any launch material:

| Forbidden phrasing | Allowed substitute |
|---|---|
| "evaluates legal reasoning" | "evaluates [behaviour] on [dataset]" |
| "comprehensive SG legal coverage" | "covers M of K capabilities, L of N obligation categories" |
| "production-grade" | "research-grade, pre-release" |
| "lawyer-validated" | "labels mechanically extracted from regulator outputs" |
| "tests AI safety in law" | "tests citation hallucination on N held-out SG citations" |
| "beats GPT-X on legal tasks" | "scores X.XX vs Y.YY on SGLB-NN (95% CI)" |
| silence on limitations | explicit §3 limitations block in every artefact |

## 6. Reproducibility expectations

The eval CLI (issue #31) must, for every run:

1. Pin all dependency versions in a lockfile.
2. Record model + dataset + scorer SHAs.
3. Emit a single JSON receipt that uniquely identifies the run.
4. Refuse to overwrite a prior receipt without explicit `--force`.
5. Be invocable without network access once the dataset is materialised.

## 7. Deferred to v0.3

These are real targets that we explicitly defer to keep v0.2 shippable:

- C9 (multi-step planning) — tool-use trace evaluation requires a
  standardised tool API not yet specified in the spec.
- Hansard-grounded statutory interpretation — depends on hansardscraper
  productionisation.
- IRAS tax ruling reasoning — useful but narrow; defer to v0.3 to keep v0.2
  scope honest.
- Multi-turn legal dialogue — requires conversational dataset; out of scope
  for a single-turn benchmark.

## 8. Risk register

Threats to the benchmark's defensibility, with mitigations:

| Risk | Likelihood | Mitigation |
|---|---|---|
| Models memorise our datasets | High | Post-cutoff held-out split (§4.3); rotation each version |
| Labels reflect regulator bias rather than legal truth | High | §1 explicit framing: we test alignment to published outcomes, not normative correctness |
| Single-author bias in task design | Medium | Pre-launch review by SAL tech committee + SMU SOLID team + ≥2 SG legal-tech engineers |
| Vendor gaming through prompt-specific tuning | Medium | Disclosed prompts; any vendor-tuned prompt must be published |
| Citation grammar parser misses edge cases | Medium | Public errata + versioning; PRs accepted from any user |
| LLM-judge variance dominates result | High for SGLB-08, SGLB-09 | ≥3 judges, disclosed κ; drop task if κ < 0.4 sustained |
| Public dataset is not sufficient for some tasks | Medium | Acknowledge in README; do not synthesise tasks to fill gaps |

## 9. Comparison to adjacent benchmarks

| Benchmark | Coverage | What we borrow | What we diverge on |
|---|---|---|---|
| LegalBench (Guha et al., NeurIPS 2023) | 162 tasks, US-centric, IRAC | Difficulty axis, issue-spotting + rule-application formats | SG-specific source, mechanical extraction, smaller curated v0.1 |
| LexGLUE (Chalkidis et al., ACL 2022) | 7 tasks, US + EU | Multi-label F1 protocol | SG-only; we add generation tasks |
| LawBench (Fei et al., 2024) | Chinese law, 20 tasks | Statutory recall + reasoning split | SG-specific; English-only |
| LEXam (2024) | Bar exam reasoning | IRAC scoring rubric | We avoid scoring legal essays directly (subjectivity) |
| SARA (Holzenberger et al., 2020) | US federal tax, statutory entailment | Statutory entailment task format | SG-PDPA / Employment Act source |
| CUAD (Hendrycks et al., NeurIPS 2021) | 500 contracts, 41 clause types | Planted-issue extraction methodology | SG-applicable contract templates only; mechanical defect injection |
| FActScore (Min et al., EMNLP 2023) | Long-form factuality | Atomic-fact decomposition + source-grounded support | SG legal sources as the knowledge base |
| IFEval (Zhou et al., 2023) | General instruction-following | Verifiable Python constraint functions | SG-context drafting constraints |
| HaluEval (Li et al., 2023); Dahl et al. (2024) | Hallucination | Injection methodology for fake citations | SG citation grammar; SG-specific case identifiers |

## 10. Maintenance protocol

- Releases follow semver: `v0.MAJOR.MINOR`. Major bumps require dataset
  changes; minor bumps may fix scorer bugs only.
- Each release ships a `CHANGELOG.md` entry per task touched.
- Errata accepted as PRs against `data/sglb_NN/errata.md`. Errata are
  applied at the next minor release with attribution.
- Tasks may be retired if (a) sustained inter-judge κ < 0.4 or (b)
  contamination renders post-cutoff scores indistinguishable from random.
