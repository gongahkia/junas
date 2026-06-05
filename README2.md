# Junas — SG-LegalBench + Reference Copilot

> [!NOTE]
> `README.md` is intentionally locked (legacy v2 desktop product narrative).
> This `README2.md` reflects the post-pivot direction. The original
> decision record (dated 2026-05-16) is preserved in git history; the
> load-bearing strategic content is now in `docs/coverage-matrix.md`,
> `CONTRIBUTING.md`, and per-task specs under `docs/sglb_specs/`.

## What this is

**SG-LegalBench** is the first open benchmark for Singapore legal reasoning in
LLMs, accompanied by a minimal reference copilot built on the same backend.
Eight tasks, all grounded in public-domain SG sources (PDPC, SSO, MOM, Rules of
Court 2021), with mechanically-extracted labels and reproducible baselines
across frontier and open-weight models.

- **Primary artifact:** SG-LegalBench (dataset + eval CLI + arXiv preprint)
- **Secondary artifact:** SG-tuned reference copilot demonstrating the benchmark
- **Audience:** ML researchers / legal-NLP community, SG legal-tech engineers, SG lawyers

## What this is not

- A practice-advice tool. We make no legal interpretive claims.
- A lawyer-credentialed product. Every label is mechanically derived from a
  published regulator or court output.
- A multi-jurisdiction platform. SG-only. The registry pattern is preserved for
  future Commonwealth adjacency (MY) but not implemented.
- A revenue product. We're optimising for stars + HN + research traction, not ARR.

## Tasks (v0.1)

| ID | Task | Source | N | Metric | Leaderboard status |
|---|---|---|---|---|---|
| SGLB-01 | PDPA-Outcome | PDPC enforcement decisions | 211 | macro-F1 (obligation), MAE (penalty log-band) | eligible |
| SGLB-02 | Statute-QA | SSO statutes | 78 PDPA seed; target ~500 | exact-match (citation), ROUGE-L (answer) | eligible |
| SGLB-03 | Case-Holding | eLitigation public judgments (TOS-gated) | deferred | exact-match on MCQ holding | ineligible - TOS-gated |
| SGLB-04 | Citation-Verify | SAL Style Guide grammar + perturbations | 30 smoke; production target ~1000 | accuracy + per-error breakdown | eligible |
| SGLB-05 | Employment-Issue | MOM guidance + Employment Act | pending | multi-label F1 | code-shipped, awaiting data[^sglb05-data] |
| SGLB-06 | Rules-of-Court-2021 | Rules of Court 2021 (SSO) | pending | exact-match (order:rule), top-3 acc | code-shipped, awaiting data[^sglb06-data] |
| SGLB-07 | Jurisdiction-Routing | SG cases citing UK/AU/HK precedent | pending | accuracy | code-shipped, awaiting data[^sglb07-data] |
| SGLB-08 | Clause-Tone | Junas SG clause library + LLM-judge | 400 | macro-F1 | eligible |

[^sglb05-data]: Data dependency: [Batch A](PROMPTS-TO-RUN.md#batch-a--mom-scraper-59-4-parallel-agents) for the MOM scraper / SGLB-05 data.
[^sglb06-data]: Data dependency: [`NEW-SSO-EXPAND`](PROMPTS-TO-RUN.md#new-sso-expand-sso-ingest-beyond-pdpa-closes-gap-04-partial) for Rules of Court 2021 SSO ingest.
[^sglb07-data]: Data dependency: [Batch B](PROMPTS-TO-RUN.md#batch-b--commonlii-sg-case-ingester-34-4-parallel-agents) for the CommonLII SG case ingester / SGLB-07 data.

Phase-2 candidates: SGLB-09 (Hansard-grounded statutory interpretation),
SGLB-10 (IRAS Tax Ruling reasoning).

## Labeling provenance — the credibility substitute

Every label derives from a public regulator/court source by **mechanical
extraction**, not by author legal judgment. This is the load-bearing
methodological commitment.

- PDPA outcomes: pulled from PDPC's published findings.
- Statute QA: derived from SSO section headings and content.
- Case holdings: extracted from "Holding" / catchwords sections.
- Citation validity: mechanically derived from the SAL Style Guide grammar.
- Employment issues: tagged using MOM's own published issue taxonomy.
- ROC 2021: derived from the Rule's own scope text.
- Jurisdiction routing: derived from explicit court statements about
  precedent applicability.
- Clause tone: bootstrap with LLM-judge across ≥3 frontier models with
  explicit disclosure; held-out subset spot-checked.

Label disputes and methodology concerns are handled through the
[dispute and errata process](docs/dispute-process.md).

## Reference copilot — minimal scope

The copilot exists to demonstrate the benchmark, not to replace existing OSS
legal copilots. Feature set:

- BYOK chat (multi-provider: Anthropic, OpenAI, Google, Ollama, LM Studio)
- SG statute + case retrieval (hybrid BM25 + dense + cross-encoder)
- Citation verifier in chat output (SAL Style Guide)
- PDPA + Employment Act compliance checker
- SG clause + template library (6 SG clauses, 6 SG templates seeded)
- Document parsing for PDF/DOCX

Explicitly **not** in scope: matter management, Word add-in, multi-user
collaboration, billing, agent orchestration, court-prediction UI.

## Stack

- **Backend:** Python 3.11+, FastAPI, Celery, Postgres, Elasticsearch, Qdrant, Redis
- **Frontend:** Next.js 14, React 19, TypeScript, Tailwind
- **AI providers:** Anthropic, OpenAI, Google, Ollama, LM Studio (BYOK)
- **ML:** sentence-transformers, HuggingFace transformers, ort
- **Data:** PDPC (`pdpcscraper`), SSO (`sgstatutescraper`), SAL (`sal-citation-generator`)

## Running locally

```sh
# Backend (port 8000)
make api

# Frontend (port 3000)
make frontend

# Both
make dev

# Infra (Postgres, Elasticsearch, Qdrant, Redis)
make up
```

## Reproducing baselines

`[Unverified]` Eval CLI lands in P2 (issue #31). Once shipped:

```sh
# Run a single task
python -m backend.benchmark run --task SGLB-01 --model claude-sonnet-4-6

# Full v0.1 suite
python -m backend.benchmark run-all --output runs/<run_name>
```

Every regenerated benchmark dataset carries extraction-rule provenance:
each case row has `extraction_rule_sha`, and each harness YAML has a
top-level `extraction_rules` map such as `{pdpc: <sha>, sso: <sha>}`.
The SHA is the 7-character git revision of the ingestion or builder module
that last changed the mechanical extraction rule. CI validates these fields
for datasets that declare extraction rules.

## Data provenance

All benchmark instances trace to a public-domain SG source. Public adapters
live at `backend/api/adapters/public/` (issue #30). The benchmark uses **public
adapters only**; the copilot can additionally use user-credentialed adapters
(LawNet, Practical Law SG) via opt-in Settings with credentials in OS keychain.

## Licensing

- **Code: MIT** — see `LICENSE`.
- **Datasets: CC-BY-4.0** — see `docs/dataset-license.md` and `LICENSE`
  §"Dataset licence".
- Rationale + alternatives considered: `docs/decisions/dr-001-name-and-license.md`.

When citing this benchmark: `SG-LegalBench (Junas), CC-BY-4.0, <repo URL>`.

## Roadmap

| Phase | Issues | Status |
|---|---|---|
| P0 | #24 #25 #26 | In progress (this PR) |
| P1 | #27 #28 #29 #30 | Next |
| P2 | #31 #32 | Pending P1 |
| P3 | #33 #34 | Pending P2 |
| P4 | #36 | Pending P3 |
| P5 | #37 #38 | Pending P4 |
| P6 | #39 | Pending P5 |

See [GitHub issues](https://github.com/gongahkia/junas/issues) for full tracking.

## Disclaimer

This is research infrastructure, not legal advice. The benchmark and copilot
are AI-generated and may contain errors. Users must independently verify any
output before relying on it in any legal context. See `README.md` §Legal
Disclaimer for full terms.
