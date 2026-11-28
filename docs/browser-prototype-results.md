# Browser prototype and short development evaluation

The selected-text extension prototype and broader short development suite are implemented. The old document/finding numeric scores and `SAFE`/`LOW_RISK`/`HIGH_RISK` document decision were removed in review v2. Detector evidence and contextual decisions were preserved across 1,722 regression documents after excluding only the removed fields and the new version marker. This is an API cleanup, not an accuracy improvement.

## Product flow and current boundary

Highlight text on a normal page, choose **Process selected text with Junas**, and keep the processing tab open while a local worker evaluates it. Findings can be selected for explicit redaction preview and copy. The source page is not rewritten. Source edits invalidate results; clear/cancel terminates pending work. No cloud classifier, API key, telemetry or autonomous agent loop was added.

The candidate WebLLM runtime, model weights and compiled-library revisions are pinned. Exact source quotations and code-point offsets are validated outside the model, but semantic correctness, exhaustive detection and legal/public-status truth remain unverified. The model result is a separate proposal rather than an override of Python's deterministic assessment. Exact-text CLI JSON can be imported for comparison. Automatic fusion and an installed local model adapter remain unimplemented.

## Broader development evidence

[The saved report](../reports/current/browser_short_development_v1.json) records **144 authored synthetic passages**, each at most **291 UTF-8 bytes**. The core has 16 event families, two wording/layout variants and 32 documents in each of the four PII/MNPI quadrants. Sixteen additional documents cover eight edge-case families, including negation, hypothetical events, mixed issuers, contradictory disclosure, missing evidence and instructions inside a document. All nine PII subtypes are represented.

These are authored development expectations. Reused names, identifiers, issuer names and template patterns limit independence; the labels are not independent legal ground truth. No model judges or new paid calls were used to create them. Their source fingerprints are added to future holdout exclusions and the case file is included in future source snapshots. Prior frozen holdouts, reference labels and locks are unchanged.

On this suite, the deterministic classifier **fails five of the nine existing targets**:

| Measurement | Observed |
|---|---:|
| MNPI-positive detections | 10/66 |
| MNPI-positive abstentions / negative predictions | 24/66 / 32/66 |
| MNPI-negative flags / abstentions | 0/72 / 16/72 |
| Ambiguous MNPI expectations returned unknown | 6/6 |
| PII-positive detections | 37/72 |
| PII-negative flags / abstentions | 0/72 / 0/72 |
| Exact / overlapping typed PII spans | 30/72 / 30/72 |

Failed targets are PII-positive detection, both PII span metrics, MNPI-positive detection and MNPI-positive abstention. Four targets pass. No rule tuning followed inspection. This supports continued investigation; it does not establish that a browser model is better.

Observed deterministic replay inference timings were p50 **4.03 ms** and p95 **9.03 ms** on this machine. These are one local replay's measurements, not hardware-independent performance claims. Browser inference timing remains unavailable. The browser benchmark processes the same passages through its worker, records load time separately, reports per-document and p50/p95 inference latency, keeps failures in denominators, and stops on cancellation or repeated failures. No fresh or independent evaluation is claimed.

## Verification and remaining limits

- Full Python 3.11 and 3.12 suites: **1,932 tests and 254 subtests pass on each**.
- Nine unchanged corpus gates pass across 1,722 documents. Evidence/decision equivalence was separately checked against the pre-removal source with network access denied.
- Full mypy passes 108 source/evaluation files, with the existing unused `junas.cli` config note. Changed Python Ruff lint/format checks pass. Wheel and source distribution builds pass.
- Clean `npm ci --ignore-scripts`, 18 Node tests and extension bundling pass. Browser tests load the unpacked extension in an isolated Chromium profile and check session handoff, unavailable-device handling, mocked processing, explicit redaction/copy, source invalidation, clear/cancellation races and narrow layout with all HTTP(S) requests blocked.
- Standard headless Chromium exposed WebGPU but no usable adapter. A software-adapter probe lacked `shader-f16`, required by this pinned candidate. **Actual model execution, model accuracy, cold/warm model loading, offline-ready operation, peak memory, weight download size and native context-menu interaction remain unverified.** No weights were downloaded. Mocked browser results are not model evaluation.
- The browser CI workflow is prepared; hosted CI was not run or triggered. The root README predates review v2 and remains unchanged under its editing restriction; use the migration and browser instructions for the active contracts.

**New paid inference spend: USD0.** No old allowance was reopened. The next discriminating experiment is the same frozen candidate and short-case benchmark on a compatible WebGPU device, with its results kept separate from this deterministic baseline. Any new paid reference generation still needs a separate cost proposal and authorization.

Build/load commands and device requirements are in the [browser instructions](../browser/README.md); architecture limits and the proposed integration are in [local-model direction](local-model-direction.md).
