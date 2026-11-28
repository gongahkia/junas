// synthetic-only candidate worker; excluded from the extension build.
import { CreateMLCEngine } from "@mlc-ai/web-llm";
import { admitText, decodeProposal } from "../src/contract.js";
import { modelConfig, WEIGHTS_REVISIONS, LIBRARY_REVISION } from "../src/model.js";
import { anchoredRequest, ANCHORED_REQUEST_VERSION } from "./anchored-request.js";

let engine, loadedModel, busy = false;
const assetFetch = globalThis.fetch.bind(globalThis);
self.onmessage = async ({ data }) => {
  if (busy) return;
  busy = true;
  let phase = "input", choice;
  try {
    const text = admitText(data.text), model = data.model_id;
    const request = anchoredRequest(text, model), started = performance.now();
    phase = "model_loading";
    if (engine && loadedModel !== model) { await engine.unload(); engine = undefined; }
    if (!engine) {
      globalThis.fetch = assetFetch;
      engine = await CreateMLCEngine(model, { appConfig: modelConfig(model), initProgressCallback: p => self.postMessage({ type: "progress", message: p.text }) }, { context_window_size: 4096 });
      loadedModel = model;
    }
    const loaded = performance.now();
    globalThis.fetch = async () => { throw Error("Network disabled during synthetic inference."); };
    phase = "inference";
    const reply = await engine.chat.completions.create(request);
    choice = reply.choices?.[0];
    phase = "validation";
    const proposal = decodeProposal(text, choice, true);
    proposal.model = model;
    self.postMessage({ type: "result", proposal, model_identity: { model, request_version: ANCHORED_REQUEST_VERSION,
      build_sha256: __JUNAS_BUILD_ID__, weights_revision: WEIGHTS_REVISIONS[model], library_revision: LIBRARY_REVISION, runtime: "@mlc-ai/web-llm@0.2.89" },
      timing: { load_ms: loaded - started, inference_ms: performance.now() - loaded, total_ms: performance.now() - started }, usage: reply.usage ?? null });
  } catch (error) {
    self.postMessage({ type: "error", phase, code: error.name, message: `Candidate ${phase} failed: ${phase === "validation" ? error.message : error.name}` });
  } finally { busy = false; }
};
