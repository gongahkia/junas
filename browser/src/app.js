import { MODEL, MAX_BYTES, admitText, previewRedaction, validateComparison } from "./contract.js";
import { consumeSelection } from "./selection.js";

const $ = id => document.getElementById(id);
let worker, timer, proposal, requestVersion = 0;
const status = text => { $("status").textContent = text; };
function resetResults() {
  proposal = undefined;
  $("results").hidden = $("redaction").hidden = true;
  $("redacted").value = "";
  $("evidence").replaceChildren();
  $("json").textContent = $("comparison-result").textContent = "";
  $("comparison").value = "";
  $("preview").onclick = null;
}
function busy(active) {
  $("source").disabled = active;
  $("process").disabled = active;
  $("cancel").hidden = !active;
}
function stop(message) {
  requestVersion++;
  worker?.terminate(); worker = undefined;
  clearTimeout(timer); busy(false);
  if (message) status(message);
}
function showResult(data) {
  proposal = data.proposal;
  $("results").hidden = false;
  $("states").textContent = `PII proposal: ${proposal.sensitivity.pii.state} · MNPI proposal: ${proposal.sensitivity.mnpi.state}. Public status is unverified.`;
  $("timing").textContent = `Load ${(data.timing.load_ms / 1000).toFixed(2)} s · inference ${(data.timing.inference_ms / 1000).toFixed(2)} s · ${MODEL}`;
  const findings = [...proposal.sensitivity.pii.evidence, ...proposal.sensitivity.mnpi.evidence];
  for (const finding of findings) {
    const label = document.createElement("label"), input = document.createElement("input"), text = document.createElement("span");
    input.type = "checkbox";
    input.addEventListener("change", () => { $("redaction").hidden = true; $("redacted").value = ""; });
    text.textContent = `${finding.label}: ${finding.matched_text}`;
    label.append(input, text); $("evidence").append(label);
  }
  $("preview").disabled = !findings.length;
  $("preview").onclick = () => {
    try {
      const selected = findings.filter((_, i) => $("evidence").querySelectorAll("input")[i].checked);
      if (!selected.length) throw Error("Select at least one finding to redact.");
      $("redacted").value = previewRedaction($("source").value, selected);
      $("redaction").hidden = false;
    } catch (error) { status(error.message); }
  };
  $("json").textContent = JSON.stringify(data, null, 2);
  status(proposal.complete ? "Processing completed. Review the proposed evidence before using it." : "Assessment is incomplete. Both category decisions remain unknown; findings may be missing.");
}
async function processText() {
  const version = ++requestVersion;
  resetResults();
  try {
    const text = admitText($("source").value);
    busy(true);
    if (!navigator.gpu) throw Error("WebGPU is unavailable. Use a supported browser/device; no cloud fallback is configured.");
    const adapter = await navigator.gpu.requestAdapter();
    if (version !== requestVersion) return;
    if (!adapter?.features.has("shader-f16")) throw Error("A usable WebGPU adapter with shader-f16 support is required. No model was downloaded.");
    busy(true); status("Loading the local model. First use downloads model files; this may take several minutes.");
    worker ??= new Worker(new URL("worker.js", import.meta.url), { type: "module" });
    worker.onerror = () => { resetResults(); stop("The local worker failed. No classification is available."); };
    worker.onmessage = ({ data }) => {
      if (version !== requestVersion) return;
      if (data.type === "progress") status(data.message);
      else if (data.type === "error") { resetResults(); stop(data.message); }
      else if (data.type === "result") { clearTimeout(timer); busy(false); showResult(data); }
    };
    timer = setTimeout(() => { resetResults(); stop("Processing timed out. No classification is available; try a shorter passage or a more capable device."); }, 600_000);
    worker.postMessage({ text });
  } catch (error) { if (version === requestVersion) stop(error.message); }
}
$("process").onclick = processText;
$("cancel").onclick = () => { resetResults(); stop("Cancelled. No classification is available."); };
$("source").addEventListener("input", () => {
  resetResults();
  $("size").textContent = `${new TextEncoder().encode($("source").value).length} / ${MAX_BYTES} UTF-8 bytes`;
});
$("clear").onclick = () => { stop(); $("source").value = ""; resetResults(); $("size").textContent = ""; status("Text and results cleared. Cached model assets remain on this device."); };
$("copy").onclick = async () => {
  try { await navigator.clipboard.writeText($("redacted").value); status("Redacted text copied. The source page is unchanged."); }
  catch { status("Clipboard access failed. You can select and copy the redacted preview manually."); }
};
$("comparison").onchange = async event => {
  try {
    const file = event.target.files[0];
    if (!file || file.size > 1024 * 1024) throw Error("Select a review JSON file of at most 1 MiB.");
    const reference = validateComparison($("source").value, JSON.parse(await file.text()));
    if (!proposal) throw Error("Process this passage first.");
    $("comparison-result").textContent = ["pii", "mnpi"].map(c => `${c.toUpperCase()}: deterministic ${reference[c].state}, model ${proposal.sensitivity[c].state}`).join(" · ");
  } catch (error) { $("comparison-result").textContent = error.message; }
};
const params = new URLSearchParams(location.search);
if (params.has("capture")) status("Selection could not be captured. Select a shorter passage or paste it here.");
if (params.has("selection")) {
  try {
    $("source").value = await consumeSelection(chrome, params.get("selection"));
    $("source").dispatchEvent(new Event("input"));
    await processText();
  } catch (error) { status(error.message); }
}
