import { CreateMLCEngine } from "@mlc-ai/web-llm";
import { MODEL, admitText, inferenceRequest, validateProposal } from "./contract.js";
import { MODEL_CONFIG, WEIGHTS_REVISION, LIBRARY_REVISION } from "./model.js";

let engine;
let busy = false;
self.onmessage = async ({ data }) => {
  if (busy) { self.postMessage({ type: "error", message: "A local request is already running." }); return; }
  busy = true;
  try {
    const text = admitText(data.text);
    const request = inferenceRequest(text);
    const started = performance.now();
    if (!engine) engine = await CreateMLCEngine(MODEL, {
      appConfig: MODEL_CONFIG,
      initProgressCallback: progress => self.postMessage({ type: "progress", message: progress.text }),
    }, { context_window_size: 4096 });
    const loaded = performance.now();
    // after initialization there is no network fallback, including on errors.
    globalThis.fetch = async () => { throw Error("Network access is disabled during classification."); };
    const reply = await engine.chat.completions.create(request);
    const choice = reply.choices?.[0];
    const proposal = validateProposal(text, JSON.parse(choice?.message?.content ?? ""), choice?.finish_reason ?? "missing");
    self.postMessage({ type: "result", proposal, model_identity: { build_sha256: __JUNAS_BUILD_ID__, weights_revision: WEIGHTS_REVISION, library_revision: LIBRARY_REVISION, runtime: "@mlc-ai/web-llm@0.2.89" }, timing: {
      load_ms: loaded - started, inference_ms: performance.now() - loaded,
      total_ms: performance.now() - started,
    }, usage: reply.usage ?? null });
  } catch {
    self.postMessage({ type: "error", message: "Local processing failed or produced incomplete/invalid evidence. No clean result is available. Check WebGPU support, available memory, model assets and passage length." });
  } finally { busy = false; }
};
