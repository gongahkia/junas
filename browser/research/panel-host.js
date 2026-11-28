// browser-panel preview transport; production extension uses Chrome offscreen messaging.
import { captureSelection, replaceSelection } from "../src/page-redaction.js";
const frame = document.getElementById("popup");
let listener;
globalThis.chrome ??= {};
chrome.runtime = {
  id: "junas-panel-preview",
  onMessage: { addListener: callback => { listener = callback; } },
  sendMessage: async message => {
    if (message.target === "badge") return;
    if (message.target === "apply-redaction") {
      try { return { ok: replaceSelection(message.jobId, message.text) }; }
      catch { return { ok: false }; }
    }
  },
};
await import("../src/offscreen.js");
function command(message) {
  return new Promise(resolve => listener({ ...message, target: "offscreen" }, { id: chrome.runtime.id }, resolve));
}
addEventListener("message", async event => {
  if (event.origin !== location.origin || event.source !== frame.contentWindow || event.data?.target !== "panel-session") return;
  const message = event.data;
  try {
    const response = await command(message);
    event.source.postMessage({ id: message.id, panelReply: true, ...response }, location.origin);
  } catch (error) { event.source.postMessage({ id: message.id, panelReply: true, ok: false, error: error.message }, location.origin); }
});
document.getElementById("toggle").onclick = () => {
  const closed = frame.hidden = !frame.hidden;
  frame.src = closed ? "about:blank" : "panel-popup.html";
  document.getElementById("toggle").textContent = closed ? "Open Junas" : "Close popup";
};

const menu = document.getElementById("context-process");
let selected = "";
document.getElementById("sample").addEventListener("contextmenu", event => {
  selected = getSelection()?.toString() || "";
  if (!selected.trim()) return;
  event.preventDefault(); menu.hidden = false;
});
menu.onclick = async () => {
  menu.hidden = true;
  try {
    const jobId = crypto.randomUUID(); captureSelection(selected, jobId);
    const response = await command({ kind: "capture", text: selected, jobId, destination: { tabId: 0, frameIds: [0] } });
    if (!response.ok) throw Error(response.error);
  }
  catch (error) { document.getElementById("preview-status").textContent = error.message; }
};
