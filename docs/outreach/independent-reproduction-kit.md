# SG-LegalBench Independent Reproduction Kit

This kit is for an institutional partner that can run SG-LegalBench v0.1
independently, keep the raw receipt JSON, and publish the result as an
external reproduction alongside the project-maintained baseline runs. It is
designed for SMU SOLID, NUS TRAIL, SAL/LawNet Technology Services, or a similar
research or legal-data team with one ML engineer and one named institutional
reviewer.

SG-LegalBench is an open Singapore legal-reasoning benchmark for LLMs. The
load-bearing methodology is simple: use public-domain Singapore sources,
derive labels mechanically where possible, run strong evaluators in `--strict`
mode, and publish receipt files with provenance, bootstrap confidence
intervals, and contamination summaries. The benchmark is not legal advice and
does not claim to resolve any underlying legal question.

An independent reproduction is valuable because it separates "we ran our own
benchmark" from "a third party can run the same suite and obtain inspectable
receipts." Even one external reproduction with a published receipt, confidence
intervals, contamination probe output, and reviewer sign-off is a large
credibility improvement for SG legal-tech users deciding whether to trust the
leaderboard.

## What We Are Asking For

Run the v0.1 eligible suite against either:

- the institution's Singapore-law model of choice, if one is available; or
- a named frontier model using the institution's own API key and environment.

Publish the output under:

```text
runs/external/<institution>/
```

Each external run directory should contain:

- `README.md` with institution name, runner, reviewer, model label, provider,
  date, commit SHA, and any deviations from the contract.
- One receipt JSON per task, emitted by `--output`.
- The receipt's `per_evaluator_bootstrap` fields, which are the published
  confidence intervals. See [Benchmark receipt schema](../../backend/benchmark/receipt_schema.md).
- The receipt's `contamination_summary` when `--contamination-probe` was run.
  See [Contamination probe methodology](../methodology/contamination.md).
- Optional `notes.md` for rate limits, failed cases, excluded tasks, or
  institution-specific review comments.

## Technical Contract

### 1. Install

Use a fresh clone and virtual environment.

```sh
git clone https://github.com/gongahkia/junas.git
cd junas
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e backend
```

Then run the benchmark commands from `backend/` so the local `benchmark`
package is on the Python path.

```sh
cd backend
../.venv/bin/python -m benchmark.cli list
```

### 2. Configure the Model Runner

The default registered tasks are oracle wrappers used to exercise the harness.
They return gold labels and must not be published as a model score.

For an LLM run, register an LLM-backed task with `benchmark.llm_runner` and the
institution's provider credentials. The receipt should include a non-empty
`provenance` block with `prompt_version`, `prompt_sha`, `provider_label`, and
`max_tokens`. The operational walkthrough is the vendor self-eval guide from
NEW-VENDOR-GUIDE, expected at `docs/vendor-self-eval-guide.md`; the receipt
schema remains authoritative at
[backend/benchmark/receipt_schema.md](../../backend/benchmark/receipt_schema.md).

Provider keys stay in the institution's environment. Do not commit keys,
provider logs containing secrets, or paywalled source text.

### 3. Select Tasks

Run the current v0.1 eligible tasks first. SGLB-05, SGLB-06, and SGLB-07 may
have code in the tree, but they should not be treated as the external v0.1
suite unless their data is explicitly marked leaderboard-eligible in the
release notes.

| Task | Dataset | Evaluators | Notes |
| --- | --- | --- | --- |
| SGLB-01 PDPA Outcome | `benchmark/datasets/sglb_01_pdpa.yaml` | `sglb_01_obligations_f1`, `penalty_band_mae` | 211 public PDPC cases |
| SGLB-02 Statute QA | `benchmark/datasets/sglb_02_statute_qa_full.yaml` | `sglb_02_citation_match`, `rouge_l_answer` | 500-case full dataset; use `sglb_02_statute_qa.yaml` for the 78-case PDPA smoke |
| SGLB-04 Citation Verify | `benchmark/datasets/sglb_04_citation_verify_full.yaml` | `multi_label_f1` | 1,080-case full grammar set; use `sglb_04_citation_verify.yaml` for the 30-case smoke |
| SGLB-08 Clause Tone | `benchmark/datasets/sglb_08_clause_tone_reviewed/dataset.yaml` | `multi_label_f1` | 400 reviewed synthetic clauses; publish under the synthetic tier |

SGLB-04's citation grammar and SGLB-02's citation comparison use mechanical
normalisation rules. The audit contract is in
[Citation and statute normalisation spec](../normalisation-spec.md).

### 4. Run Strict Receipts

Run a smoke receipt first with `--strict` and a low concurrency value. Replace
the workflow name with the LLM-backed task name registered for the model, for
example `sglb_04_llm_external`.

```sh
cd backend
../.venv/bin/python -m benchmark.cli run \
  --workflow sglb_04_llm_external \
  --dataset benchmark/datasets/sglb_04_citation_verify.yaml \
  --evaluator multi_label_f1 \
  --strict \
  --max-concurrency 2 \
  --output ../runs/external/<institution>/sglb_04_smoke_<model>.json
```

Then run the full eligible suite.

```sh
../.venv/bin/python -m benchmark.cli run \
  --workflow sglb_01_llm_external \
  --dataset benchmark/datasets/sglb_01_pdpa.yaml \
  --evaluator sglb_01_obligations_f1 \
  --evaluator penalty_band_mae \
  --strict \
  --contamination-probe \
  --max-concurrency 2 \
  --output ../runs/external/<institution>/sglb_01_<model>.json

../.venv/bin/python -m benchmark.cli run \
  --workflow sglb_02_llm_external \
  --dataset benchmark/datasets/sglb_02_statute_qa_full.yaml \
  --evaluator sglb_02_citation_match \
  --evaluator rouge_l_answer \
  --strict \
  --contamination-probe \
  --max-concurrency 2 \
  --output ../runs/external/<institution>/sglb_02_<model>.json

../.venv/bin/python -m benchmark.cli run \
  --workflow sglb_04_llm_external \
  --dataset benchmark/datasets/sglb_04_citation_verify_full.yaml \
  --evaluator multi_label_f1 \
  --strict \
  --max-concurrency 2 \
  --output ../runs/external/<institution>/sglb_04_<model>.json

../.venv/bin/python -m benchmark.cli run \
  --workflow sglb_08_llm_external \
  --dataset benchmark/datasets/sglb_08_clause_tone_reviewed/dataset.yaml \
  --evaluator multi_label_f1 \
  --strict \
  --contamination-probe \
  --max-concurrency 2 \
  --output ../runs/external/<institution>/sglb_08_<model>.json
```

If a task fails because the provider cannot return valid JSON, keep the failed
receipt. JSON failures are part of the model-quality record and should not be
hidden by manual retries unless the rerun is clearly labelled.

### 5. Read The Receipt

Before publishing, check every receipt for:

- `strict: true`
- `weak_evaluators_used: []`
- `provenance.provider_label` naming the exact provider and model
- `provenance.prompt_sha` and `provenance.prompt_version`
- `per_evaluator_mean` for headline scores
- `per_evaluator_bootstrap.<evaluator>.ci_low` and `ci_high` for 95 percent
  bootstrap confidence intervals
- `contamination_summary.mean_memorisation_rate` for SGLB-01, SGLB-02, and
  SGLB-08 when the probe is enabled
- `contamination_summary.contamination_adjusted_score` where a clean subset
  remains after memorisation flags

The contamination probe asks a separate recall-style question with the benchmark
input withheld. A high memorisation rate does not make a model bad, but it does
mean the ordinary score may be measuring recall of public labels rather than
reasoning from the supplied prompt.

### 6. Publish The External Run

Open a PR that adds only:

```text
runs/external/<institution>/
```

Use this PR title shape:

```text
docs(runs): add <institution> independent reproduction for <model>
```

The run directory README should say whether the institution consents to:

- listing the reproduction beside the leaderboard;
- naming the institution and reviewer in the v0.2 preprint acknowledgements;
- co-authorship, if the contribution includes substantive methodology review,
  new error analysis, or a material reproducibility improvement.

If the institution wants a pre-publication check, send the receipt bundle first
and hold the PR until their communications or legal team approves publication.

## What The Institution Gets

- A link from the SG-LegalBench leaderboard and reproduction notes.
- A citable external receipt bundle showing model score, confidence interval,
  contamination summary, and prompt provenance.
- Co-authorship consideration on the v0.2 preprint if the institution makes a
  substantive contribution beyond running the commands.
- Visibility as an early Singapore legal-tech benchmark reproducer.

## Compute Estimate

These estimates assume one hosted frontier-model call per benchmark case, a
second call for contamination probes on SGLB-01, SGLB-02, and SGLB-08, and no
manual retries. Provider pricing changes, context length, and reasoning-token
billing can dominate the final bill.

| Task | Cases | Calls with probe | Wall-time at concurrency 2 | Hosted-model budget envelope |
| --- | ---: | ---: | --- | --- |
| SGLB-01 | 211 | 422 | 20-60 min | USD 5-25 |
| SGLB-02 full | 500 | 1,000 | 45-120 min | USD 10-60 |
| SGLB-04 full | 1,080 | 1,080 | 60-180 min | USD 10-80 |
| SGLB-08 | 400 | 800 | 30-90 min | USD 8-50 |
| Quick smoke pass | 719 | 1,408 if probed | under 90 min | USD 5-40 |

The quick smoke pass means SGLB-01 and SGLB-08 at their current shipped size,
plus the 78-case SGLB-02 PDPA smoke and 30-case SGLB-04 smoke.

[Inference] The practical budget for a full strict reproduction is one engineer
day and roughly USD 50-250 of hosted-model spend, unless the selected provider
uses expensive reasoning tokens. Local Ollama runs trade token cost for longer
wall-time and hardware variability; record the machine and model quantisation in
the run README.

## Timeline

Target elapsed time from outreach to published receipt: 4-6 weeks.

| Week | Activity | Owner |
| --- | --- | --- |
| 1 | Intro call, scope confirmation, model choice, publication approval path | Maintainers + institution lead |
| 2 | Local install, smoke run, provider credentials confirmed | Institution ML engineer |
| 3 | Full strict run and contamination probes | Institution ML engineer |
| 4 | Receipt review, failed-case notes, CI and contamination summary check | Institution reviewer + maintainers |
| 5 | Optional methodology comments, communications/legal review | Institution lead |
| 6 | PR opened, receipt published, leaderboard link added | Maintainers + institution |

For outreach sent on 6 June 2026, the 4-6 week window lands between
4 July 2026 and 18 July 2026. [Inference] That is before the main August
teaching term for both NUS and SMU, which makes it a reasonable pre-semester
research sprint if approvals do not require a formal MOU.

## If They Disagree With A Label

Use the public [dispute and errata process](../dispute-process.md). The short
version: file a label-dispute or methodology-concern issue with task ID, case
ID, dataset version, public evidence URL, and suggested correction. Maintainers
triage within 14 calendar days and accepted disputes land through a versioned
corrigenda release.

## Bundle Checklist

To send this as a single Markdown or PDF bundle, include:

1. This kit.
2. [Cover letter template](cover-letter-template.md).
3. [Three target briefs](three-targets.md).
4. Links to the receipt schema, contamination methodology, normalisation spec,
   and dispute process above.
