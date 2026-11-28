# Junas browser research prototype

Highlight text, right-click and choose **Redact with Junas**. Junas captures that exact selection and starts local processing in the background. Findings in enabled categories that meet the configured model-estimated confidence threshold are replaced in the original selection. It does not open a popup or tab. Use the browser's extensions toolbar to open settings and recent local history.

The popup saves the selected model, threshold (default 85%), and PII/MNPI switches. Confidence is an **uncalibrated model estimate**, not independently validated accuracy. Incomplete assessments, unknown categories, invalid quotations and findings below the threshold do not trigger automatic replacement. First use downloads model assets.

The most recent **20** inputs, redacted outputs and outcomes are stored in the extension's IndexedDB, including sensitive source text. History survives closing the browser; individual deletion and clear-all are available. Settings persist separately. No remote history service or analytics was added. Source/result expiry in the active processing session does not delete saved history.

Replacement uses a captured DOM range or textarea/input selection rather than searching for repeated text. Changed/disconnected/expired source selections are refused. Page replacements insert plain text, so selected formatting can be flattened. Protected pages or frames may deny injection, and application-managed editors may revert DOM changes; these are explicit failure/compatibility limits, not a guarantee of universal page support.


## Build and load

Requires Node 22.12+ and a Chromium browser with a usable WebGPU adapter supporting `shader-f16` for the pinned model.

```sh
cd browser
npm ci --ignore-scripts
npm test
npm run build
```

Open `chrome://extensions`, enable Developer mode, choose **Load unpacked**, and select `browser/dist`. Browser installation is manual; this repository does not publish or install the extension into your normal profile.

The candidate is `Qwen3-1.7B-q4f16_1-MLC` with WebLLM 0.2.89. Weight and compiled-library repository revisions are pinned in `src/model.js`; builds hash the relevant source, dependency lock, prompts and targets. A [real 144-case development run](../docs/browser-live-results.md) completed on Intel WebGPU but **failed seven of nine quality targets**: 42 proposals were rejected and all 102 accepted proposals were incomplete/unknown. This candidate is not promoted. Lightweight operation and generalization are not established.

## Processing and data boundaries

- First processing downloads model/tokenizer/compiled assets from Hugging Face and the MLC library repository. Weights are additional to the extension bundle. Cached assets can remain on the device.
- There is no API key, remote classification endpoint, cloud fallback or autonomous tool loop. The worker rejects `fetch` after model initialization. A newly created real worker successfully loaded cached assets and processed one smoke passage with its isolated browser context offline; see the live report for device and timing limits.
- Capture uses only the browser’s explicit `selectionText` event. A one-shot `activeTab`/`scripting` injection anchors and replaces that selection after the explicit menu action. No persistent content scripts or broad host permissions are requested.
- The offscreen session keeps the current passage and result in memory. Context-menu processing does not open a popup or tab; the toolbar badge indicates progress or completion. Closing a review view leaves processing running. Cancellation terminates the worker. The idle model is released after five minutes; source/results expire after fifteen minutes without an assessment or settings change. Browser shutdown clears the in-memory session.
- Input is capped at 1,024 UTF-8 bytes, with an additional conservative full-prompt/context check that can reject shorter passages. The prototype does not silently truncate. It handles a single selected passage, not full-document coverage.
- A fixed structured response is checked for valid shape, categories, unique exact quotations, source bounds and contradictory state/evidence combinations. Offsets use Unicode code points, matching Python. These checks establish quotation grounding; they do not establish semantic linkage, legal materiality, truth of public status or exhaustive PII coverage.
- Incomplete output, invalid evidence, an unavailable model/device, cancellation and timeout produce explicit failure/uncertainty. A complete model response can still be wrong.
- Manual redaction review in the popup operates on a copy; the context-menu action applies the saved automatic policy to the page. Findings are initially unchecked. Quoted MNPI components are redacted as their containing evidence interval, which may include intervening text; the preview exposes this before copy. Editing the source invalidates findings and the preview.

The browser model emits `junas.browser.proposal.v1`, marked `classification_applied: false`. It is separate from the Python `junas.review.v2` deterministic result. An optional comparison panel imports CLI JSON for **exactly the same text**; it does not invoke Python from the browser or fuse decisions. Automatic Python bridging and a model-assisted primary classifier remain future work, contingent on measured quality.

## Development evaluation

Open the extension's `benchmark.html` page by replacing `process.html` in its URL. Clicking **Run local benchmark** processes 144 authored short cases through the same worker and evidence validation. It records all four quadrants, family-level agreement, typed PII span matches, failure counts, individual inference timings, p50/p95 and model/build identities. Inference timings cover accepted proposals only; rejected proposals do not supply worker timing. Load time is separate from inference. Missing/error cases remain in denominators. Three consecutive infrastructure failures stop the run; per-case timeouts and a 60-minute loop deadline bound work. Stop produces a partial report rather than discarding failures. Downloading a report is explicit.

The cases cover 16 issuer-event families with two wording/layout variants and all quadrants, plus eight edge-case families. They include all nine contextual PII subtypes. **These are authored development expectations, not independently validated legal labels or a fresh holdout.** Repeated entities and template structure limit independence. All cases are added to future synthetic holdout exclusion fingerprints. Existing holdouts, annotations and locked gates remain unchanged. Rejected model proposals are recorded as validation failures while the same worker continues; three consecutive infrastructure failures still stop the run.

Replay the deterministic classifier and score its results without model calls:

```sh
# from the project root; use an environment installed with the project
python scripts/evaluate_short_cases.py --output /tmp/junas-short-rows.json
cd browser
node eval/score.mjs eval/cases.json /tmp/junas-short-rows.json /tmp/junas-short-report.json
```

Outputs refuse overwrites. `npm run eval:generate` reproduces `eval/cases.json`; tests check that it matches its generator. The same nine existing development quality targets are reported without lowering thresholds. A passing authored suite would still not establish generalization.

## Verification limits

`npm run test:browser` uses an isolated Chromium profile and a **mocked model worker**, with HTTP(S) requests blocked. It exercises extension loading, real session-storage handoff, unavailable-device handling, processing UI, explicit redaction/copy, changed-source invalidation, clearing and narrow layouts. It does not measure model accuracy, model download size, model load/inference latency or peak GPU memory.

```sh
npx playwright install chromium
npm run test:browser
# alternatively, use a system Chromium:
JUNAS_CHROMIUM=/usr/bin/chromium npm run test:browser
```

On the development machine's standard headless Chromium, WebGPU was exposed but no adapter was available. An additional software-adapter probe lacked `shader-f16`. Later headed Linux tests with explicit process-local Vulkan flags ran the real Intel GPU, native selection/context-menu handoff, cached offline processing and redaction. The [live report](../docs/browser-live-results.md) records the failed quality result, observed asset responses, latency, approximate process RSS and remaining limits. Complete cold-start timing, precise GPU memory, energy use and cross-device performance remain unverified. No paid API inference was used. The browser CI workflow is prepared; hosted CI has not run locally.

## Live Linux research harness

For a real-model session on this Linux machine, use an isolated persistent profile and a private evidence directory:

```sh
JUNAS_CHROMIUM=/usr/bin/chromium \
JUNAS_LIVE_OUTPUT=/absolute/private/evidence-directory npm run test:live
```

The harness opens a headed Chromium window with explicit X11/Vulkan/WebGPU test flags, loads only the unpacked Junas extension, reports the observed adapter, and accepts one JSON command per stdin line. It does not use a mocked worker or a paid API. Use fictional data; explicitly saved evaluations and screenshots can include the source text. Model assets remain cached in the private profile for warm/offline checks. The test flags are process-local and do not modify the user's browser configuration.

```json
{"action":"goto","url":"/benchmark.html"}
{"action":"click","selector":"#run"}
{"action":"snapshot"}
{"action":"download","selector":"#download","name":"benchmark.json"}
{"action":"close"}
```

Other supported actions are `fill`, `press`, `mouse`, `upload`, `evaluate` (optionally `save`), `screenshot`, `newest` and `offline`. Native context-menu selection still needs native browser interaction; programmatically injecting session storage is not equivalent evidence. The initial headless limitations above are historical; a successful live run must be reported separately with its actual hardware, flags, build identity, failures and timing coverage.

## Browser panel research

The T3 browser panel can run the real model and a preview of the popup UI. It cannot open `chrome://extensions`, so that preview does not verify toolbar installation or Chrome permissions. `npm run test:browser` separately exercises real extension/offscreen messaging with an explicitly mocked model.

```sh
cd browser
npm run build
node research/build-panel.mjs
./node_modules/.bin/esbuild research/automatic.js --bundle --format=esm --outfile=dist/research-automatic.js
python research/serve.py --output /absolute/private/research-output
```

Open port 8766 `/panel.html` in T3 for the compact UI, or `/benchmark.html` for research. The research-only server writes bounded, atomic checkpoints on loopback. It is not part of the distributed extension. After opening the benchmark, importing `/research-automatic.js` and calling `runResearch()` runs the fixed 32-case screens, freezes the strongest exploratory candidate, evaluates all 144 development passages, then evaluates 48 frozen authored validation passages. No paid endpoint is used, and failed gates do not trigger model promotion. The validation set is separate from the prompt and selection set; its authored labels and template dependence do not establish independent accuracy.

The popup uses neutral light/charcoal surfaces and muted green, with progress, evidence and explicit redaction; selected source text is available in a collapsed read-only section. Model selection and diagnostics are tucked into details. The layout takes inspiration from [Obsidian Web Clipper](https://obsidian.md/clipper), with no purple colorway.

The confidence-enabled redaction request is identified as `redaction-estimates-v1`. Historical v3 classification benchmarks do not validate the accuracy or calibration of this new request. Research preview data is origin-local and separate from installed-extension history.

### Actual redactor and source-anchored research

`research/redactor-run.js` evaluates the actual confidence-enabled request and checkpoints every completed case. `research/redactor-metrics.js` replays category switches, confidence thresholds and the popup's MNPI scope setting without additional inference. Exact evidence scope is the default; optional sentence expansion is limited to the selected passage. Confidence estimates are uncalibrated. PII has authored character spans; MNPI currently has passage-level labels and an allowable event/disclosure paragraph, **not independently annotated minimal spans**. Removal within that paragraph is not evidence of minimal redaction quality.

The separate source-anchored candidate restricts quotes to unique exact source substrings and uses explicit schema alternatives for category/evidence consistency. Its catalog contains up to twelve consecutive whitespace-delimited words, trimmed punctuation variants, unique lines and the full passage. This finite catalog can exclude useful subword evidence and can still permit overly broad or semantically wrong quotes. Source grounding does not verify that a quotation establishes its claimed meaning. The candidate is excluded from the distributed extension.

Build into a new research directory alongside the running server's assets:

```sh
node research/build-anchored.mjs \
  --output /absolute/research-assets/anchored-v2 \
  --validation /absolute/private/validation-frozen.json
```

The build refuses overwrites and verifies the original 48-case reference artifact's hash. Open `/anchored-v2/anchored-eval.html?mode=smoke` in the T3 panel for eight development cases. After inspecting them, `?mode=all` runs the fixed 32-case screen for each pinned model, all 144 development cases for the selected candidate, then the 48 frozen validation cases. Completed rows are reused only for the same source and build identity. The default policy stays at 85%, both categories enabled, exact MNPI evidence scope. Selection maximizes the weaker of PII character recall and MNPI document redaction recall, then prefers fewer changed negative documents and failures. A failed development gate remains explicit; validation is then exploratory and does not authorize promotion. Validation follows a saved configuration freeze and cannot affect model selection.

Each source-anchored case uses a fresh worker to bound the lifetime of per-source compiled grammars; this also adds cached model initialization overhead. Errors remain in recall denominators. Both scope choices, all four category combinations and six fixed thresholds are replayed from the same proposals. A separate shadow result combines explicit-context local PII patterns with accepted model findings. Those patterns have no probability score and bypass the model threshold only in this research comparison; they are not enabled in the product. All runs use local WebLLM inference and make no paid API calls.
