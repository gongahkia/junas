import { MODEL, previewRedaction, validateComparison } from "./contract.js";

const $ = id => document.getElementById(id);
let revision = -1, resultRevision, findings = [], current, polling = false;
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
  $("source").textContent = state.text;
  $("cancel").hidden = !state.busy;
  $("model").disabled = state.busy;
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
$("model").onchange = async () => {
  try { const state = await request("get"); render(await request("draft", { text: state.text, model: $("model").value })); }
  catch (error) { status(error.message); }
};
$("cancel").onclick = async () => {
  try { render(await request("cancel")); } catch (error) { status(error.message); }
};
$("preview").onclick = () => {
  try {
    const selected = findings.filter((_, i) => $("evidence").querySelectorAll("input")[i].checked);
    if (!selected.length) throw Error("Select a finding to redact.");
    $("redacted").value = previewRedaction(current.proposal.document.text, selected);
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
    const reference = validateComparison(current?.proposal.document.text, JSON.parse(await file.text()));
    if (!current) throw Error("Process this passage first.");
    $("comparison-result").textContent = ["pii", "mnpi"].map(c => `${c.toUpperCase()}: deterministic ${reference[c].state}, model ${current.proposal.sensitivity[c].state}`).join(" · ");
  } catch (error) { $("comparison-result").textContent = error.message; }
};
try { render(await request("get")); } catch (error) { status(error.message); }
setInterval(async () => {
  if (polling || document.hidden) return;
  polling = true;
  try { const state = await request("get"); if (state.revision !== revision) render(state); }
  catch (error) { status(error.message); }
  finally { polling = false; }
}, 500);
export { MODEL };
