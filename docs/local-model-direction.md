# Local-model classification direction

Status: a [browser extension research prototype](../browser/README.md) now implements selected-text capture, a pinned WebLLM worker, quotation validation and explicit redaction preview/copy. Its real-model execution and accuracy remain unverified on the development hardware. The installed-runtime adapter, automatic fusion with Python detectors, semantic-link verification and model promotion described below remain proposed work. No paid calls or default-classifier replacement are authorized by this direction.

The latest frozen v6 holdout failed five of nine targets, including contextual MNPI detection. Moving inference into a browser changes deployment and data handling; it does not establish better classification. A compact semantic model is a candidate to evaluate against the rules engine, not an assumed accuracy improvement.

## Recommended scope

Use one bounded classification workflow with a shared evidence contract and two possible runtime adapters: an installed local runtime and a browser worker using WebLLM. The user selected browser-first: highlight text, process in a worker, then optionally preview/copy redactions. Avoid an autonomous agent loop for this task: extraction, validation and aggregation can have explicit input, output, context and time limits. Begin with shadow evaluation, keeping model and deterministic results separate.

1. Admit canonical text and explicitly supplied jurisdiction/context. Preserve the original source.
2. Run high-specificity PII detectors and a semantic MNPI extractor on the same bounded input. Do not gate semantic extraction on existing MNPI keyword hits: that would preserve the current detector's misses.
3. Require structured issuer/event hypotheses and exact source quotations for issuer, event, materiality and claimed public status. Treat input instructions as document content. Require an explicit unknown state when evidence or context is missing.
4. Validate quotation matches, occurrences, bounds, component linkage and response shape outside the model. Resolve offsets against original text, with a defined Unicode code-point convention shared by Python and JavaScript. Reject fabricated spans. Unsupported, truncated or incomplete processing must produce visible uncertainty, not a clean negative.
5. Keep rule findings and model proposals attributable. Initial output reports disagreements rather than silently merging them or allowing a model to erase direct PII evidence. A future fusion policy must be evaluated separately.

MNPI public status remains text-claimed unless independent evidence is explicitly supplied. A local model cannot establish current public availability just by reasoning over a document.

## Browser feasibility

[WebLLM](https://webllm.mlc.ai/) runs model inference inside a WebGPU-capable browser, offers structured generation and worker support, and can cache downloaded assets. A browser runtime still needs model weights, compatible GPU features, memory, initial loading and storage. The current [model registry](https://github.com/mlc-ai/web-llm/blob/main/src/config.ts) lists compact quantized models, including `Qwen3-1.7B-q4f16_1-MLC`; that is a feasibility candidate, not a recommended MNPI model or a measured resource promise. Pin runtime, model artifact and quantization identities before evaluation rather than relying on mutable registry defaults.

Keep analysis text on the device. Asset downloads must be distinguishable from inference requests; an offline-ready claim needs a tested cold-load/warm-load and network-denied run after assets are installed. An unsupported GPU, missing model, resource limit or context overflow should fail explicitly without a cloud fallback. A browser-only implementation cannot call the Python engine without a bridge; porting required validators/detectors or defining an explicitly local service boundary is additional implementation work, not something WebLLM provides automatically. The first prototype uses an explicit exact-text CLI JSON import for comparison, without pretending that the Python engine runs in the browser.

## Compare before selecting a model

Use already-exposed development material for prompt/schema iteration; do not reinterpret it as fresh validation. Fix reference definitions, scenario-family splits, scoring and resource acceptance criteria before model selection. Evaluate the exact quantized model/runtime that would ship, measuring:

- MNPI detection, false positives and abstentions separately; all four PII/MNPI quadrants;
- grounding/linkage errors, mixed issuers, conflicting disclosure claims, paraphrases and instructions embedded in text;
- PII document and span metrics, including negative cases;
- download size, cold/warm load, peak memory, context coverage and latency on declared target hardware.

Freeze candidates before one untouched evaluation. Use existing predeclared quality targets as the starting acceptance requirements; do not lower them to promote a small model. Judge agreement alone is not independent accuracy, and self-reported confidence remains uncalibrated. Distillation is a later option if a compact model has a repeatable gap and suitable training data is available. Any new paid reference generation needs a separate cost proposal and authorization.
