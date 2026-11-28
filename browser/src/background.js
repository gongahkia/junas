import { admitText } from "./contract.js";
import { captureSelection, replaceSelection } from "./page-redaction.js";
let creating;
async function ensureSession() {
  const contexts = await chrome.runtime.getContexts({ contextTypes: ["OFFSCREEN_DOCUMENT"], documentUrls: [chrome.runtime.getURL("offscreen.html")] });
  if (contexts.length) return;
  creating ??= chrome.offscreen.createDocument({ url: "offscreen.html", reasons: ["WORKERS"], justification: "Run the local text model independently of the review popup." }).finally(() => { creating = undefined; });
  await creating;
}
async function command(message) {
  await ensureSession();
  return chrome.runtime.sendMessage({ ...message, target: "offscreen" });
}
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id !== chrome.runtime.id) return;
  if (message.target === "apply-redaction") {
    chrome.scripting.executeScript({ target: message.destination, func: replaceSelection, args: [message.jobId, message.text] })
      .then(rows => respond({ ok: rows[0]?.result === true }), () => respond({ ok: false, error: "Source changed or page unavailable; no replacement was confirmed." }));
    return true;
  }
  if (message.target !== "session") return;
  command(message).then(respond, () => respond({ ok: false, error: "Local processing could not be opened. Reopen Junas and try again." }));
  return true;
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "process", title: "Redact with Junas", contexts: ["selection"] });
});
async function showStatus(state) {
  await chrome.action.setBadgeText({ text: state.busy ? "…" : state.failed ? "!" : state.result ? "✓" : "" });
  await chrome.action.setTitle({ title: state.busy ? "Junas — processing" : state.status });
}
chrome.runtime.onMessage.addListener((message, sender) => {
  if (sender.id === chrome.runtime.id && message.target === "badge") showStatus(message.state).catch(() => {});
});
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "process") return;
  try {
    admitText(info.selectionText);
    const jobId = crypto.randomUUID();
    if (!Number.isInteger(tab?.id)) throw Error("No source tab.");
    const destination = { tabId: tab.id, frameIds: [info.frameId ?? 0] };
    const captured = await chrome.scripting.executeScript({ target: destination, func: captureSelection, args: [info.selectionText, jobId] });
    if (!captured[0]?.result) throw Error("Selection unavailable.");
    const result = await command({ kind: "capture", text: info.selectionText, jobId, destination });
    if (!result.ok) throw Error(result.error);
    await showStatus(result.state);
  } catch {
    await command({ kind: "capture-error" }).catch(() => {});
    await showStatus({ failed: true, status: "Junas could not start. Open Junas to review the status." });
  }
});
