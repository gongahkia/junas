import { admitText } from "./contract.js";
import { ProcessingSession } from "./session.js";
import { settings, saveSettings, history, saveHistory, deleteHistory } from "./local-data.js";
import { automaticRedaction } from "./auto-redaction.js";

let active;
const session = new ProcessingSession({
  createWorker: () => new Worker(new URL("worker.js", import.meta.url), { type: "module" }),
  getAdapter: () => navigator.gpu?.requestAdapter(),
  changed: () => {
    const state = session.snapshot();
    chrome.runtime.sendMessage({ target: "badge", state: { busy: state.busy, result: !!state.result, failed: state.failed, status: state.status } }).catch(() => {});
    if (active && !state.busy && (state.failed || state.status.startsWith("Cancelled"))) {
      const record = active; active = undefined;
      saveHistory({ ...record, status: state.status, outcome: "failed_or_cancelled" }).then(() => session.publish({})).catch(() => session.publish({ status: "Local history could not be saved." }));
    }
  },
  finished: async (data, version) => {
    const job = active;
    if (!job) return;
    const result = automaticRedaction(data.proposal, job.settings);
    let outcome = "unchanged", status = "No changes: no complete, enabled finding met the confidence threshold.";
    await saveHistory({ ...job, redacted: result.text, outcome: "ready", status: "Applying redaction…" });
    if (version !== session.version) return;
    if (result.findings) {
      const response = await chrome.runtime.sendMessage({ target: "apply-redaction", destination: job.destination, jobId: job.id, text: result.text });
      outcome = response?.ok ? "redacted" : "replacement_failed";
      status = response?.ok ? "Highlighted text redacted on the page." : "Replacement was not confirmed. The source may have changed; check history.";
      if (!response?.ok) session.publish({ failed: true });
    }
    if (version !== session.version) return;
    if (!data.proposal.complete || ["pii", "mnpi"].some(c => job.settings[c] && data.proposal.sensitivity[c].state === "unknown")) session.publish({ failed: true });
    await saveHistory({ ...job, redacted: result.text, outcome, status, findings: result.findings, confidence_kind: "uncalibrated_model_estimate" });
    active = undefined;
    return status;
  },
});
async function view() { return { ...session.snapshot(), settings: await settings(), history: await history() }; }
setInterval(() => session.expire(), 30_000);
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id !== chrome.runtime.id || message.target !== "offscreen") return;
  (async () => {
    session.expire();
    switch (message.kind) {
      case "get": break;
      case "settings": await saveSettings(message.settings); session.publish({}); break;
      case "delete-history":
        if (active && (!message.id || active.id === message.id)) session.cancel();
        await deleteHistory(message.id); session.publish({}); break;
      case "capture-error":
        if (!session.state.busy) session.publish({ result: null, text: "", failed: true, status: "Page selection unavailable. Highlight the text again on a supported page." });
        break;
      case "draft": session.draft(message.text, message.model); break;
      case "capture":
        if (session.state.busy) throw Error("An assessment is already running.");
        try {
          admitText(message.text);
          if (message.jobId && message.destination) {
            const preferences = await settings();
            if (!preferences.pii && !preferences.mnpi) throw Error("Enable PII or MNPI redaction in settings first.");
            active = { id: message.jobId, created: Date.now(), source: message.text, settings: preferences, destination: message.destination, outcome: "processing", status: "Processing" };
            await saveHistory(active);
            await session.start(message.text, preferences.model, { confidence: true });
          } else await session.start(message.text);
        } catch (error) {
          session.publish({ text: "", result: null, failed: true, busy: false, status: error.message });
        }
        break;
      case "start": await session.start(message.text, message.model); break;
      case "cancel": session.cancel(); break;
      case "clear": session.clear(); break;
      default: throw Error("Unknown session command.");
    }
    return view();
  })().then(state => respond({ ok: true, state }), error => respond({ ok: false, error: error.message }));
  return true;
});
