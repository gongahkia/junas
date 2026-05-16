# WORKON-PIVOT-ASAP

Date: 2026-05-16
Owner: gongahkia (solo)
Status: pivot decided, not yet executed

## 0. TL;DR

Pivot junas from "broad multi-jurisdiction legal AI desktop+web platform" to **SG-LegalBench: an open benchmark for Singapore legal reasoning in LLMs, plus a minimal reference copilot**.

- Lead artifact: SG-LegalBench (dataset + eval CLI + arXiv preprint).
- Secondary artifact: SG-tuned reference copilot built on the same backend.
- Goal: GitHub stars + HN frontpage + legal-tech career capital, with research-grade defensibility.
- Constraint: solo dev, no lawyer credentials, AGPL/MIT acceptable, SG-only scope, public-domain data only for the benchmark.
- Anti-goal: do not chase BigLaw revenue, do not duplicate Mike OSS, do not preserve the broad feature surface.

## 1. Why this shape

[Inference] Three findings drove the pivot:

1. **The OSS legal AI copilot slot for this cycle is occupied.** Mike OSS (willchen96/mike) launched 2026-05-04, hit 3,000 stars / 877 forks in ~12 days, AGPL-3.0, BYOK, Next.js+Express, Anthropic/Gemini/OpenAI. Press: Artificial Lawyer, Legal IT Insider, Legal Futures, Legal Cheek. Ex-Latham founder narrative. A second "OSS legal copilot" launch is derivative.
2. **No SG-specific legal LLM benchmark exists.** LegalBench (Stanford, NeurIPS 2023) is US, LexGLUE is US+EU, LawBench is Chinese law, LEXam covers exam reasoning. SG is a clean gap.
3. **SMU + MinLaw are building SOLID** (Singapore Open Legal Informatics Database), early iteration Q4 2026, full Q1 2028. The official open SG legal data train is coming. Junas can position as the **downstream evaluation suite** that SOLID lacks.

Junas's existing assets fit the benchmark thesis better than the copilot thesis: hybrid retrieval (BM25+dense+cross-encoder), LexGLUE harness, contract classifier, NER, multi-jurisdiction registry, compliance rules. These are eval-infra-shaped, not product-shaped.

## 2. Thesis & positioning

- *Tagline:* "The first open benchmark for Singapore legal reasoning in LLMs, with a reproducible reference implementation."
- *Audience priority:* (1) ML researchers / legal-NLP community, (2) SG legal-tech engineers, (3) SG lawyers (last, downstream of benchmark traction).
- *Category:* evaluation infrastructure, not product. Stars come from researchers and engineers, not lawyers.
- *Distribution channels:* arXiv cs.CL, GitHub, HN Show HN, NLLP Workshop submission, SAL / SMU SOLID team / NUS TRAIL outreach, LinkedIn SG legal-tech community.

## 3. Scope: keep / refocus / delete (file-level)

### 3.1 Delete outright

| Path | Reason |
|---|---|
| `src/` | Legacy Tauri renderer. Already slated for removal in `FOR-CLAUDE-TODO.md` Phase 4. |
| `src-tauri/` | Same. |
| `backend/api/routers/predictions.py` | SCOTUS/ECtHR/CaseHOLD/EUR-LEX prediction — non-SG. |
| `backend/api/services/court_predictor.py` | Same. |
| `frontend/app/predictions/` | Same. |
| `backend/api/routers/rome_statute.py` | ICC — non-SG. |
| `backend/api/services/rome_statute.py` | Same. |
| `frontend/app/rome-statute/` | Same. |
| `frontend/app/compare-jurisdictions/` | Multi-jurisdiction comparison — out of scope. |
| `frontend/app/benchmarks/` (current LexGLUE UI) | Will be rebuilt for SG-LegalBench. |
| `backend/api/services/benchmarks.py` (LexGLUE harness) | Same — rewrite. |
| Tauri-only deps in `package.json` (`@tauri-apps/*`, related) | Remove with Tauri stack. |
| `docker-compose.yml` Elasticsearch service (if not used) | Audit; keep only what serves SG retrieval. |

### 3.2 Refocus to SG

| Path | Refocus to |
|---|---|
| `backend/api/services/statute_lookup.py` | SSO-only via integrated `sgstatutescraper` ingestion. Drop non-SG statute paths. |
| `backend/api/services/case_retrieval.py` | SG corpus only (CommonLII SG + eLitigation public judgments + AustLII SG). Keep hybrid BM25+dense+reranker pipeline as-is — this is the highest-leverage existing asset. |
| `backend/api/services/compliance_service.py` | PDPA + Employment Act + Rules of Court 2021 only. Drop multi-jurisdiction routing. |
| `backend/api/services/clause_service.py` | SG clauses only (already the 6 SG clauses are the seed). |
| `backend/api/services/template_service.py` | SG templates only (already 6 SG templates). |
| `backend/api/services/entity_extractor.py` | SG legal entities only: parties, statutes (with section refs), case citations (`[YYYY] SGXX n`), judges, dates, monetary amounts in SGD. Drop multilingual generic NER. |
| `backend/api/services/citation_verifier.py` | Rewrite around `sal-citation-generator` logic (SAL Style Guide). |
| `backend/api/services/jurisdiction_registry.py` | Collapse to SG only. Keep registry pattern for future commonwealth adjacency (MY) but do not implement now. |
| `backend/api/routers/benchmarks.py` | Replace LexGLUE handlers with SG-LegalBench task handlers. |
| `frontend/app/page.tsx` | New landing: benchmark leaderboard front-and-center; copilot below. |
| `frontend/app/benchmarks/` | Rebuild as SG-LegalBench leaderboard + per-task pages. |
| `README.md` (locked per `FOR-CLAUDE-TODO.md` rule) | Do not edit. |
| `README2.md` | Rewrite to lead with SG-LegalBench thesis, copilot secondary. |

### 3.3 Keep as-is (already aligned)

- `backend/api/services/chat_service.py` (BYOK chat, multi-provider) — required for copilot.
- `backend/api/services/llm_client.py` — required for eval runs across providers.
- `backend/api/services/document_parser.py` — required for both benchmark ingestion and copilot.
- `backend/api/services/glossary_lookup.py` — SG terms; useful as one benchmark task source.
- `backend/api/services/tos_scanner.py` — keep for SG-Contract-Clause tasks.
- `backend/api/services/contract_classifier.py` — LEDGAR-trained, multi-jurisdictional but reusable for SG contract clause classification. Keep with retraining caveat.

## 4. SG-LegalBench v0.1 task spec

Eight initial tasks. All grounded in public-domain SG sources. Each task ships with: spec (markdown), JSONL dataset, scorer, baseline numbers across ≥4 frontier models (GPT-5, Claude 4.x, Gemini 2.x, Llama 3 or Qwen 3 as open-weight baseline).

| Task | Source data | N (target) | Format | Metric |
|---|---|---|---|---|
| **SGLB-01 PDPA-Outcome** | PDPC enforcement decisions via `pdpcscraper` (211 rows) | ~180 train / ~30 held-out | given facts → predict obligation breached + penalty band | macro-F1 (obligation), MAE (penalty log-band) |
| **SGLB-02 Statute-QA** | SSO statutes via `sgstatutescraper` | ~500 | question grounded in statute section → answer + correct section citation | exact-match (citation), ROUGE-L (answer) |
| **SGLB-03 Case-Holding** | eLitigation public judgments (TOS-gated, see §9) | ~300 | given facts + question presented → holding | exact-match on multiple-choice holding selection |
| **SGLB-04 Citation-Verify** | `sal-citation-generator` parser + perturbations | ~1000 | input string → valid SAL-style citation? | accuracy + per-error-class breakdown |
| **SGLB-05 Employment-Issue** | MOM published guidance + Employment Act sections | ~150 | scenario → list of EA issues triggered | multi-label F1 |
| **SGLB-06 Rules-of-Court-2021** | Rules of Court 2021 (Subsidiary Legislation, SSO) | ~200 | procedural scenario → applicable Order + Rule | exact-match (order:rule), top-3 accuracy |
| **SGLB-07 Jurisdiction-Routing** | Curated SG cases citing UK/AU/HK precedent + neutral SG cases | ~250 | given question → SG / UK persuasive / AU persuasive / not-applicable | accuracy |
| **SGLB-08 Clause-Tone** | Junas existing SG clause library + LLM-judge augmentation | ~400 | clause text → tone (standard / aggressive / balanced / protective) | macro-F1 |

Reserve task slots SGLB-09 / SGLB-10 for Hansard-grounded statutory interpretation (Phase 2, requires `hansardscraper`) and IRAS Tax Ruling reasoning (Phase 2).

### 4.1 Labeling provenance — the credibility substitute

Every label must derive from a public regulator/court source by **mechanical extraction**, not by author legal judgment. This is the load-bearing methodological commitment.

- PDPA outcomes: pulled from PDPC's own published findings.
- Statute QA: derived from SSO section headings and content, not paraphrased.
- Case holdings: extracted from the "Holding" / catchwords sections of published judgments.
- Citation validity: derived mechanically from the SAL Style Guide grammar.
- Employment issues: tagged using MOM's own published issue taxonomy.
- ROC 2021: derived from the Rule's own scope text.
- Jurisdiction routing: derived from explicit court statements about precedent applicability.
- Clause tone: bootstrap with LLM-judge across ≥3 frontier models with explicit disclosure; held-out subset spot-checked.

The paper's methodology section must lead with this framing: **"We make no legal interpretive claims. We mechanically reformulate published regulator and court outputs as evaluation tasks."** This is the academically-defensible move that bypasses the lawyer-credentials gap (see §10).

## 5. Reference copilot — minimal scope

The copilot exists to demonstrate the benchmark, not to replace Mike OSS or Harvey. Minimal feature set:

- BYOK chat (already exists, keep).
- SG statute + case retrieval (refocused from existing pipeline).
- Citation verifier in chat output (SAL Style Guide).
- PDPA + Employment Act compliance checker (refocused from existing).
- SG clause + template library (already exists, keep).
- Document parsing for PDF/DOCX (already exists, keep).
- Adapter plug system for external sources (Phase 2, §7).

Explicitly **not** in scope: matter management, Word add-in, multi-user collaboration, billing, agent orchestration, court-prediction UI. Each of those is a feature-tag trap.

## 6. kevanwee repo integration plan

### Phase 1 (essential, integrate before benchmark v0.1 ships)

**`pdpcscraper`** → most valuable of the nine.
- Port to `backend/data/ingestion/pdpc.py`.
- Convert Excel output into `data/benchmarks/sglb_01_pdpa/{train,dev,test}.jsonl`.
- Wire into `make ingest-all` and `make ingest-pdpc`.
- License: MIT, compatible.

**`sgstatutescraper`** → SSO ingestion.
- Port to `backend/data/ingestion/sso.py`.
- Add hardening: rate-limiting per AGC ToS, retry logic, version-pinning of statute revisions.
- Output: act → part → division → section JSONL with stable IDs.
- Wire into `case_retrieval.py` index build + `statute_lookup.py` source.
- Caveat: source repo is WIP (2 commits). Expect ~2–3x rewrite for production reliability.

**`sal-citation-generator`** → citation verifier core.
- Port logic to Python at `backend/api/services/sal_citation.py` (parser + formatter + supra/ibid/id tracking).
- Backend reusability is non-negotiable for the eval CLI; do not keep this TS-only.
- Becomes both benchmark task SGLB-04 scorer and copilot chat-output formatter.
- License: MIT.

**`elitiscraper`** → SG case corpus, with TOS gating.
- Do **not** integrate verbatim. First, do a TOS pass on eLitigation; second, restrict to confirmed-public-domain endpoints (free judgment HTML, no authenticated routes); third, document the source provenance per case.
- If the TOS pass fails or is ambiguous: defer integration; ship benchmark v0.1 with CommonLII-only case data; add a `--user-supplied-corpus` flag so users with their own LawNet subscription can plug in their downloads locally.
- Long-term path: apply for SAL/LawNet partner data feed.

### Phase 2 (after benchmark v0.1 ships)

**`hansardscraper`** → only if a Hansard-grounded benchmark task is designed (SGLB-09 candidate: statutory interpretation via legislative history, grounded in Interpretation Act s 9A). Do not integrate as generic "Hansard search" — that's feature-tagging.

### Phase 3 (copilot polish only)

**`sightstone`** → clause harmonization across multiple uploaded contracts.
- Only build if real users (post-launch) ask for it.
- Distinct from existing junas clause library (single-clause, template-based vs cross-contract harmonization).
- Would surface as a copilot workflow, not a benchmark task.

### Rejected (would be feature-tagging)

- **`citation_extraction`** — Neo4j snapshot of EurLex fiscal state-aid academic paper. Wrong domain.
- **`lexlynx`** — Generic GPT-4 PDF summarizer. Duplicates existing junas RAG + chat.
- **`copycat`** — Content-similarity copyright triage. Different problem domain (content moderation), not legal reasoning.

## 7. Adapter architecture for paywalled / authenticated sources

To address the "real implementation includes paywalled services" goal without breaking the benchmark's public-domain rigor:

```
backend/api/adapters/
├── base.py                     # LegalSourceAdapter protocol
├── public/
│   ├── sso.py                  # AGC, free
│   ├── commonlii_sg.py         # AustLII-hosted, free
│   ├── elitigation.py          # TOS-gated, free public endpoints only
│   ├── pdpc.py                 # PDPC, free
│   ├── iras.py                 # IRAS public e-Tax guides + rulings
│   ├── mom.py                  # MOM guidance
│   ├── hansard.py              # sprs.parl.gov.sg, free
│   └── austlii_sg.py           # AustLII SG section, free
└── user_credentialed/          # Phase 3 only
    ├── lawnet.py               # OFFICIAL API path only — never session cookies
    ├── practical_law_sg.py     # ditto
    └── lexisnexis_sg.py        # ditto
```

Rules:

1. **Benchmark uses public adapters only.** Every benchmark task instance must trace to a public-domain source. No paywalled-data leakage into the benchmark.
2. **Copilot can use both.** User opts in to credentialed adapters via Settings, credentials in OS keychain (Tauri) or session-only (web). Server never persists.
3. **Paid sources require official API access.** Do not ship scrapers that submit user passwords to commercial sites. Apply for partner data feeds: SAL/LawNet has a tech-partner program, LexisNexis has API access tiers. Slower but defensible.
4. **Audit-logged user responsibility.** UI must surface: *"You are accessing [Source] under your own subscription. You are responsible for compliance with that source's terms."*

This separation lets the benchmark stay copyright-clean and reproducible-by-anyone, while the copilot can be genuinely useful to SG lawyers with subscriptions.

## 8. Distribution & launch plan

### 8.1 Pre-launch (weeks 1–8)

1. Cut legacy code (§3.1). Single PR per directory removal for cleanliness.
2. Integrate Phase 1 kevanwee repos (§6).
3. Build SG-LegalBench v0.1 datasets and scorers (§4).
4. Build eval CLI: `junas eval --task SGLB-01 --model claude-opus-4-7 --output leaderboard.json`.
5. Run baselines across ≥4 frontier models. Budget the API spend now — likely several hundred USD.
6. Draft arXiv preprint (targets: NLLP Workshop @ EMNLP 2026, arXiv cs.CL primary, cs.AI secondary).
7. Write README2 + landing page focused on benchmark.
8. Prepare a single canonical demo GIF: model picks wrong PDPC obligation, leaderboard shows it, click-through to held-out test case.

### 8.2 Launch week

Coordinated across one Tuesday (HN best for Show HN, Tue 0700 PT):

- T-7d: arXiv submission + ensure DOI lands.
- T-3d: SAL / SMU SOLID team / NUS TRAIL / MinLaw LIFT outreach emails (no embargo ask, just "FYI, launching X on Y, would value your feedback").
- T-0 0700 PT: HN Show HN post with the leaderboard surprise as the hook ("We benchmarked GPT-5, Claude 4.x, and Gemini 2.x on Singapore law — they all fail PDPA reasoning at < X%").
- T-0 0900 SGT: LinkedIn post tagging SG legal-tech community.
- T-0: tweet thread with the four most surprising eval findings.
- T-0: email Artificial Lawyer, Legal IT Insider, Legal Futures, LawTech.Asia (Asia-focused outlet) — they covered Mike OSS, SG-LegalBench is differentiated enough to also cover.

### 8.3 Post-launch (weeks 1–8 after)

1. Respond to HN/GitHub issues fast (first 72h matters).
2. Open a `CONTRIBUTING.md` with the LegalBench-style task contribution model: anyone can submit a new SG legal task PR with provenance + scorer.
3. Submit to NLLP Workshop @ EMNLP 2026 (submission deadlines typically July–August).
4. TechLaw.Fest abstract submission (October SG event, SAL-run).
5. Reach out to SMU SOLID team for an explicit "downstream eval consumer" alignment — if SOLID expands data, junas adds benchmark tasks.

## 9. Success metrics (concrete, dated)

[Speculation] Targets at +3 months post-launch:

| Metric | Floor | Target | Stretch |
|---|---|---|---|
| GitHub stars | 300 | 1,000 | 2,500 |
| Forks | 30 | 100 | 250 |
| HN Show HN rank | front-page (top 30) | top 10 | #1 |
| arXiv preprint downloads | 200 | 500 | 1,500 |
| Citations within 12 months | 0 | 3 | 10+ |
| Independent benchmark contributions (PRs adding tasks) | 1 | 5 | 15 |
| SG legal-tech press hits | 1 | 3 | 5+ |
| Frontier-model leaderboard entries (us + external) | 4 (ours) | 8 | 15+ |

Floor numbers must justify continuing the project; if floor is not hit by +6 months, treat as portfolio-piece-only and stop investing.

## 10. Risk register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | **No lawyer credibility** (P0, see §11) | High | Methodology-as-substitute (see §11 in full). |
| R2 | **eLitigation scraping TOS** | High | TOS pass before integration; fallback to CommonLII-only or user-supplied corpus mode. |
| R3 | **Copyright on SLR / paywalled case text** | High | Benchmark uses only public-domain sources; paywalled access via official APIs and user subscriptions in copilot only. |
| R4 | **Labeling quality without lawyer review** | High | Mechanical-derivation framing (§4.1); LLM-judge with full disclosure; held-out test sets reviewed via crowd contributors post-launch. |
| R5 | **SOLID (Q4 2026) supersedes benchmark data sources** | Medium | Position as downstream consumer; when SOLID ships, add benchmark tasks grounded in SOLID data. SOLID strengthens, not threatens, the thesis. |
| R6 | **Mike OSS does its own SG version** | Medium | Mike has not signaled SG focus; benchmark moat is methodology, not data. If Mike forks the data, junas remains the upstream eval authority. |
| R7 | **HN miss on launch** | Medium | Pre-warmed outreach, surprising headline number, single demo GIF, Tuesday morning PT timing, ready-to-go submission text. |
| R8 | **Solo dev burnout** | Medium | Phased plan; floor metrics define exit. |
| R9 | **Token budget on baselines** | Low | Use cached Anthropic prompt caching for eval, budget < USD 500 across all baselines. Open-weight baselines (Llama 3, Qwen 3) cost only GPU time. |
| R10 | **AGC / SAL legal pushback on scraping** | Medium | Rate-limit, respect robots.txt, cache aggressively, prefer official endpoints, surface contact channel for takedown requests. |

## 11. Operating without lawyer credibility — the load-bearing constraint

[Inference] No named lawyer co-author is likely. The project must succeed without it. This section is the substitute-strategy.

### 11.1 Reframe the claim being made

Do **not** claim: "we built a benchmark that tests legal reasoning competence."
Do claim: "we built a benchmark that mechanically reformulates published Singapore regulator and court outputs as evaluation tasks for LLMs."

The difference is epistemological. The first claim requires legal authority; the second requires reproducible engineering. Stanford LegalBench could make the first claim because of law-faculty co-authors. SG-LegalBench makes the second because that is what its data provenance actually supports.

### 11.2 Tactics

1. **Provenance-first methodology section.** Every task spec leads with "Source: [exact regulator URL]. Extraction rule: [deterministic script]." Reviewers cannot dismiss derivations they can re-run.
2. **No author legal opinions in labels.** If a label requires legal judgment beyond mechanical extraction, either redesign the task or drop it.
3. **LLM-judge with full disclosure where used.** When ground-truth is ambiguous (e.g., clause tone), use ≥3 frontier models in consensus, disclose disagreement rates, publish raw model votes alongside aggregated labels.
4. **Open contribution model from day one.** LegalBench grew from 162 tasks via 40 contributors. Set the same contribution path. Lawyers contribute legitimacy by submitting tasks, not by endorsing the maintainer.
5. **Workshop venue, not conference.** Target NLLP Workshop (Natural Legal Language Processing) at EMNLP. The community there evaluates engineering on engineering merits; multiple NLLP papers are authored by NLP engineers without law credentials. Conference main-track legal papers expect law-faculty co-authorship.
6. **Institutional partnership over personal endorsement.** Ask SAL / SMU SOLID team / NUS TRAIL for institutional alignment, not personal vouching. Different ask, different success rate.
7. **Career framing.** Position self publicly as "evaluation infrastructure engineer for legal LLMs," not "legal AI expert." The first is true and defensible; the second invites attack.
8. **Surface uncertainty.** Every task page lists known limitations and where labels could be wrong. Surfaces fragility as a feature, not a vulnerability.
9. **Reproducibility is the credibility currency.** A reviewer running `make ingest-all && junas eval` and getting identical numbers is worth more than a named lawyer in this audience.
10. **Avoid practice-advice surfaces.** Do not ship anything that could be construed as offering legal advice. Compliance checker becomes "PDPA-rule heuristic alignment scorer," not "PDPA compliance certifier."

### 11.3 What this rules out

- BigLaw enterprise sales (always needs credentials + insurance + sales motion).
- Solo / small SG firm direct sales (needs credentials + relationships).
- Press framing as "the SG lawyer's tool" (we are upstream of that).

### 11.4 What this opens up

- ML research community legibility (engineers evaluating engineers).
- arXiv + NLLP + cs.CL distribution channels.
- Junior NLP / legal-tech engineering roles (LawNet, INTELLLEX, Lupl, NUS/SMU research labs).
- Long-tail academic citation.

## 12. Phased timeline

[Speculation] Solo dev, evenings + weekends, 2026-05 start.

| Phase | Window | Deliverable |
|---|---|---|
| P0 — Cut | weeks 1–2 | All deletions per §3.1 merged. Tauri stack removed. README2 rewritten. |
| P1 — Ingest | weeks 2–4 | `pdpcscraper` + `sgstatutescraper` + `sal-citation-generator` ported. `make ingest-all` working. Datasets land in `data/benchmarks/`. |
| P2 — Tasks | weeks 4–7 | SGLB-01 through SGLB-04 spec + dataset + scorer. Eval CLI MVP. |
| P3 — Tasks cont. | weeks 7–10 | SGLB-05 through SGLB-08 spec + dataset + scorer. eLitigation TOS pass + integration or fallback. |
| P4 — Baselines | weeks 10–12 | Baselines across ≥4 frontier models. Leaderboard JSON + static page. |
| P5 — Paper | weeks 12–14 | arXiv preprint draft. Methodology, results, limitations. |
| P6 — Launch | week 15 | Coordinated launch (§8.2). |
| P7 — Sustain | weeks 16–28 | NLLP submission, contributor PRs, copilot polish, Phase 2 kevanwee repos (`hansardscraper`) conditional on task design, Phase 3 (`sightstone`) conditional on user demand, adapter architecture for paid sources. |

Floor decision: if at +12 weeks the baseline numbers are not interesting (i.e., every frontier model already scores >90% on every task), the benchmark is not landing the narrative — pivot tasks toward harder reasoning before launch.

## 13. Open questions to revisit before P6

1. Final benchmark name: "SG-LegalBench" vs "SingLegalBench" vs "LexSG-Eval". [Speculation] "SG-LegalBench" is clearest and most discoverable; defer final choice to week 14.
2. License: MIT for code + CC-BY-4.0 for dataset? Or AGPL-3.0 for code to match Mike OSS and discourage commercial copilot forks? Decision needed by P6.
3. NLLP 2026 vs 2027 submission window — depends on actual ship date.
4. Whether to publish a "BYOK SG legal copilot" SaaS-style hosted demo at launch (cheap but adds maintenance cost) or rely on local-run only.
5. Whether to seek MinLaw LIFT visibility — likely valuable but slow and may constrain framing.

## 14. Non-goals

Restating for discipline:

- Not building a Mike OSS competitor.
- Not building a Harvey competitor.
- Not building a Word add-in.
- Not selling to law firms.
- Not adding court prediction back.
- Not adding multi-jurisdiction breadth back.
- Not seeking lawyer endorsement as a precondition to launch.
- Not preserving any feature solely because it currently exists.

End of plan.
