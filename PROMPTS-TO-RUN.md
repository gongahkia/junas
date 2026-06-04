# PROMPTS-TO-RUN

Each fenced code block is a self-contained prompt you can copy verbatim
into a fresh Claude Code session that has been spawned inside this
repository. Every prompt assumes the agent has access to
`AGENT-RUNBOOK.md` — agents will read that first as part of their
work.

## How to use this doc

1. Pick a batch (parallel, runs together) or a solo prompt.
2. For each prompt, open a new Claude Code session inside this repo
   (or spawn an agent with `isolation: "worktree"`). Paste the prompt
   verbatim.
3. Run parallel agents in **separate worktrees** to avoid file-write
   conflicts. The runbook §7 documents the worktree convention.
4. Once the agent reports done, review the branch + tests + commit
   message, then merge to `main` yourself (the user is the merge
   authority; agents do not push to `origin/main`).

**Do not kill the SGLB-08 synthetic gen** running in the background.
See runbook §8.

## Critical context the user should know before running any of this

These are honest constraints, not blockers:

1. **No frontier baselines exist yet.** The launch story ("frontier
   models fail PDPA reasoning") cannot be told until #36 runs. Every
   data-shipping task downstream of this is gated by that.
2. **SGLB-08 synth cost is unmodeled for reasoning tokens.** The
   $0.015/example estimate omits reasoning-token cost; actual Azure
   spend may be 5-10x. Decide before running another 400-case gen.
3. **SGLB-02 is PDPA-only.** Until `make ingest-sso` runs against AGC
   for EmA / PC / ROC2021, the leaderboard cell stays at 78 cases.
   The README2 target was 500.
4. **Three tasks have no data** (SGLB-05/06/07). Code is shipped; the
   harness scores them at 1.0 via oracle, but a real model run would
   show "no dataset" errors. The HN claim "8 tasks shipped" is
   misleading until the data lands.
5. **No reference copilot work** since the pivot. Pivot §5 said the
   copilot demonstrates the benchmark. Currently it's untouched
   except for backend services. A real legal tech company evaluating
   this will care about the copilot more than the benchmark — they
   buy products, not papers.
6. **License + name decision** (#40) is still open. Affects PR
   acceptance policy. Decide before launch.

These are not concerns the parallel agents need to solve — they're
context for prioritisation.

---

---

# Fire order (read this first)

PROMPTS BELOW ARE LISTED IN EXECUTION ORDER. Top to bottom.

The tier markers are ship-discipline, not arbitrary. Items within a
tier can run in parallel; items in later tiers should wait until
their tier's dependencies land. Hard-dependency notes are inline on
each prompt.

| Tier | Why this tier exists | Items |
|---|---|---|
| **Tier 1 — Launch path** | Without these, there is no HN headline + no v0.1 ship | Batch D, SOLO-17, SOLO-9, Batch A, Batch B |
| **Tier 2 — Post-numbers** | Need Tier-1 outputs to start | SOLO-8, SOLO-18, SOLO-10 |
| **Tier 3 — Pre-launch polish** | Visible to launch-day visitors | Batch E, Batch C, SOLO-3, SOLO-1, SOLO-2, SOLO-5, SOLO-6, SOLO-4 |
| **Tier 4 — Post-launch + v0.2** | Ships after launch | Batch G, Batch H, Batch F, SOLO-7, SOLO-11, SOLO-13, SOLO-15, SOLO-12, SOLO-14, SOLO-16, COPILOT-1..4 |

## Hard dependencies (do not violate)

- **SOLO-17 before Batch D's SGLB-08 run** — otherwise the receipt
  records single-judge labels with no κ.
- **SOLO-9 before Batch G's G3 (SGLB-14)** — G3 needs PDPC Advisory
  Guidelines data.
- **SOLO-13 (#45 design) before SOLO-15 (#47 selector impl).**
- **SOLO-7 (#35 copilot scope) before SOLO-11 (#42 templates).**

## Cost gates (read AGENT-RUNBOOK §8)

- **Batch D D1 + Batch H H2/H3** call Azure gpt-5; estimator quotes
  5-10x low because reasoning-token billing is not modelled. Get
  explicit user approval before firing.
- **SOLO-17 + every Anthropic/Gemini-only prompt** is cost-safe
  (~$0.005/call); these can fire without escalation.

---
## Tier 1 — Launch path

_Fire these first; baselines are the whole launch story._

## SOLO-17: SGLB-08 multi-judge ensemble pass (methodology upgrade)

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
labels (advances #33)`.

Acceptance:
- judges.jsonl materialised with 400 × 2 vote rows.
- κ printed to stdout + persisted in a summary JSON.
- All κ pairs ≥ 0.4 (or, if any drop below, an issue is filed +
  spec doc updated to reflect retirement risk per coverage matrix §8).

Report back: the 3 pairwise κ values + Fleiss' κ + any cell where
agreement is dangerously low. Note any provider-specific JSON-parse
failures (those are a quality signal too).
```

## SOLO-9: PDPC Advisory Guidelines scraper (#60)

```text
You are implementing issue #60 in the junas repo: PDPC Advisory
Guidelines scraper (unblocks SGLB-14 Statutory-Entailment data).

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

---

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

---

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

---

## Tier 2 — Post-numbers

_Need Tier-1 results to fill placeholders / make decisions._

## SOLO-8: arXiv preprint outline (#37)

```text
You are starting issue #37 in the junas repo: SG-LegalBench preprint
draft. Read AGENT-RUNBOOK.md, docs/coverage-matrix.md, and all of
docs/sglb_specs/SGLB-NN.md.

Scope: produce the preprint outline + draft §§1-3 (Introduction,
Methodology, Tasks). Leave §§4-5 (Results, Limitations) as
TODO-blocks gated on baselines (#36).

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

## SOLO-18: SGLB-08 human-reviewed held-out subset

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
checklist (advances #33)`.
Commit (after user returns checklist): `feat(sglb-08): apply human
holdout decisions; flag disputes`.

Acceptance:
- 40-row checklist generated, stratified across all cells.
- Spec doc references the file.
- A clear "user, please fill this in and report back" surfacing in
  your final message so the human-in-the-loop step doesn't get lost.

Report back: the stratification table (which cells got how many);
your hand-off message to the user.
```

## SOLO-10: #40 Final benchmark name + license research brief

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
#40)`. Co-Authored-By trailer.

Acceptance: 1-page brief in markdown; user can make the call without
asking follow-ups.
Report back: your one-sentence recommendation; any surprising
constraint you found.
```

## Tier 3 — Pre-launch polish

_Visible to launch-day visitors; queue after Tier 2._

# Batch E — Launch Assets (#39), 4 parallel agents

**Goal:** produce ship-ready launch assets so the moment #36 (baselines)
lands, the launch can fire same-day. These run in parallel since they
touch different files and require no shared state.

**Coordination contract:** branch `feat/launch-assets-v0.1`. All four
agents commit to the same branch; user reviews each commit
independently. Where copy depends on baseline numbers, agents leave
`<PLACEHOLDER>` tokens that a follow-up PR fills.

## E1: HN Show HN post + landing-page hook

```text
You are working on issue #39 (launch assets) in the junas repo. Read
AGENT-RUNBOOK.md, README2.md, docs/coverage-matrix.md §5 (anti-snake-
oil checklist), and the existing landing page at frontend/app/page.tsx.

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
- Lead with the SG-uniqueness gap (LegalBench=US, LexGLUE=US+EU,
  LawBench=CN; SG is a clean gap).
- "We make no legal interpretive claims" must appear.
- 3 headline candidates: surprising-number variant (gated on #36),
  capability-gap variant (no number needed), methodology variant
  ("first SG benchmark with mechanical labels"). Mark which need #36.

Post structure (suggested):
- Title (≤80 chars)
- Opening hook (2 sentences)
- What it is (3 bullets, link to repo + spec dir)
- What it isn't (1-2 bullets, defuses scope-overclaim)
- Reproducibility (1 bullet — `make eval` and you get the same numbers)
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
that depends on baseline (#36) numbers.

Files you own:
- docs/launch/twitter-thread.md (new)

Files you must NOT touch:
- E1/E3/E4's files.

Thread structure:
1. Hook tweet — why this matters (no number needed)
2. The gap (LegalBench=US, LexGLUE=US+EU, LawBench=CN, gap=SG)
3. Methodology — mechanical extraction; the credibility substitute
4-8. One surprising finding per tweet (each gated on #36; mark
   <PLACEHOLDER>)
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

Branch + commit: same as E1.
Acceptance: 1 post + 6 personalised DMs.
Report back: which targets warrant a phone call vs DM.
```

## E4: Press kit + journalist outreach

```text
You are working on issue #39 in the junas repo. Read AGENT-RUNBOOK.md,
README2.md, and (for tone reference) any coverage Mike OSS got from
the same outlets (Google "willchen96 mike artificial lawyer").

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
- Key facts (8 tasks, public-domain sources, mechanical labels,
  multi-model baselines)
- 50-80 word attributable quote from the solo dev (Gabriel) about the
  SG-uniqueness gap
- Where to find screenshots / demo GIF (placeholder paths)
- Contact (TBD; surface to user)

Each pitch email ≤200 words. Differentiate from Mike OSS coverage
angle (benchmark, not product; SG, not generic).

Branch + commit: same as E1.
Acceptance: 1 press kit + 5 personalised pitches.
Report back: which outlets covered Mike OSS recently and how we
differentiate.
```

---

# Batch C — Frontend Audit Fixes, 4 parallel agents

**Goal:** address the critical findings from `docs/audit/00_EXECUTIVE_AUDIT.md`
that remain unfixed. The audit was 2026-04-02; some have since been
resolved (predictions/, rome-statute/, compare-jurisdictions/ pages
removed). What's left:

- 3 GET-method forms with sensitive textareas (privacy risk;
  browser-history leakage)
- 2 `dangerouslySetInnerHTML` on user-supplied data
- Duplicated API data-access (api-client.ts + api-server.ts + direct
  `fetch` in pages)
- Command palette `/home` dead link

These four areas have **non-overlapping file targets** so they can
run in parallel without rebase pain.

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
request/response shapes between callers (this is a real risk; the
audit listed jurisdiction mismatch as one such case).
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
that we relied on (e.g. iframes, MathML, style attributes — note
them so the user can decide whether to whitelist).
```

---

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

Report back: any synth-pipeline edge cases (the synth gen is
running RIGHT NOW; don't break the in-flight gen).
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

Report back: any task whose data_tier is ambiguous (e.g. a mixed
dataset).
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

Report back: any step that surprised you (i.e. anything not
documented elsewhere that you needed to know).
```

## Tier 4 — Post-launch + v0.2

_Fire after v0.1 ships; safe to defer._

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

## G1: SGLB-09 Summary-Faithfulness

```text
You are working on issue #50 (SGLB-09 Summary-Faithfulness).

Read AGENT-RUNBOOK.md, docs/sglb_specs/SGLB-09.md, CONTRIBUTING.md
"Adding a new task", and the FActScore paper (Min et al., EMNLP 2023,
https://arxiv.org/abs/2305.14251).

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
  bool}]}` — list of atomic facts in the summary with per-fact
  supported-by-source booleans.
- Score: precision over `supported=true` facts that actually appear
  in source_text (deterministic substring or entailment check).

Smoke seed (v0.1): ~20 cases built from existing PDPC JSONL.
Generate 3 candidate summaries per source (faithful / mild hallucination
/ wholesale fabrication) via an LLM call; the atomic-fact extraction
uses an LLM-judge per coverage-matrix §4.1. For smoke, single judge
acceptable WITH disclosure; v0.2 expansion uses ≥3-judge ensemble.

Branch: feat/sglb-v0.2-wave-1.
Commit: `feat(sglb-09): Summary-Faithfulness task (closes #50)`.

Acceptance: 20-case smoke; oracle scores 1.0; tests pass.
Report back: methodology compromises (single-judge); how to scale to
N=200 in v0.2.
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

---

# Batch H — v0.2 Task Wave 2 (#51, #53, #56), 3 parallel agents

**Goal:** close out the synthetic-data v0.2 tasks. SGLB-11 (#52) was
already closed in v0.1.

**Coordination contract:** branch `feat/sglb-v0.2-wave-2`. Same
file-touchpoint discipline as Wave 1.

**Synth-gen cost warning:** H2 and H3 need synthetic candidates.
SGLB-08 synth gen is in flight right now at ~$0.05/candidate
(reasoning-token cost). Get explicit user approval before kicking off
new synth jobs that could spend another $20-50.

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
- backend/benchmark/dataset_builders/sglb_12.py (NEW file if not
  present — reads reviewed synthetic candidates into harness shape)
- backend/benchmark/tasks/sglb_12.py (extend if needed; do not break
  existing tests)
- backend/benchmark/llm_runner.py (refine sglb_12 prompt if needed;
  preserve version string semantics)
- backend/benchmark/datasets/sglb_12_multi_issue_reviewed/ (output
  dir; promote synthetic candidates here)
- docs/sglb_specs/SGLB-12.md (bump to 0.1-shipped if you reach ≥50
  reviewed cases)
- backend/tests/test_sglb_12_task.py (extend coverage)

Files you must NOT touch:
- H1/H3's sglb_NN files.
- backend/benchmark/synthetic/sglb_12.py (used by the existing synth
  pipeline; do not modify unless a real bug surfaces).

Cost gate: if reviewed candidates don't exist yet, you'd need to run
`make synth-gen TASK=sglb_12 N=200 ...`. The SGLB-08 synth gen is
currently running and costing ~$0.05/example via Azure gpt-5. A 200-
case SGLB-12 run would cost ~$10-20. STOP and get user approval before
firing synth-gen.

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
- backend/benchmark/dataset_builders/sglb_15.py (new if not present)
- backend/benchmark/tasks/sglb_15.py (extend)
- backend/benchmark/llm_runner.py (refine prompt)
- backend/benchmark/constraints.py (add SG-context constraints; see
  list below)
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

---

# Batch F — MCP Server (#48), 4 parallel agents

**Goal:** expose junas as an MCP server so Claude Desktop / Claude
Code users can run benchmarks + query SG legal sources without
leaving chat. A "drop into Claude Desktop and get SG legal lookup +
benchmark" demo is much more compelling than a static leaderboard.

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

Acceptance: `make mcp` boots without error; `health` tool responds;
server starts under Claude Desktop config (test on the user's
machine if possible).

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
- backend/mcp/server.py (F1; you register tools into it via a clean
  import — append registrations after F1's stub list)
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
- docs/mcp/troubleshooting.md (port collision, missing keys, SDK
  version mismatch)

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
workflows (e.g. "verify [2023] SGCA 5, then retrieve cases that cite
it").

Branch: feat/mcp-server.
Commit: `docs(mcp): setup + example prompts + troubleshooting
(advances #48)`.

Acceptance: a fresh user (test on the user's machine or a clean VM)
can install + use junas-mcp within 5 min.

Report back: brittle setup steps; OS-specific gotchas.
```

## F4: MCP tests + integration

```text
You are working on issue #48 in the junas repo. WAIT until F1+F2
have landed. Read AGENT-RUNBOOK.md, F1's server, F2's tools.

Goal: tests for the MCP server + tools.

Files you own:
- backend/tests/test_mcp_server.py (server boots + health works)
- backend/tests/test_mcp_tools.py (each tool callable + shape)

Files you must NOT touch:
- backend/mcp/* (F1/F2)
- docs/mcp/* (F3)

Requirements:
- Mock the underlying api.services calls; do NOT make real LLM calls.
- For run_benchmark, use the existing MockLLMClient pattern from
  backend/tests/test_llm_runner.py.
- Test the JSON-schema validation per tool input.
- One integration test: spawn the server in a subprocess, send a
  `list_tools` request, assert 5 tools enumerated.

Branch: feat/mcp-server.
Commit: `test(mcp): server + tool tests (advances #48)`.

Acceptance: `pytest -x -q backend/tests/test_mcp_*` passes; no
network calls in test mode.

Report back: any tool hard to test deterministically (that's a smell
to fix in F2).
```

---

## SOLO-7: Reference copilot scope cleanup (#35)

```text
You are addressing issue #35 in the junas repo: keep only SG
retrieval, citation, and compliance surfaces in the reference
copilot. Read AGENT-RUNBOOK.md and the pivot history in git
(commit a910403 is the SSO landing; earlier commits cut non-SG
paths).

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
keep-vs-cut call, surface the question; don't decide unilaterally
on borderline items.
```

## SOLO-11: #42 Port SG-applicable contract templates

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

## SOLO-13: #45 Region-per-index naming + adapter pattern (design FIRST)

```text
You are working on issue #45 in the junas repo. Read AGENT-RUNBOOK.md,
backend/api/services/{case_retrieval,statute_lookup,retrieval_orchestrator}.py,
backend/api/indices.py.

This is ARCHITECTURAL. Two-phase delivery:
- PHASE 1: design doc (this prompt). STOP after committing.
- PHASE 2: implementation (separate prompt the user will issue after
  reviewing the design).

Files you own (Phase 1 only):
- docs/decisions/dr-002-region-per-index.md (new)

Design doc sections:

1. **Current state.** No region prefix; indices implicitly SG-only.
   Document the cases this hurts.
2. **Why we need this.** Future Commonwealth adjacency (MY); SOLID
   partnership may want per-region routing; copilot may serve clients
   with multi-region practice.
3. **Proposed naming convention.** `sg.statutes`, `sg.cases`,
   `my.statutes`, etc.
4. **Adapter pattern.** Each LegalSourceAdapter declares
   `metadata.region: str`; retrieval orchestrator routes by region
   tag pulled from a request header (X-Junas-Region) or session
   state.
5. **Migration plan.** Backward-compat shim during the deprecation
   cycle; how to reindex without downtime.
6. **Risks.** Index reindex cost; query API breakage; downstream
   evaluator assumptions.
7. **Estimate.** Implementation effort post-approval (days/weeks).

STOP after design. Do not begin implementation.

Branch: docs/dr-002-region-per-index.
Commit: `docs(decision): region-per-index design (advances #45)`.

Acceptance: a design doc the user can approve in one read.
Report back: your recommendation; implementation effort estimate.
```

## SOLO-15: #47 Jurisdiction selector UI

```text
You are working on issue #47 in the junas repo.

**Honesty check first.** SG-only scope means a jurisdiction selector
is forward-investment for the MY adjacency planned in SOLO-13 (#45).
Do NOT implement a single-option dropdown. Either:
- Wait for SOLO-13's design doc + Phase-2 impl, OR
- Build the component now with MY visibly greyed out as "coming v0.3"
  so the selector exists for future expansion.

If proceeding:

Read AGENT-RUNBOOK.md, frontend/components/*, frontend/lib/*,
backend/api/services/jurisdiction_registry.py.

Files in scope:
- frontend/components/JurisdictionSelector.tsx (new — Radix Select)
- frontend/lib/jurisdiction-state.ts (new — Zustand store or React
  context; match whichever pattern the rest of the app uses)
- frontend/app/layout.tsx (mount the selector in the global header)
- frontend/tests/JurisdictionSelector.test.tsx

Constraints:
- Default: SG. Selected state persists across reload.
- MY option greyed with tooltip "coming in v0.3".
- Adding future jurisdictions requires only a registry entry, not
  a component edit.
- The selected jurisdiction is plumbed into every backend call as
  X-Junas-Region header.

Branch: feat/jurisdiction-selector.
Commit: `feat(frontend): jurisdiction selector UI (closes #47)`.

Acceptance: component renders; SG → MY toggle changes the API header
(verify via network panel); tests pass.
Report back: any backend endpoint that ignores the header (those are
bugs to file separately).
```

## SOLO-12: #43 Logfire observability

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
- A future contributor running `LOGFIRE_TOKEN=xxx make eval` should
  see traces in their Logfire project.

Branch: feat/logfire-observability.
Commit: `feat(observability): opt-in Logfire instrumentation (closes
#43)`.

Acceptance: opt-in works; nothing leaks in CI; doc walks a contributor
through 2-min setup.
Report back: any signal Logfire surfaced that we should add as a
permanent metric in our own receipts.
```

## SOLO-14: #46 PydanticAI migration

```text
You are working on issue #46 in the junas repo.

**Honesty check first.** PydanticAI migration is labelled "low
priority" for a reason. Before starting, verify the migration adds
clear value over the current shape in backend/api/services/legal_qa.py
and backend/api/services/chat_service.py. If you can't articulate
the upside in 2 bullets, STOP and surface to the user — there may
be a better use of the agent slot.

If proceeding:

Read AGENT-RUNBOOK.md, PydanticAI docs (https://ai.pydantic.dev/),
backend/api/services/legal_qa.py + chat_service.py.

Files in scope:
- backend/api/services/orchestration.py (new — agent graphs for RAG
  + tool-use)
- backend/api/services/legal_qa.py (refactor to use orchestration)
- backend/api/services/chat_service.py (refactor)
- backend/tests/test_orchestration.py (new)
- backend/pyproject.toml: + `pydantic-ai`

Constraints:
- Existing chat + legal_qa endpoints must remain bit-identical
  behaviourally.
- The migration must be reversible (preserve the old code path behind
  a JUNAS_USE_PYDANTIC_AI feature flag for one minor version).

Branch: refactor/pydantic-ai-orchestration.
Commit: `refactor(orchestration): migrate to PydanticAI (closes #46)`.

Acceptance: tests pass; existing endpoints behave identically; flag
toggles cleanly.
Report back: the 2-bullet upside you found OR an explicit "stopped
— could not justify the migration; recommend closing #46".
```

## SOLO-16: #73 Branching policy consolidation

```text
You are working on issue #73 in the junas repo. Read AGENT-RUNBOOK.md
§7, CONTRIBUTING.md, PROMPTS-TO-RUN.md.

Branching policy is spread across multiple files. Pick ONE canonical
location and link from the others.

Files you own:
- CONTRIBUTING.md (add or expand a "Branching policy" section as the
  canonical source)
- AGENT-RUNBOOK.md (§7 → replace bulk content with one-line link to
  CONTRIBUTING.md#branching-policy)
- PROMPTS-TO-RUN.md (any branching content → one-line link)

Policy content (canonical):
- Branch naming: feat/<short>, fix/<short>, docs/<short>,
  refactor/<short>, ci/<short>, test/<short>.
- `main` is protected; never push --force.
- Conventional Commits format.
- Pre-commit hooks must pass (no --no-verify).
- Shared interfaces (scorer registry, dataset format) → PR required;
  low-risk fixes can land direct.
- Worktrees for parallel agents; runbook §7 reference for the path
  convention.

Branch: docs/branching-policy-consolidation.
Commit: `docs(policy): consolidate branching policy in CONTRIBUTING
(closes #73)`.

Acceptance: branching policy lives in exactly one place; other docs
link to it.
Report back: any policy mismatch between existing docs that you had
to reconcile.
```

---

## Tier 4 (cont.) — Copilot product polish

_Lifts the copilot from harness UI to a thing a SG legal-tech engineer would put in front of a real lawyer._

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

# Truly backlog (still not prompt-ready)

These are the items left without prompts. They need user decisions
or external dependencies before they can be specified:

- **#58** — meta-tracking issue for the v0.2 expansion. All sub-issues
  (#50, #51, #53, #54, #55, #56, #57) are specified above (Batches G
  + H). When all close, this one closes too.
- **Future user-driven issues** — if you find a need that isn't in
  this doc:
  1. Open a GitHub issue; write a prompt for it here in a follow-up PR.
  2. Surface to the user directly if it's a one-off operational concern.

