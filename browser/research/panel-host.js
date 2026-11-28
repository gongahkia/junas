// browser-panel preview transport; production extension uses Chrome offscreen messaging.
import { ProcessingSession } from "../src/session.js";
const frame = document.getElementById("popup");
const session = new ProcessingSession({
  createWorker: () => new Worker("worker.js", { type: "module" }),
  getAdapter: () => navigator.gpu?.requestAdapter(),
});
setInterval(() => session.expire(), 30_000);
addEventListener("message", async event => {
  if (event.origin !== location.origin || event.source !== frame.contentWindow || event.data?.target !== "panel-session") return;
  const message = event.data;
  try {
    let state;
    switch (message.kind) {
      case "get": state = session.snapshot(); break;
      case "draft": state = session.draft(message.text, message.model); break;
      case "start": state = await session.start(message.text, message.model); break;
      case "cancel": state = session.cancel(); break;
      case "clear": state = session.clear(); break;
      case "selection": event.source.postMessage({ id: message.id, panelReply: true, selection: getSelection()?.toString() || "" }, location.origin); return;
      default: throw Error("Unknown preview command.");
    }
    event.source.postMessage({ id: message.id, panelReply: true, ok: true, state }, location.origin);
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
  try { await session.start(selected); }
  catch (error) { document.getElementById("preview-status").textContent = error.message; }
};
