// synthetic-only diagnostic worker; excluded from the extension build.
import { CreateMLCEngine } from "@mlc-ai/web-llm";
import { MODEL, inferenceRequest, RESPONSE_SCHEMA } from "../src/contract.js";
import { MODEL_CONFIG } from "../src/model.js";
import baseline from "./baseline-requests.json" with { type: "json" };

const personal = "Personal email: alice.tan@example.com.";
const negative = "The company cafeteria serves lunch at noon.";
const trials = [
  ["baseline-email", baseline.email],
  ["baseline-negative", baseline.negative],
  ["current-email", inferenceRequest(personal)],
  ["current-negative", inferenceRequest(negative)],
  ["explicit-completion", { ...inferenceRequest(personal), messages: [
    { role: "system", content: `Assess the entire passage and return JSON. complete means you finished reading the supplied passage, not that all real-world context is known. Use complete true when the supplied passage was fully assessed. pii contains exact personal quotations. mnpi requires linked issuer, event, materiality and nonpublic quotations; otherwise use an empty array. Here is the response schema: ${JSON.stringify(RESPONSE_SCHEMA)}` },
    { role: "user", content: JSON.stringify({ document_text: personal }) },
  ] }],
  ["boolean-true", { messages: [{ role: "user", content: 'Return {"ok":true} exactly.' }], response_format: { type: "json_object", schema: JSON.stringify({ type: "object", properties: { ok: { type: "boolean" } }, required: ["ok"], additionalProperties: false }) }, temperature: 0, max_tokens: 64, extra_body: { enable_thinking: false } }],
  ["plain-json", { messages: [{ role: "user", content: 'Return only JSON: {"complete":true,"email":"alice.tan@example.com"}. Do not add explanations.' }], temperature: 0, max_tokens: 128, extra_body: { enable_thinking: false } }],
  ["current-both", inferenceRequest("Personal email: dora@example.org. Listed Aster Ltd signed a material acquisition. This acquisition is confidential and has not been publicly announced.")],
];
let started = false;
self.onmessage = async () => {
  if (started) return;
  started = true;
  const deadline = setTimeout(() => { self.postMessage({ error: "Diagnostic deadline exceeded." }); self.close(); }, 600_000);
  try {
    const start = performance.now();
    const engine = await CreateMLCEngine(MODEL, { appConfig: MODEL_CONFIG, initProgressCallback: p => self.postMessage({ progress: p.text }) }, { context_window_size: 4096 });
    self.postMessage({ loaded_ms: performance.now() - start });
    globalThis.fetch = async () => { throw Error("Network access disabled during synthetic inference."); };
    for (const [id, request] of trials) {
      const started = performance.now();
      const reply = await engine.chat.completions.create(request);
      self.postMessage({ id, elapsed_ms: performance.now() - started, choice: reply.choices[0], usage: reply.usage });
    }
    await engine.unload();
    self.postMessage({ done: true });
  } catch (error) { self.postMessage({ error: error.message }); }
  finally { clearTimeout(deadline); }
};
