# SG-LegalBench: A Singapore Legal AI Evaluation Suite with Mechanical Labels and Reproducible Receipts

Target venue: NLLP workshop at EMNLP 2026.

Status: working draft for sections 1-3. Sections 4-5 are intentionally TODO-gated on baseline runs.

## Paper Outline

1. Introduction: motivate SG-LegalBench as vendor-defensibility infrastructure for Singapore legal AI systems, not as a broad failure claim about model competence.
2. Methodology: define the capability surface, source policy, mechanical-label rule, evaluator-strength rule, contamination protocol, bootstrap confidence intervals, dispute process, and receipt format.
3. Tasks: document SGLB-01 through SGLB-16 with input/output contracts, source provenance, extraction rule, scorer, and limitation.
4. Results: TODO after NEW-BATCH-D baseline cells and approved cost-gated runs.
5. Limitations: TODO after baseline receipts, multi-judge agreement, and human-review artefacts are complete.

## Abstract

Singapore legal AI tools need evaluation artefacts that are narrow enough to audit and broad enough to cover the behaviours that vendors claim in practice. We introduce SG-LegalBench, a Singapore-focused legal AI benchmark and reference harness built around public legal sources, deterministic task construction, strong evaluators, and reproducible JSON receipts. The benchmark covers statute question answering, citation handling, outcome prediction, issue spotting, drafting constraints, document review, and source-grounded summarisation across statutes, regulator outputs, procedure rules, contracts, guidance, and case-law scaffolds. Its central methodological rule is that labels should be mechanically derived from published regulator or court outputs wherever possible; where that is not possible, the task is explicitly marked synthetic or provisional and gated by disclosed judge agreement or human review. This draft describes the benchmark motivation, methodology, and task suite. We do not report model rankings yet; results are left for the post-baseline version of the paper.

## 1. Introduction

Singapore legal AI evaluation needs defensible audit infrastructure more than it needs another leaderboard headline. Legal products increasingly claim statute lookup, citation handling, compliance review, contract drafting, and document review capabilities, but a vendor-facing benchmark must let a reviewer inspect exactly what data was used, how each label was obtained, whether a result may reflect memorisation, and how disputes are handled. SG-LegalBench is designed around that narrower claim: it evaluates bounded behaviours on public Singapore legal material with disclosed source provenance, contamination analysis, bootstrap confidence intervals, a published dispute process, and receipt-level reproducibility.

The benchmark deliberately avoids broad failure narratives about model competence. Such claims would be too broad without lawyer-validated task labels, model-specific baseline receipts, and a stable post-cutoff test set. Instead, SG-LegalBench asks a more auditable question: given a specified Singapore legal task, a specified public source, and a specified scorer, what behaviour does a model exhibit and how uncertain is that measurement? This framing makes negative results interpretable without turning them into general claims about legal competence, and it makes strong results inspectable without treating them as legal advice.

Existing legal NLP benchmarks provide useful task families but do not directly solve the Singapore evaluation problem. LegalBench offers a broad legal-reasoning taxonomy and collaborative task format; LexGLUE provides standardised legal NLU classification tasks; LawBench extends legal LLM evaluation to Chinese legal knowledge; SARA isolates statutory entailment in US federal tax law; CUAD demonstrates contract-review extraction; IFEval supplies verifiable instruction-following constraints; FActScore and HaluEval motivate source-grounded factuality and hallucination evaluation. SG-LegalBench borrows these evaluation patterns but changes the jurisdiction, source policy, and label policy: tasks are Singapore-specific, public-source-only, and mechanically extracted where possible.

The core contribution is a benchmark construction protocol rather than a model result. SG-LegalBench maps a nine-capability surface to sixteen task specifications, separates shipped datasets from code-shipped or synthetic scaffolds, and marks each task with its label source, evaluator strength, data tier, and known limitation. The protocol is intended to make it hard to overclaim: a task can be strong because it has regulator-derived labels and deterministic scoring, provisional because it uses a single synthetic judge, or benchmark-ineligible because the real public corpus has not yet landed.

This draft makes three contributions. First, it defines a Singapore legal AI capability surface grounded in product behaviours: statute QA, case retrieval, citation handling, outcome prediction, issue spotting, drafting constraints, document review, faithful summarisation, and multi-step planning. Second, it gives a methodology for converting public Singapore legal sources into evaluation cases with mechanical labels, strong scorers, contamination checks, and JSON receipts. Third, it documents the current SGLB-01 through SGLB-16 task suite, including what each task tests, what it does not test, and what remains gated before leaderboard publication.

## 2. Methodology

### 2.1 Design Principle

We make no legal interpretive claims. We mechanically reformulate published regulator and court outputs as evaluation tasks.

This principle determines what can enter the benchmark. A PDPC task may use the obligation that PDPC itself published; a statute task may use the section text and citation emitted by Singapore Statutes Online; a citation task may use a deterministic Singapore Academy of Law citation grammar; a contract-defect task may use deterministic defect injection. When a task requires author judgement, synthetic generation, or LLM-as-judge labels, the draft marks it as synthetic, provisional, or benchmark-ineligible until the required review protocol is complete.

### 2.2 Capability Surface

SG-LegalBench starts from a product-facing capability surface rather than from an abstract definition of legal reasoning. The in-scope behaviours are: C1 statute QA, C2 case-law retrieval, C3 citation handling, C4 outcome prediction from facts, C5 issue spotting, C6 drafting under constraints, C7 document review, C8 faithful summarisation, and C9 multi-step planning. Version 0.2 covers C1 through C8 directly or through scoped proxies; C9 is deferred because it requires a standardised tool-use trace API.

The task matrix crosses task type, source type, difficulty layer, and capability. It contains classification tasks such as PDPA outcome prediction and jurisdiction routing, extraction tasks such as review red-flag recall, retrieval/extraction tasks such as statute QA, generation tasks such as citation generation and drafting constraints, and reasoning-style tasks such as counterfactual outcome and faithfulness. The matrix intentionally leaves some cells empty: free-form legal strategy, settlement valuation, oral advocacy, witness assessment, billing, conflicts, KYC, non-English material, and private arbitration or mediation records are out of scope.

### 2.3 Source Policy

Every benchmark source must be public, versionable, and redistributable or reconstructable through an open adapter. Current sources include PDPC enforcement decisions, Singapore Statutes Online, Rules of Court 2021 text, MOM public material, PDPC Advisory Guidelines, local SG contract templates, and curated public citation pools. Paywalled LawNet or proprietary practice materials may be useful for a reference copilot but are not benchmark data sources.

Each case carries source metadata. For regulator and statute tasks, this includes source URLs, document IDs, statute version IDs, publication dates, and extraction-rule hashes. For synthetic tasks, this includes the source template, taxonomy, generator, quality metadata, and data-tier flag. For code-shipped tasks with missing live data, the task remains benchmark-ineligible or data-pending until the source corpus is materialised.

### 2.4 Label Extraction

Mechanical label extraction is the default label policy. In SGLB-01, obligation labels are canonicalised from PDPC's published obligation column and penalty bands are derived from PDPC's published financial penalty column. In SGLB-02, citation labels are generated from SSO section identifiers and answer spans are extracted from statute text. In SGLB-04, validity labels come from a deterministic SAL citation parser. In SGLB-06, labels are parsed from Rules of Court Order and Rule identifiers. In SGLB-14, entailment labels are emitted only when a regulator-authored worked example explicitly says that conduct contravenes, complies with, or depends on a section.

When mechanical extraction is unavailable, the benchmark uses explicit safeguards. SGLB-08 is single-judge provisional until multi-judge agreement and human-review artefacts land. SGLB-10 currently ships only a synthetic lookup smoke because CommonLII headnote-derived fact patterns are absent. SGLB-12 and SGLB-15 are synthesis-ready but require reviewed candidate promotion before publication. SGLB-16 uses deterministic defect injection and is benchmark-ineligible until its synthetic nature is accepted for the leaderboard.

### 2.5 Scoring and Evaluator Strength

Publication runs use strong evaluators only. Strong evaluators include exact match after canonical normalisation, deterministic citation grammar parsing, multi-label F1 with per-class detail, top-k citation accuracy, Python constraint satisfaction, span-localised F1, and source-grounded factuality protocols. Weak evaluators such as keyword presence, citation-marker presence, and minimum length remain in the codebase only for migration or smoke tests and are rejected in strict publication mode.

The scorer is part of the benchmark claim. Each result should identify the workflow, dataset version, evaluator name, evaluator strength, scorer code SHA, and any task-specific tolerances. For example, SGLB-16 span matching uses a plus/minus ten-character tolerance, while SGLB-06 normalises common Order/Rule surface forms before F1 and top-3 scoring.

### 2.6 Contamination and Uncertainty

SG-LegalBench treats memorisation as a measurement threat. Where source publication dates support it, a held-out split uses material published after a fixed cutoff, currently 2026-Q1 for planned PDPC and SG judgment expansions. Leaderboard rows should report training-era and post-cutoff scores separately, so a large drop can be interpreted as possible memorisation or source exposure rather than reasoning failure.

Uncertainty is reported with bootstrap confidence intervals. The harness computes per-evaluator bootstrap summaries for each run, and receipts retain per-case scores so downstream reviewers can recompute intervals, stratify by source, and inspect outliers. This draft does not include baseline numbers because the NEW-BATCH-D baseline cells have not yet landed.

### 2.7 Receipts and Disputes

Every run produces a JSON receipt rather than only a scalar score. The receipt records workflow, dataset path, evaluator list, total cases, per-case outputs, per-evaluator scores, strict-mode status, weak evaluator use, data tier, model provenance for LLM-backed runs, contamination probe results when enabled, and bootstrap statistics. LLM-backed runs add prompt version, prompt SHA, provider label, max tokens, and inference configuration.

Disputes are expected. A benchmark user may challenge a source parse, a label derivation, a scorer rule, or a task's inclusion in the public leaderboard. The dispute process should route each challenge to an errata entry, a scorer patch, a dataset minor version, or a task retirement decision. The paper should not present disputed or provisional tasks as settled evidence.

## 3. Task Suite

### 3.1 SGLB-01 PDPA-Outcome

SGLB-01 tests outcome prediction from PDPC enforcement summaries. The input is a mechanically redacted PDPC fact summary, and the output is a JSON object containing breached obligations and a penalty band. Source rows come from the vendored PDPC decision spreadsheet, with obligations copied from PDPC's published taxonomy and penalty bands bucketed from published SGD amounts. The primary scorers are `sglb_01_obligations_f1` and `penalty_band_mae`. The main limitation is source skew: the upstream scraper is protection-obligation-heavy, so the task measures alignment to PDPC-published outcomes more than broad PDPA reasoning.

### 3.2 SGLB-02 Statute-QA

SGLB-02 tests statute-grounded question answering. The input is a natural-language question plus an Act short and full name; the output is a JSON object with a section citation and answer. Source rows come from Singapore Statutes Online through the SSO ingestion pipeline, including PDPA, Employment Act, Penal Code, and Rules of Court 2021 material. The citation scorer is `sglb_02_citation_match`, and the answer proxy is `rouge_l_answer`. The limitation is that questions are mechanically templated and answer scoring is only a surface proxy, so the citation metric is the primary defensible signal.

### 3.3 SGLB-03 Case-Holding

SGLB-03 is a draft case-holding task. The intended input is a fact pattern, question presented, and four candidate holdings; the output is the selected holding index. The source plan is eLitigation or CommonLII Singapore judgments, with holdings extracted from judgment text and same-category distractors. The scorer is exact match over the selected index. The task is not yet benchmark-ready because the public case corpus and holding extraction pipeline are not materialised, and the spec still requires hand audit for holding quality.

### 3.4 SGLB-04 Citation-Verify

SGLB-04 tests SAL citation grammar verification. The input is a candidate Singapore legal citation, and the output is `["valid"]` or `["invalid"]`. The dataset is generated from the deterministic citation grammar implementation plus perturbations such as year, volume, page, case name, court, wholesale fabrication, and composite errors. The scorer is `multi_label_f1` over the single validity label, with detailed metadata for error strata. The key limitation is that grammar conformance is not existence verification; SGLB-11 covers existence-oriented citation hallucination.

### 3.5 SGLB-05 Employment-Issue

SGLB-05 tests employment issue spotting. The input is an employer-employee dispute scenario, and the output is a JSON list of MOM or Employment Act issue labels. The intended source is MOM public material with stated breaches, act references, subject organisation, and publication date. The scorer is `multi_label_f1`. The task is code-shipped but data-pending because the live MOM ingest has not been fired; it should remain non-public until `vendor-data/mom/enforcement.jsonl` and a production YAML are materialised.

### 3.6 SGLB-06 Rules-of-Court-2021

SGLB-06 tests procedural issue spotting under the Rules of Court 2021. The input is a procedural scenario built from a Rule's own scope text, and the output is a JSON list of `O. <N>, r. <M>` labels ordered by relevance. Source rows come from the SSO Rules of Court 2021 supplement, with labels parsed from Order headers and rule numbers. The scorers are `order_rule_label_f1` and `order_rule_top3`. The limitation is that v0.1 scenarios are mechanically authored from rule text and generally single-label.

### 3.7 SGLB-07 Jurisdiction-Routing

SGLB-07 tests source-jurisdiction classification for Singapore case-law questions. The input is a legal question or catchwords-derived prompt, and the output is one of `sg_binding`, `uk_persuasive`, `au_persuasive`, `hk_persuasive`, or `not_applicable`. The intended source is CommonLII SG judgment text with regex-extracted jurisdiction statements. The scorer is `multi_label_f1`. The task is code-shipped but data-pending because the CommonLII SG corpus has not landed; multi-source cases are excluded from v0.1.

### 3.8 SGLB-08 Clause-Tone

SGLB-08 tests clause-tone classification as a weak proxy for drafting behaviour. The input is a contract clause and clause type, and the output is one of `standard`, `aggressive`, `balanced`, or `protective`. The current dataset contains 400 reviewed synthetic cases generated from the SG clause library and tone taxonomy. The scorer is `multi_label_f1`, but the methodology requires multi-judge agreement and human spot-checking before the task is treated as publication-grade. The limitation is fundamental: tone is subjective and not mechanically published by a regulator.

### 3.9 SGLB-09 Summary-Faithfulness

SGLB-09 is a draft faithfulness task. The input is an SG legal source document and a prompt type; the model output is a bounded summary. The intended scorer decomposes the summary into atomic claims and judges each claim as supported, contradicted, or unsupported against the source, following FActScore-style factual precision. The source plan includes judgments, PDPC decisions, and MOM advisories. The task is not yet shipped because it depends on source corpora, LLM-judge agreement, and a hand-checked extraction sample.

### 3.10 SGLB-10 Citation-Generation

SGLB-10 tests citation generation. The input is an SG legal scenario, and the output is a JSON list of up to three citation strings ordered by relevance. The current v0.1 smoke uses the existing curated real SG citation pool from SGLB-11, selects cases by deterministic domain round-robin, and copies the gold citation mechanically from the curated row. The scorers are `citation_generation_top1` and `citation_generation_top3`. The task is benchmark-ineligible in its current form because the fact patterns are synthetic lookup prompts; production requires CommonLII or eLitigation headnote-derived fact patterns.

### 3.11 SGLB-11 Citation-Hallucination

SGLB-11 tests citation hallucination detection. The input is a passage containing real and perturbed fake Singapore citations, and the output is a JSON list of citations flagged as fabricated. Real citations come from a curated SG case pool; fake citations are generated by deterministic perturbations with collision checks against the real pool. The scorer is `citation_hallucination_f1`, with per-perturbation detail and false-positive-on-real tracking. The limitation is that web-enabled models can solve the task by lookup, so closed-book settings and web-access flags matter.

### 3.12 SGLB-12 Multi-Issue-Spotting

SGLB-12 is a synthesis-ready multi-issue spotting task. The input is a compound Singapore fact pattern across PDPA, Employment Act, and Rules of Court issues, and the output is a JSON list of issue labels. The planned source pipeline composes atomic scenarios with fixed labels from a declared taxonomy and validates candidate cases before promotion. The scorer is `multi_label_f1`, with macro, micro, and exact-set-match reporting planned. The limitation is synthetic realism: compound scenarios may not reflect natural legal requests until human review and source-derived variants land.

### 3.13 SGLB-13 Counterfactual-Outcome

SGLB-13 tests counterfactual outcome sensitivity. The implemented task takes an original PDPC fact pattern and a perturbation with one obligation-cue fact excised, then predicts whether the enforcement outcome changes. The gold label is mechanically derived from PDPC's published obligation count: removing the sole obligation cue changes the outcome, while removing one cue from a multi-obligation case does not. The scorer is `sglb_13_outcome_accuracy`. The spec currently describes an older `fact_pattern_a`/`fact_pattern_b` plus justification contract; that inconsistency should be resolved before submission.

### 3.14 SGLB-14 Statutory-Entailment

SGLB-14 tests statutory entailment over regulator-authored worked examples. The input is a statute section and conduct text; the output is `{"entailment": "contravenes"}`, `{"entailment": "complies"}`, or `{"entailment": "indeterminate"}`. The builder emits cases only when PDPC guideline text explicitly states the entailment relation near the section reference. The scorer is `sglb_14_entailment_accuracy`. The live PDPC Advisory Guidelines audit found only one strict section-level case, so the production dataset is not promoted.

### 3.15 SGLB-15 Draft-Constraint-Sat

SGLB-15 is a synthesis-ready drafting constraint task. The input is a drafting brief plus verifiable constraints, and the output is a Markdown document. Constraints include named-party presence, Singapore governing law, valid citation format, required sections, minimum word count, ISO dates, SGD amounts, and forbidden phrases. The scorer is `constraint_sat`, which runs Python functions rather than LLM judges. The limitation is that constraint satisfaction does not measure drafting quality; a model can satisfy structural checks while producing poor prose.

### 3.16 SGLB-16 Review-Redflag-Recall

SGLB-16 tests document review over planted contract defects. The input is an SG-context contract with deterministic defects, and the output is a JSON list of defect type and span offsets. Base contracts come from local SG templates, a clean review-clause bundle is appended, and defects are planted by block deletion or phrase replacement. The scorer is `sglb_16_redflag_f1`, matching defect type and span endpoints within a plus/minus ten-character tolerance. The limitation is distributional realism: planted defects and zero-width missing-clause anchors are easier to score than naturally negotiated contract issues.

## 4. Results

TODO after NEW-BATCH-D baseline cells, approved Azure/Ollama runs, and any required multi-judge or human-review gates land.

The results section should include:

- model and provider table with dates, temperatures, max tokens, and prompt versions;
- per-task headline scores with 95% bootstrap confidence intervals;
- train/dev versus post-cutoff held-out comparison where available;
- per-stratum breakdowns for citation perturbations, Order/Rule labels, domains, obligations, and defect classes;
- refusal and malformed-output rates for generation tasks;
- receipt links or paths for every reported row.

## 5. Limitations

TODO after baseline receipts are available.

Expected limitation themes:

- SG-LegalBench evaluates bounded behaviours, not legal advice or lawyer-equivalent reasoning.
- Several tasks are code-shipped, synthetic, provisional, or data-pending rather than publication-grade.
- Public Singapore legal sources are uneven across practice areas.
- Mechanical labels reflect regulator or court publication frames, not normative truth.
- Some generation and document-review tasks score verifiable structure rather than legal quality.
- Citation and case-law tasks depend on CommonLII/eLitigation materialisation for production-grade coverage.

## Drafting Self-Review

Contribution: pass for sections 1-3. The draft states a benchmark construction and audit contribution, not model superiority.

Writing clarity: pass with one caveat. Section 3 is intentionally dense because each task needs source, extraction, scoring, and limitation.

Experimental strength: needs new evidence. No model results are reported; section 4 is gated on baseline receipts.

Evaluation completeness: needs new evidence. Multi-judge and human-review gates remain open for SGLB-08, SGLB-09, SGLB-12, and SGLB-15.

Method design soundness: pass for mechanical-label tasks; provisional for synthetic and judge-based tasks as marked.

## Claim-Evidence Map

Claim: SG-LegalBench is designed as defensible audit infrastructure rather than a broad legal-reasoning claim. Evidence: coverage matrix sections 1, 4, and 5; this draft's sections 1 and 2. Status: supported.

Claim: Labels are mechanically derived wherever possible. Evidence: SGLB-01, SGLB-02, SGLB-04, SGLB-06, SGLB-13, SGLB-14, and SGLB-16 task descriptions and builders. Status: supported.

Claim: Some tasks are provisional or benchmark-ineligible. Evidence: SGLB-08 multi-judge caveat, SGLB-10 smoke status, SGLB-14 live audit, SGLB-16 synthetic status, and registry eligibility flags. Status: supported.

Claim: The paper can report model performance. Evidence: not yet available. Status: needs evidence; section 4 remains TODO.

Claim: SG-LegalBench covers all Singapore legal AI behaviours. Evidence: none. Status: unsupported and intentionally not claimed.

## Working References

- Guha et al. LegalBench: A Collaboratively Built Benchmark for Measuring Legal Reasoning in Large Language Models. NeurIPS 2023.
- Chalkidis et al. LexGLUE: A Benchmark Dataset for Legal Language Understanding in English. ACL 2022.
- Fei et al. LawBench: Benchmarking Legal Knowledge of Large Language Models. EMNLP 2024.
- Holzenberger, Blair-Stanek, and Van Durme. A Dataset for Statutory Reasoning in Tax Law Entailment and Question Answering. NLLP 2020.
- Hendrycks, Burns, Chen, and Ball. CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review. NeurIPS 2021.
- Zhou et al. Instruction-Following Evaluation for Large Language Models. 2023.
- Min et al. FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation. EMNLP 2023.
- Li et al. HaluEval: A Large-Scale Hallucination Evaluation Benchmark for Large Language Models. EMNLP 2023.
- Dahl et al. Large Legal Fictions: Profiling Legal Hallucinations in Large Language Models. Journal of Legal Analysis 2024.
