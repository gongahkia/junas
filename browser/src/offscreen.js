import { ProcessingSession } from "./session.js";

const session = new ProcessingSession({
  createWorker: () => new Worker(new URL("worker.js", import.meta.url), { type: "module" }),
  getAdapter: () => navigator.gpu?.requestAdapter(),
});
setInterval(() => session.expire(), 30_000);
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id !== chrome.runtime.id || message.target !== "offscreen") return;
  (async () => {
    session.expire();
    switch (message.kind) {
      case "get": return session.snapshot();
      case "draft": return session.draft(message.text, message.model);
      case "start": return session.start(message.text, message.model);
      case "cancel": return session.cancel();
      case "clear": return session.clear();
      default: throw Error("Unknown session command.");
    }
  })().then(state => respond({ ok: true, state }), error => respond({ ok: false, error: error.message }));
  return true;
});
