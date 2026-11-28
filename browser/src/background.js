import { queueSelection } from "./selection.js";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "process", title: "Process selected text with Junas", contexts: ["selection"] });
});
chrome.contextMenus.onClicked.addListener(async info => {
  if (info.menuItemId !== "process") return;
  try { await queueSelection(chrome, info.selectionText); }
  catch {
    await chrome.tabs.create({ url: chrome.runtime.getURL("process.html?capture=failed") });
  }
});
chrome.action.onClicked.addListener(() => chrome.tabs.create({ url: chrome.runtime.getURL("process.html") }));
