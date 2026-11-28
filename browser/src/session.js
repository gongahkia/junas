import { MODEL, MODEL_IDS, admitText, inferenceRequest } from "./contract.js";

export class ProcessingSession {
  constructor({ createWorker, getAdapter, changed = () => {}, now = Date.now }) {
    Object.assign(this, { createWorker, getAdapter, changed, now });
    this.version = 0;
    this.state = { text: "", result: null, busy: false, status: "Ready. Highlight text or paste a passage.", revision: 0, model: MODEL };
    this.updated = now();
  }
  publish(patch) {
    Object.assign(this.state, patch, { revision: this.state.revision + 1 });
    this.changed();
    return this.snapshot();
  }
  snapshot() { return structuredClone(this.state); }
  stop() {
    this.version++;
    clearTimeout(this.timer); clearTimeout(this.idle);
    this.worker?.terminate(); this.worker = undefined;
  }
  clear() {
    this.stop(); this.updated = this.now();
    return this.publish({ text: "", result: null, busy: false, status: "Text and results cleared. Cached model files remain on this device." });
  }
  cancel() {
    this.stop(); this.updated = this.now();
    return this.publish({ result: null, busy: false, status: "Cancelled. No classification is available." });
  }
  draft(text, model = this.state.model) {
    if (this.state.busy) throw Error("Cancel the current assessment before changing the passage.");
    if (typeof text !== "string" || new TextEncoder().encode(text).length > 16_384) throw Error("Paste a shorter passage.");
    if (!MODEL_IDS.includes(model)) throw Error("Unsupported local model.");
    if (model !== this.state.model) this.stop();
    this.updated = this.now();
    return this.publish({ text, model, result: null, status: "Ready to process this passage." });
  }
  expire() { if (!this.state.busy && this.now() - this.updated > 900_000) this.clear(); }
  async start(text, model = this.state.model) {
    if (this.state.busy) throw Error("An assessment is already running.");
    admitText(text); inferenceRequest(text);
    if (!MODEL_IDS.includes(model)) throw Error("Unsupported local model.");
    if (this.state.model !== model) this.stop();
    clearTimeout(this.idle);
    const version = ++this.version;
    this.updated = this.now();
    this.publish({ text, model, result: null, busy: true, status: "Loading local model… First use downloads model files." });
    const fail = message => {
      if (version !== this.version) return;
      this.stop(); this.updated = this.now();
      this.publish({ busy: false, result: null, status: message });
    };
    this.timer = setTimeout(() => fail("Processing timed out. No classification is available."), 600_000);
    try {
      const adapter = await this.getAdapter();
      if (version !== this.version) return this.snapshot();
      if (!adapter?.features.has("shader-f16")) throw Error("A usable WebGPU adapter with shader-f16 is required. No cloud fallback is configured.");
      this.worker ??= this.createWorker();
      this.worker.onerror = () => fail("The local worker failed. No classification is available.");
      this.worker.onmessage = ({ data }) => {
        if (version !== this.version) return;
        if (data.type === "progress") this.publish({ status: data.message });
        if (data.type === "error") fail(data.message);
        if (data.type === "result") {
          if (data.proposal?.document?.text !== text) { fail("Result source mismatch. No classification is available."); return; }
          clearTimeout(this.timer); this.updated = this.now();
          this.publish({ busy: false, result: data, status: data.proposal.complete
            ? "Assessment complete. Review the evidence; findings can still be wrong."
            : "Assessment incomplete. Both decisions remain unknown; findings may be missing." });
          this.idle = setTimeout(() => { this.worker?.terminate(); this.worker = undefined; }, 300_000);
        }
      };
      this.worker.postMessage({ text, model_id: model });
    } catch (error) { fail(error.message); }
    return this.snapshot();
  }
}
