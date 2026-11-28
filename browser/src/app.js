import { MODEL, MAX_BYTES, previewRedaction, validateComparison } from "./contract.js";
import { consumeSelection } from "./selection.js";

const $ = id => document.getElementById(id);
let revision = -1, resultRevision, findings = [], current, editing = Promise.resolve(), polling = false, draftVersion = 0;
const status = message => { $("status").textContent = message; };
function resetResults() {
  findings = []; current = undefined;
  $("results").hidden = $("redaction").hidden = true;
  $("redacted").value = ""; $("evidence").replaceChildren();
  $("json").textContent = $("comparison-result").textContent = "";
  $("comparison").value = "";
}
async function request(kind, extra = {}) {
  const response = await chrome.runtime.sendMessage({ target: "session", kind, ...extra });
  if (!response?.ok) throw Error(response?.error || "Local session unavailable. Reopen Junas and try again.");
  return response.state;
}
function render(state) {
  if (state.revision < revision) return;
  revision = state.revision;
  $("source").value = state.text;
  $("size").textContent = `${new TextEncoder().encode($("source").value).length} / ${MAX_BYTES} bytes`;
  $("source").disabled = $("process").disabled = $("model").disabled = $("capture").disabled = state.busy;
  $("cancel").hidden = !state.busy;
  $("model").value = state.model;
  status(state.status);
  if (!state.result) { resetResults(); resultRevision = undefined; return; }
  const signature = JSON.stringify(state.result);
  if (resultRevision === signature) return;
  resultRevision = signature; resetResults(); current = state.result;
  const proposal = current.proposal;
  $("results").hidden = false;
  $("pii-state").textContent = proposal.sensitivity.pii.state.replaceAll("_", " ");
  $("mnpi-state").textContent = proposal.sensitivity.mnpi.state.replaceAll("_", " ");
  $("timing").textContent = `Load ${(current.timing.load_ms / 1000).toFixed(1)}s · process ${(current.timing.inference_ms / 1000).toFixed(1)}s`;
  findings = [...proposal.sensitivity.pii.evidence, ...proposal.sensitivity.mnpi.evidence];
  for (const finding of findings) {
    const label = document.createElement("label"), checkbox = document.createElement("input"), text = document.createElement("span");
    checkbox.type = "checkbox";
    checkbox.addEventListener("change", () => { $("redaction").hidden = true; $("redacted").value = ""; });
    const type = document.createElement("small"); type.textContent = finding.label.replaceAll("_", " ");
    const quote = document.createElement("span"); quote.textContent = finding.matched_text;
    text.append(type, quote); label.append(checkbox, text); $("evidence").append(label);
  }
  if (!findings.length) $("evidence").textContent = "No source-grounded findings to display.";
  $("preview").disabled = !findings.length;
  $("json").textContent = JSON.stringify(current, null, 2);
}
function draft() {
  resetResults(); resultRevision = undefined;
  $("size").textContent = `${new TextEncoder().encode($("source").value).length} / ${MAX_BYTES} bytes`;
  const text = $("source").value, model = $("model").value;
  const version = ++draftVersion;
  editing = editing.catch(() => {}).then(() => request("draft", { text, model }))
    .then(state => { if (version === draftVersion) render(state); }).catch(error => status(error.message));
}
$("source").addEventListener("input", draft);
$("model").onchange = draft;
$("process").onclick = async () => {
  try { await editing; render(await request("start", { text: $("source").value, model: $("model").value })); }
  catch (error) { status(error.message); }
};
for (const kind of ["cancel", "clear"]) $(kind).onclick = async () => {
  try { await editing; render(await request(kind)); }
  catch (error) { status(error.message); }
};
$("preview").onclick = () => {
  try {
    const selected = findings.filter((_, i) => $("evidence").querySelectorAll("input")[i].checked);
    if (!selected.length) throw Error("Select a finding to redact.");
    $("redacted").value = previewRedaction($("source").value, selected);
    $("redaction").hidden = false;
  } catch (error) { status(error.message); }
};
$("copy").onclick = async () => {
  try { await navigator.clipboard.writeText($("redacted").value); status("Redacted copy saved to clipboard. Original text unchanged."); }
  catch { status("Clipboard unavailable. Select and copy the preview manually."); }
};
$("comparison").onchange = async event => {
  try {
    const file = event.target.files[0];
    if (!file || file.size > 1024 * 1024) throw Error("Choose review JSON of at most 1 MiB.");
    const reference = validateComparison($("source").value, JSON.parse(await file.text()));
    if (!current) throw Error("Process this passage first.");
    $("comparison-result").textContent = ["pii", "mnpi"].map(c => `${c.toUpperCase()}: deterministic ${reference[c].state}, model ${current.proposal.sensitivity[c].state}`).join(" · ");
  } catch (error) { $("comparison-result").textContent = error.message; }
};
async function capture() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const results = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: () => {
      const element = document.activeElement;
      if (element instanceof HTMLInputElement && element.type === "password") return "";
      if (element instanceof HTMLTextAreaElement || (element instanceof HTMLInputElement && element.type !== "password")) {
        if (Number.isInteger(element.selectionStart) && element.selectionEnd > element.selectionStart) return element.value.slice(element.selectionStart, element.selectionEnd);
      }
      return window.getSelection()?.toString() || "";
    } });
    const text = results[0]?.result;
    if (!text) { status("Highlight text on the page, or paste a passage here."); return; }
    render(await request("draft", { text, model: $("model").value }));
  } catch { status("Selection is unavailable on this page. Paste the passage instead."); }
}
$("capture").onclick = capture;
const params = new URLSearchParams(location.search);
try {
  const state = await request("get"); render(state);
  if (params.has("selection")) render(await request("start", { text: await consumeSelection(chrome, params.get("selection")) }));
  else if (params.has("capture")) status("Selection could not be captured. Paste a shorter passage.");
  else if (document.body.classList.contains("popup") && !state.busy && !state.text) await capture();
} catch (error) { status(error.message); }
setInterval(async () => {
  if (polling || document.hidden || document.activeElement === $("source")) return;
  polling = true;
  const version = draftVersion;
  try { await editing; const state = await request("get"); if (version === draftVersion && state.revision !== revision) render(state); }
  catch (error) { status(error.message); }
  finally { polling = false; }
}, 500);
export { MODEL };
