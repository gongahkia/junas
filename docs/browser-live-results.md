# Real browser development benchmark — 28 November 2026

The real WebLLM worker completed all **144 authored short development cases** in a visible Chromium window using the laptop's Intel GPU. Native selection, processing and optional redaction worked. **The candidate fails seven of nine quality targets and is not ready to become the classifier.** No paid API calls were made.

The [machine-readable report](../reports/current/browser_live_development_v1.json) retains every case, accepted proposal, error, unchanged target, model/build identity and observation metadata. These are authored synthetic expectations, not independent accuracy, legal ground truth or an unseen holdout. The earlier [deterministic replay](browser-prototype-results.md) is a separate, preserved result.

## Quality result

| Outcome | Documents |
|---|---:|
| Attempted / planned | 144 / 144 |
| Rejected by source-quotation validation | 42 |
| Accepted but marked incomplete by the model | 102 |
| Accepted complete proposals | 0 |

Every accepted proposal had `complete: false`; the existing contract therefore retained `unknown` for both categories. PII-positive detection was **0/72**, MNPI-positive detection **0/66**, and exact/overlapping typed PII span matches **0/72**. Twelve PII candidate spans and seven MNPI candidate intervals survived quotation validation, but none of those PII spans matched a reference span, even by typed overlap. Six authored ambiguous MNPI cases returned unknown. Zero negative flags do not establish useful specificity when every case is unknown or rejected.

All 42 rejected proposals produced the same validation message: a quotation was absent from the source or had ambiguous repeated occurrences. This message does not distinguish invented quotations from repeated matches. Rejected proposals remained failures in every denominator; validation was not relaxed. The seven failed targets cover positive detection, PII span agreement and excessive abstention. The two negative-flag targets pass mechanically, without making the candidate usable.

This measures the pinned model, prompt, structured-output configuration and validator together. It does not isolate whether model capability, prompt design or schema interaction causes the persistent incomplete responses. Those require separate development experiments; this run was not retuned after inspection. Fresh unseen validation is still required after any such changes.

## Timing and resources

| Measurement | Observed |
|---|---:|
| Complete sequential run | 1,079.28 s (17.99 min) |
| All-attempt wall time, p50 / p95 | 5.23 s / 15.58 s |
| Accepted-proposal inference, p50 / p95 | 4.94 s / 11.74 s |
| Accepted-proposal inference samples | 102 |
| Sampled sum of Chromium process RSS, peak | 2,246.67 MiB (about 2.19 GiB) |
| Initial observed asset responses | 986,617,134 bytes across 67 requests |
| External HTTP requests during the completed benchmark | 0 |

All-attempt timing comes from status transition timestamps and includes the 42 validation failures and first-case cached initialization. The inference percentiles exclude rejected proposals because their worker errors do not carry inference timings; they must not be presented as the latency of all requests. This is one sequential run on a shared laptop, without controlled hardware comparisons or repeated warm runs.

Memory was sampled every two seconds for 521 samples within the benchmark, starting 25.75 seconds after its first case. Summed process RSS can count shared pages more than once, does not account precisely for GPU memory, and can miss transient peaks. It is not a total model-memory measurement. The asset response count includes redirects and headers as reported by Playwright; it is neither pure weight size nor installed footprint. Complete cold initialization timing was not reliably captured.

From case 51 through post-run export, a page PerformanceObserver recorded no main-thread tasks over 50 ms. A 100 ms timer recorded one drift over 50 ms (maximum 61.5 ms), with no hidden-page samples. This limited observation does not establish a frame-rate, responsiveness or battery guarantee. Energy use, precise peak GPU memory and other devices/platforms were not measured. The results do not justify calling this candidate lightweight.

## Live interaction checks

The native check used actual mouse selection on a fictional source page and the browser's **Process selected text with Junas** context-menu action. It opened a processing tab containing exactly the selected passage, excluding another paragraph. The source page was unchanged and the pending extension session entry was consumed. This check did not inject selection storage. Its result was observed live and captured in a browser-scoped screenshot; it is distinct from the CI flow's mocked worker.

A separate 38-byte smoke passage, `Personal email: alice.tan@example.com.`, produced a grounded EMAIL candidate. With networking disabled on the isolated browser context **before opening the processing page**, a newly created worker loaded cached assets in **4.45 s**, then performed real inference in **7.37 s**. The proposal remained incomplete/unknown. Selecting the candidate, previewing and copying produced `Personal email: [REDACTED].` while retaining the original text. This demonstrates cached offline operation for this profile/device and passage; it does not improve the failed development result. Networking was restored afterward.

Additional live checks passed: importing actual CLI JSON for the exact passage; rejecting JSON for another passage; hiding/clearing findings and redaction after a source edit; explicitly rejecting blank and 1,025-byte input; and cancellation after model loading. Six seconds after cancellation, no result had appeared and input was enabled. The [saved browser-only screenshot](/home/gongahkia/.local/share/junas/research/2026-11-28-live-browser/real-extension/offline-real-redaction.png) shows the offline redaction flow. Raw synthetic captures, isolated profile/cache and artifact hashes are retained in the private research evidence directory; no unrelated desktop capture is included.

## Runtime, repairs and verification

The candidate was `Qwen3-1.7B-q4f16_1-MLC`, WebLLM 0.2.89, with pinned weight/library revisions. The completed run used build `0d003d935496e125ee18c8839e0577e640133eca1c091780cf644511e875f2c8`. Hardware was Intel Iris Xe Graphics (RPL-U), 16 GiB system RAM, Mesa 26.2.5 and native Chromium 158.0.8127.88. A headed Linux X11/Vulkan configuration exposed the real Intel `shader-f16` adapter. Process-local flags are recorded in the report and live harness; no system or normal browser-profile configuration was changed. The standard headless probe still lacked a suitable adapter.

Live testing found two defects before the completed run:

- WebLLM prepends an exact empty `<think>` header even when thinking is disabled. Decoding now removes only that exact header before JSON validation; nonempty thinking, fabricated quotations, malformed JSON and truncated generations remain rejected.
- The benchmark originally stopped after three validation failures. It now records rejected proposals and continues case coverage in the same worker, while three consecutive infrastructure failures still stop the run. The original four-attempt partial report is retained separately and is not pooled with the completed run.

Verification passed: **19 Node tests**, extension bundling, the isolated Chromium flow suite with its explicitly mocked worker and blocked HTTP(S), and `node --check test/live-session.mjs`. The real-model evidence above is separate from those mocked checks. Hosted CI was not run. No Python runtime code changed in this work; the prior Python suites were not repeated.

Two earlier isolated windows closed, and their cause remains unverified. The later full run completed without another observed closure; that does not establish long-term stability. The Junas test window is left open for the user's live testing. The root README remains unchanged under its existing editing restriction.

**New paid inference spend: USD0.** No classifier promotion, paid reference generation or fresh holdout run is implied by these results.
