# Automated synthetic-corpus research

Current scope, chosen 22 November 2026: Junas is a **text-only classifier**. A separate research command generates synthetic text and uses different models to annotate it automatically. Human review is not a prerequisite for this development experiment. Its labels remain model-derived evidence, not independent human ground truth or a protected holdout.

## Runtime reduction

The library accepts `DocumentInput(text=...)`, `review_text(...)`, and bounded UTF-8 text files through `review_file(...)` / `junas classify --file ...`. Accepted filename suffixes are `.txt`, `.text`, `.md`, `.csv`, `.json`, `.log`, or no suffix. Files are analyzed literally: Markdown/JSON/CSV are not rendered or structurally extracted. Unicode characters, CRLF and whitespace retain their exact offsets. Source capture remains bounded at 10 MiB, and invalid UTF-8/NUL/binary-document signatures are rejected.

PDF/Office/email/MIME/archive/image extraction, OCR and base64-document inputs were removed, together with their dependencies, cloud OCR clients and obsolete format-support tests. Retired configuration sections/overrides/environment settings are refused. This intentionally removes those input APIs and extraction metadata from `AnalysisResult.document`, which now contains text, filename, MIME type and method only. The deterministic engine, scores, finding contract, jurisdiction packs, occurrence matcher, historical corpus labels/locks and archived reports remain. Legacy nullable image fields in `ReviewFinding` remain for result-schema compatibility; no active image ingestion produces them.

The user explicitly authorized the prepared root README update, which now describes text-only operation. Nested historical README files and older reports may still describe retired experiments; this document and the current [architecture](../ARCHITECTURE.md) describe the executable scope.

## Automated workflow

`scripts/model_corpus.py` executes these stages without manual annotation:

1. A high-reasoning generator writes new fictional text for a requested quadrant: neither, PII only, MNPI only, or both. The sampling request is an intention, not a reference label. No historical fixtures, detector outputs, protected data or source files are sent.
2. Exactly three judge passes annotate the generated text in separate requests. The default `distinct_models` mode requires three different IDs. The explicit `same_model_repeats` mode repeats one identical judge configuration, with separately recorded pass numbers; this is repeated-sample voting, not cross-model corroboration. Judges see the nine-label PII definitions, contextual MNPI rubric and deterministic word-offset index, without the requested quadrant, generator reasoning or other judges' answers. Different IDs do not establish independent errors; the prepared configuration uses one provider.
3. Local checks reject invalid enums/confidence, duplicate annotations and fabricated or incorrect evidence offsets. Each judge has at most two attempts for known, accounted content failures. Unknown transport/usage stops without retry. No local substring repair changes the evidence.
4. Exact occurrences supported by **two of three** judges become provisional majority annotations; **three of three** are marked unanimous. One-vote occurrences remain challenges. Supporting/dissenting judge indices, per-model confidence/reasons and raw outputs remain available. Abstentions do not lower the denominator.
5. Each judge separately declares document-level PII and MNPI as `present`, `absent` or `unknown`, with a reason and confidence. A positive needs source-grounded positive evidence. A negative requires an explicit exhaustive-completeness declaration and no positive evidence; unresolved materiality/publicity hypotheses prohibit negative MNPI labels. Empty lists alone do not count as negative declarations. These are model assertions, not independently established facts.
6. Two-of-three document votes determine the **observed** quadrant. Only resolved observed labels count toward quotas; unknown, failed, duplicate or excess-quota candidates remain in the audit trail. The scheduler targets the largest remaining deficit and stops at the accepted target, configured candidate limit or budget limit. Shortfalls produce `coverage_shortfall` and a nonzero CLI exit rather than forced labels. All-quadrant targets are mandatory for runs of at least four documents.
7. Accepted examples are compared with the unchanged strict engine. PII uses T3A exact/overlap occurrence matching and the existing narrow crosswalk; unmapped rules are separately counted. Both categories also report document-level TP/FP/TN/FN counts overall and by quadrant. The document prediction is any strict finding in the category, so MNPI detection signals are not verified legal conclusions. Unknown references never count as negatives. Document-level agreement and exact evidence-span agreement are distinct.

Span precision/F2 are conditional **model-label agreement** measurements only where all judges declare exhaustive PII coverage and their PII spans agree unanimously. Majority support alone does not establish completeness. Otherwise those aggregate precision/F2 fields are unavailable. Model-declared completeness is not independently established exhaustiveness. High agreement or self-reported confidence cannot establish real-world accuracy, legal materiality or public status. Report failures, abstentions, disagreements, sample size and selection alongside any metrics. Do not train/tune against this corpus and then claim its scores demonstrate generalization.

## Offline plan and distinct-model example roles

The example configuration is a four-document smoke test, not a paid-run authorization:

```sh
uv sync --frozen --extra dev
uv run --frozen python scripts/model_corpus.py plan --config config/model_corpus.example.json --output /tmp/junas-smoke-plan.json
```

As checked against official documentation on 22 November 2026, the proposed roles are:

| Role | Model | Effort |
|---|---|---|
| Synthetic text generator | `gpt-6.2-astra` | high |
| Separate annotation pass | `gpt-6.2-sol` | high |
| Separate annotation pass | `gpt-5.4-2026-03-05` | high |
| Separate annotation pass | `gpt-5.2-2025-12-11` | high |

Current model capabilities and prices were checked against [Astra](https://developers.openai.com/api/docs/models/gpt-6.2-astra), [Sol](https://developers.openai.com/api/docs/models/gpt-6.2-sol), [GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4) and [GPT-5.2](https://developers.openai.com/api/docs/models/gpt-5.2). The first two IDs are aliases, so configuration attribution does not freeze their underlying weights. The runner stops if the API reports a different resolved model, requiring an explicit identity/pricing review rather than silently accepting drift.

The v2 four-document example targets one accepted document per quadrant, permits up to six candidates, and uses three judges. `config/model_corpus.200.json` targets 50 accepted examples in each quadrant, with up to 300 candidates. The active 200-document configuration now uses Sol generation and three Terra samples with a USD 25 limit inside the user's S$50 allowance; see [the budget revision](model-corpus-200-budget.md). The earlier distinct-model proposal is [preserved separately](model-corpus-200-plan.md). The user-authorized USD25 job has now completed: 200 accepted documents, 50 per quadrant, with USD7.19666825 accounted/reserved; see [the completed results](model-corpus-usd25-results.md). Historical v1 artifacts and source snapshots are retained unchanged; old configuration hashes/authorizations do not authorize v2 runs.

The implementation uses [Responses Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), and [input token counting](https://developers.openai.com/api/docs/guides/token-counting) before each completion. Output-token limits include reasoning tokens. The authorized smoke job exercised these endpoints, model access and structured responses live. Mocked tests separately cover failure, privacy and budget contracts; live compatibility does not establish annotation correctness.

## Paid-run boundary and accounting

Before a live run, establish the API organization/project, approved models/configuration, synthetic-only data scope and USD cap in the local conversation. Funding can be confirmed eligible credits or an explicitly authorized potentially billable cap with unknown credit status. On 22 November the user said to go ahead with the named four-document/USD 5 proposal using the key already in `.env`. The authenticated read-only model-list response identified the organization/project and confirmed those model IDs are available. The reported 15 December expiry, balance and credit applicability remain unverified; no eligible balance was invented. The one-run authorization therefore uses potentially billable capped spending. No key belongs in configuration, source or reports.

`run` additionally requires a private JSON authorization declaration with exactly these fields:

```json
{
  "config_sha256": "COPY THE HASH FROM THE OFFLINE PLAN",
  "organization": "ACTUAL ORGANIZATION ID",
  "project": "ACTUAL PROJECT ID",
  "budget_usd": "ACTUAL APPROVED CAP",
  "available_credit_usd": null,
  "credits_apply": null,
  "data_scope": "new_synthetic_only",
  "funding_basis": "explicit_billable_cap"
}
```

This is an invalid placeholder template, not a general spending approval. Software validates consistency, not the identity of the approver or billing declarations. Alternatively, `funding_basis=confirmed_eligible_credits` requires a confirmed decimal balance at least as large as the cap and `credits_apply=true`. Billable-cap mode deliberately retains unknown credit fields as null. A configuration change changes its hash and invalidates the old declaration. Pricing must have been rechecked within seven days. Once explicitly authorized, the command is:

```sh
uv run --frozen python scripts/model_corpus.py run --config config/model_corpus.example.json --authorization /path/to/private/authorization.json --env-file .env --output /path/to/private/new-run
```

`--env-file` is explicit and loads only `OPENAI_API_KEY`; it does not execute shell expressions, load unrelated settings or read secrets during `plan`. Run directories must be new and outside this checkout. When configuration includes an SGD spending allowance, authorization cannot exceed its embedded USD cap and the FX assumptions must be current; the SGD conversion/fee scenario is conditional, not an invoice guarantee. Before sending a completion, exact preflight input tokens and the maximum output tokens are priced using configured ceilings and reserved against the per-run cap. A reservation is flushed to disk before transport. Missing/inconsistent usage, unexpected billing tier/model or uncertain transport retains the full reserve and stops the run, with no automatic retry. Valid reported usage can release unused reserve. Complete JSON responses are retained even when model/usage validation fails. The cap concerns this run's configured token-price accounting; it does not control unrelated account spending or authenticate a provider invoice/pricing change. No tools, web search, files, images, streaming or provider background jobs are enabled. Requests use the fixed OpenAI endpoint with `store=false`; this request setting is not a separate data-retention guarantee.

Artifacts include the configuration/prompt/schema/source identities, requests and token usage, response IDs/resolved models, complete responses, latency, a cost/reservation journal, source hashes, raw judge annotations, consensus/disagreements, failure/abstention counts and the qualified strict comparison. Existing run directories are never overwritten. No automatic paid resume, training, human acceptance, historical-label promotion or holdout evaluation occurs.

## Historical two-judge smoke result (v1)

The first live pass generated four unique texts, with one fully valid document and three rejected judge outputs: one offset mismatch and two GPT-5.4 responses truncated at the 8,192-token limit. Their raw responses, original records/report and v1 source/configuration snapshot are retained. High reported confidence did not establish correct offsets.

A bounded corrective pass used those same four texts, retained all already valid annotations, and reran only the three invalid GPT-5.4 annotations with the word index and larger output limit. All four documents then had valid, exactly grounded judge outputs; the judges agreed on all 22 PII occurrences but disagreed on contextual MNPI hypotheses in every document. Three had unanimous model-declared exhaustive PII coverage; one lacked unanimous exhaustive coverage and therefore retains unknown coverage. No new sources were generated during correction. The corrected corpus explicitly mixes retained v1 annotations with v2 corrected annotations; it is a development artifact, not an untouched benchmark.

The 15 completed API calls (four generation and eleven judge attempts, including the three initially invalid responses) have an aggregate configured-rate usage cost ceiling of **USD 0.9219475**, including USD 0.6296100 from the initial pass. There are no uncertain requests or outstanding reservations. This is conservative token accounting, not a verified invoice or proof of credit usage. The approved aggregate cap remained USD 5. No larger batch was launched as part of that v1 authorization.

The strict comparison matched four of 22 consensus PII occurrences under the narrow existing label crosswalk. This small, selected model-derived comparison is not population recall or independent accuracy. Aggregate precision/F2 remain unavailable because one document has unknown coverage; two postal-address findings are separately reported as unmapped. Classifier behavior was not tuned on these four examples.

Private reproducibility artifacts, complete responses, attempt histories, source snapshots and corrected records/report are retained outside the checkout at `/home/gongahkia/.local/share/junas/research/2026-11-22-text-only-smoke/`. They contain synthetic development text, not protected holdout data. No API key or `.env` file is included.

## Historical text-only conversion verification

- Full suites on Python 3.11 and 3.12: **1,620 tests and 254 subtests passed** on each version, without skips.
- All nine historical locked-corpus gates passed. Exact strict replay: **1,722 documents / 27,034 findings**, with zero changed result documents, findings, scores or classifications, and zero span/duplicate errors.
- Changed Python formatting/lint, core and scoped runner type checks, provenance, fixture scrub, label-lock freshness, package build and isolated-wheel text classification passed. Existing fixtures, earlier reports and the frozen annotation pilot were hash-checked unchanged.
- An additional unrestricted research type check reports **11 existing errors** in `scripts/span_metrics.py` and `scripts/prepare_evaluation_dataset.py`. Those files were preserved from the task's initial state; this broader check is not clean.
- External corpus downloads/evaluation, real-world/holdout validation and confidence calibration were not run. Historical document/OCR results remain historical; removed support tests are replaced by text-only admission/rejection checks.

Machine evidence is recorded in [the task report](../reports/current/text_only_automated_20261122.json).

## Majority/quadrant implementation verification

The v2 contract adds mocked tests for 2/3 versus 3/3 support, fixed-denominator abstentions, exact-span dissent, negative/unknown labels, all four PII/MNPI quadrants, the materiality/publicity state table, both categories' document confusion counts, bounded refill/shortfalls and a complete 200-document mocked run. See [the prepared run and current checks](model-corpus-200-plan.md). Model inference for the new prompt/schema and third judge remains untested live; no accuracy or confidence-calibration claim follows from mocked checks.

## Completed USD25 corpus job

The approved job filled all four quotas using Sol generation and three Terra judge passes: 200 accepted from 214 candidates, with 12 unresolved and two incomplete candidates retained separately. Three known evidence/offset failures were corrected within the pre-approved attempt bounds. An offline audit verified grounding, unique request fingerprints, usage/journal linkage, quotas and deterministic evaluation. Operator-reviewed continuations preserved all old artifacts and carried full uncertain reserves forward within the same USD25 cap; neither uncertain request/source was retried. [Results and artifact links](model-corpus-usd25-results.md) distinguish model-reference agreement, target-scope disagreements, sparse subtype coverage and unverified confidence from independent accuracy.
