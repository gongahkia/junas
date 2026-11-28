# Junas browser research prototype

Open the Junas toolbar popup, capture the highlighted passage or paste text, then choose **Process locally**. The context-menu action also starts assessment. A Chrome offscreen document hosts the local WebLLM worker so closing the popup does not cancel processing. Review its proposed evidence, select findings to redact, then preview and explicitly copy the redacted text. The original page is never edited by this prototype. Opening the extension's toolbar action also supports pasted text.

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
- Context-menu capture uses the browser's explicit `selectionText` event. Toolbar capture uses `activeTab` and `scripting` on a user gesture to return only the selection in the top frame or focused text field; password fields are excluded. There are no persistent content scripts or broad host permissions. Only that selection is assessed; a passage can omit essential MNPI context.
- Pending selections use trusted extension session storage, opaque URL references and a bounded queue. Entries expire after five minutes when next accessed/cleaned, are removed on consumption, and do not use persistent local history. Results remain in the processing tab. Clear terminates the worker and clears text/results; closing a review view leaves processing running. The idle worker is released after five minutes; source/results expire after fifteen minutes without a new assessment or edit. Browser shutdown clears the in-memory session.
- Input is capped at 1,024 UTF-8 bytes, with an additional conservative full-prompt/context check that can reject shorter passages. The prototype does not silently truncate. It handles a single selected passage, not full-document coverage.
- A fixed structured response is checked for valid shape, categories, unique exact quotations, source bounds and contradictory state/evidence combinations. Offsets use Unicode code points, matching Python. These checks establish quotation grounding; they do not establish semantic linkage, legal materiality, truth of public status or exhaustive PII coverage.
- Incomplete output, invalid evidence, an unavailable model/device, cancellation and timeout produce explicit failure/uncertainty. A complete model response can still be wrong.
- Redaction is optional and operates on an explicit copy. Findings are initially unchecked. Quoted MNPI components are redacted as their containing evidence interval, which may include intervening text; the preview exposes this before copy. Editing the source invalidates findings and the preview.

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

The popup uses neutral light/charcoal surfaces and muted green, with the selected-text field, one primary processing action, evidence and explicit redaction. Model selection and diagnostics are tucked into details. The layout takes inspiration from [Obsidian Web Clipper](https://obsidian.md/clipper), with no purple colorway.
