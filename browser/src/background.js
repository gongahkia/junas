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
  if (sender.id !== chrome.runtime.id || message.target !== "session") return;
  command(message).then(respond, () => respond({ ok: false, error: "Local processing could not be opened. Reopen Junas and try again." }));
  return true;
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "process", title: "Process selected text with Junas", contexts: ["selection"] });
});
async function showStatus(state) {
  await chrome.action.setBadgeText({ text: state.busy ? "…" : state.result ? "✓" : state.failed ? "!" : "" });
  await chrome.action.setTitle({ title: state.busy ? "Junas — processing" : state.result ? "Junas — assessment ready" : state.status });
}
chrome.runtime.onMessage.addListener((message, sender) => {
  if (sender.id === chrome.runtime.id && message.target === "badge") showStatus(message.state).catch(() => {});
});
chrome.contextMenus.onClicked.addListener(async info => {
  if (info.menuItemId !== "process") return;
  try {
    const result = await command({ kind: "capture", text: info.selectionText });
    if (!result.ok) throw Error(result.error);
    await showStatus(result.state);
  } catch {
    await showStatus({ failed: true, status: "Junas could not start. Open Junas to review the status." });
  }
});
