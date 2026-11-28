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
chrome.contextMenus.onClicked.addListener(async info => {
  if (info.menuItemId !== "process") return;
  try {
    const result = await command({ kind: "start", text: info.selectionText });
    if (!result.ok) throw Error(result.error);
    try { await chrome.action.openPopup(); }
    catch { await chrome.tabs.create({ url: chrome.runtime.getURL("process.html") }); }
  }
  catch {
    await chrome.tabs.create({ url: chrome.runtime.getURL("process.html?capture=failed") });
  }
});
