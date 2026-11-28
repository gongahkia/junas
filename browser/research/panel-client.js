const pending = new Map();
function message(command) {
  return new Promise((resolve, reject) => {
    const id = crypto.randomUUID();
    const timer = setTimeout(() => { pending.delete(id); reject(Error("Preview session unavailable.")); }, 15_000);
    pending.set(id, value => { clearTimeout(timer); resolve(value); });
    parent.postMessage({ ...command, id, target: "panel-session" }, location.origin);
  });
}
addEventListener("message", event => {
  if (event.origin !== location.origin || event.source !== parent || !event.data?.panelReply) return;
  pending.get(event.data.id)?.(event.data); pending.delete(event.data.id);
});
globalThis.chrome ??= {};
chrome.runtime = { sendMessage: command => message(command) };
await import("../src/app.js");
