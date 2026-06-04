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

# Batch D — Baseline Evaluations (#36), 4 parallel agents

**Goal:** run real baselines across SGLB-01/02/04 (and SGLB-08 once
synth-gen completes + promotes). Produces the headline numbers for
the launch.

**Hard prerequisite:** the user must approve the per-provider API
spend. Each agent should default to a `--dry-run` that estimates
spend BEFORE making any real call.

**Coordination contract:** branch `feat/baselines-v0.1`. All four
agents commit to the same branch. Receipts emit to
`runs/baselines/<provider>/<task>/<timestamp>.json`. D4 aggregates
into the leaderboard.

## D1: OpenAI (Azure) baselines

```text
You are running issue #36 (baseline evaluations) for the OpenAI
provider (via Azure OpenAI; the user has Azure credentials but not
OpenAI direct). Read AGENT-RUNBOOK.md, runbook §8 about the gpt-5
reasoning-token cost trap, and backend/benchmark/LLM_RUNNER.md.

Your scope: for each shipped task (SGLB-01, SGLB-02, SGLB-04, and
SGLB-08 ONLY if promoted candidates exist by the time you run),
register an LLM-backed runner pointing at Azure OpenAI, run the
harness, write the receipt.

Files you own:
- backend/benchmark/scripts/run_baselines_azure.py (new — a script,
  not a test; lives in benchmark/scripts/ for clarity)
- runs/baselines/azure/* (new — gitignored output)

Files you must NOT touch:
- D2/D3/D4's scripts (separate filenames per provider)
- backend/benchmark/llm_runner.py (do not edit; this is consumer
  code)

Implementation:

1. The script accepts --task, --dry-run, --max-cost-usd args.
2. Use benchmark.llm_runner.register_llm_task() to wire the runner
   with full provenance (prompt_version, prompt_sha, provider_label,
   max_tokens).
3. Run the harness via benchmark.runner.run(...).
4. Emit a receipt JSON via benchmark.runner.write_summary().
5. Estimate cost BEFORE running. For Azure reasoning models (gpt-5),
   reasoning-token cost is unmodeled. Print a loud warning that
   actual spend may be 5-10x the estimate. Refuse to run if
   --max-cost-usd is exceeded by 1.5x the estimate.

Tasks to run, in order:
1. SGLB-04 first (smallest, 30 cases, cheapest sanity check).
2. SGLB-01 (211 cases).
3. SGLB-02 (78 cases).
4. SGLB-08 (only if reviewed cases exist in
   backend/benchmark/datasets/sglb_08_clause_tone_reviewed/).

Branch: feat/baselines-v0.1. Commit:
`feat(baselines): Azure OpenAI baselines across SGLB-01/02/04
(advances #36)`.

Acceptance: 3+ receipt JSONs under runs/baselines/azure/, each
containing provenance + per-evaluator means. NO new test failures.

Report back: per-task score, actual Azure invoice (read from
response usage), any failures (JSON parse errors, rate limits, etc.).
```

## D2: Anthropic baselines

```text
Same as D1, but the provider is Anthropic. Use
api.services.llm_client.AnthropicClient (set llm_provider=anthropic
+ ANTHROPIC_API_KEY in .env). Default model: claude-sonnet-4-6 (the
config default is claude-sonnet-4-20250514; use the most recent
model the user has API access to — check
backend/api/config.py::Settings for the default and the .env for
override).

Files you own:
- backend/benchmark/scripts/run_baselines_anthropic.py (new)
- runs/baselines/anthropic/* (gitignored)

Coordinate with D1/D3/D4 only on the receipt schema (use the
existing RunSummary.to_dict shape — don't add fields).

Run the same task order as D1.

Branch: feat/baselines-v0.1 (shared).
Commit: `feat(baselines): Anthropic baselines across SGLB-01/02/04
(advances #36)`.

Report back: per-task score + comparison vs D1's Azure numbers if
both are done by the time you write the report.
```

## D3: Google (Gemini) baselines

```text
Same as D1, but the provider is Google Gemini. Use
api.services.chat_service.GeminiClient (delegate routes through
get_llm_client when llm_provider=gemini). Model: gemini-2.0-flash
(the config default).

Files you own:
- backend/benchmark/scripts/run_baselines_gemini.py (new)
- runs/baselines/gemini/* (gitignored)

If the user doesn't have a GEMINI_API_KEY set in .env, surface that
in your --dry-run output and stop. Do not silently skip the run.

Branch: feat/baselines-v0.1 (shared).
Commit: `feat(baselines): Gemini baselines across SGLB-01/02/04
(advances #36)`.

Report back: per-task score, Gemini quirks (the API rejects some
JSON-mode patterns; document any that bite).
```

## D4: Open-weight baselines + leaderboard aggregation

```text
You are running open-weight baselines + aggregating results across
all four provider runs. Read AGENT-RUNBOOK.md and #36.

Open-weight target: Ollama-hosted models (Llama 3 8B or Qwen 3 4B,
whatever the user has pulled). Check `ollama list` first; do not
trigger model downloads (large bandwidth + disk).

Files you own:
- backend/benchmark/scripts/run_baselines_ollama.py (new)
- backend/benchmark/scripts/build_leaderboard.py (new — reads all
  receipt JSONs under runs/baselines/*/ and emits a single
  runs/baselines/leaderboard.json + a markdown table at
  docs/leaderboard.md)
- runs/baselines/ollama/* (gitignored)
- docs/leaderboard.md (committed; the human-readable summary)

WAIT until D1-D3 have at least one receipt each before running the
leaderboard build (you can run Ollama baselines in parallel).

Leaderboard format:

| Task | Metric | OpenAI (Azure gpt-5) | Anthropic (claude-sonnet-4.6) | Gemini 2.0 | Llama 3 8B |
|---|---|---|---|---|---|
| SGLB-01 | obligation F1 | X.XX | X.XX | X.XX | X.XX |
| SGLB-01 | penalty MAE | X.XX | X.XX | X.XX | X.XX |
| SGLB-02 | citation match | X.XX | X.XX | X.XX | X.XX |
| SGLB-02 | ROUGE-L | X.XX | X.XX | X.XX | X.XX |
| SGLB-04 | label F1 | X.XX | X.XX | X.XX | X.XX |

Include per-task 95% confidence interval (bootstrap n=1000) — this
is per coverage-matrix §5 ("scores X.XX vs Y.YY on SGLB-NN (95%
CI)").

Branch: feat/baselines-v0.1 (shared).
Commit: `feat(baselines): Ollama open-weight + leaderboard
aggregation (closes #36 first pass)`.

Acceptance: docs/leaderboard.md committed with real numbers; no
"TBD" rows for any task with a shipped dataset.

Report back: any task where every model scored ≥98% (per
coverage-matrix §12, this triggers a "task too easy" review). Any
task where every model scored ≤30% (instructive but suggests
prompt-builder issues — check the system prompt before concluding
the task is hard).
```

---

# Solo prompts (single agent each)

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

# Backlog: prompts not yet specified (write them when prioritised)

These open issues are not yet prompt-ready because they need user
decisions or are blocked on upstream work:

- #40 — final benchmark name + license decision (USER DECISION; not
  an agent task)
- #39 — launch assets + outreach checklist (needs #36, #37 done first)
- #45 — region-per-index naming + adapter pattern (architectural;
  needs a design doc before coding)
- #46 — PydanticAI migration (refactor; low priority)
- #47 — jurisdiction selector UI (depends on copilot scope #35
  being settled)
- #48 — MCP server (nice-to-have; not a v0.1 blocker)
- #43 — Logfire observability (post-launch nice-to-have)
- #42 — port SG-applicable contract templates (#35 scope-cleanup
  first)
- #73 — branching policy docs (this file + CONTRIBUTING already do
  90% of it)
- #58 / #50-#57 — v0.2 task expansion (SGLB-09..16); deferred until
  v0.1 ships
