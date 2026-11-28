import assert from "node:assert/strict";
import { test } from "node:test";
import { admitText, decodeProposal, inferenceRequest, previewRedaction, validateProposal, validateComparison, MAX_BYTES } from "../src/contract.js";
import { consumeSelection, queueSelection } from "../src/selection.js";

const text = "🙂 Alice Tan at alice.tan@example.com. Orchid Ltd signed a material acquisition, not publicly announced.";
const positive = () => ({
  pii_state: "present", pii: [{ label: "EMAIL", quote: "alice.tan@example.com" }],
  mnpi_state: "present", mnpi: [{ issuer: "Orchid Ltd", event: "acquisition", materiality: "material", claimed_nonpublic: "not publicly announced" }], complete: true,
});
for (const pii of [true, false]) for (const mnpi of [true, false]) {
  test(`accept grounded quadrant pii=${pii}, mnpi=${mnpi}`, () => {
    const raw = positive();
    if (!pii) { raw.pii = []; raw.pii_state = "not_detected"; }
    if (!mnpi) { raw.mnpi = []; raw.mnpi_state = "not_detected"; }
    const result = validateProposal(text, raw);
    assert.equal(result.sensitivity.pii.state, raw.pii_state);
    assert.equal(result.sensitivity.mnpi.state, raw.mnpi_state);
    assert.equal(result.sensitivity.absence_verified, false);
    assert.equal(result.classification_applied, false);
  });
}
test("Unicode offsets use Python-compatible code points", () => {
  const result = validateProposal(text, positive());
  const span = result.sensitivity.pii.evidence[0];
  assert.equal(span.start_char, 15);
  assert.equal(Array.from(text).slice(span.start_char, span.end_char).join(""), span.matched_text);
  assert.equal(previewRedaction(text, [span]), text.replace("alice.tan@example.com", "[REDACTED]"));
});
test("overlapping redactions merge without altering other text", () => {
  assert.equal(previewRedaction("abcdef", [
    { start_char: 1, end_char: 4, matched_text: "bcd" },
    { start_char: 3, end_char: 5, matched_text: "de" },
  ]), "a[REDACTED]f");
});
test("missing, repeated, fabricated and contradictory evidence is refused", () => {
  for (const mutate of [
    p => { p.pii[0].quote = "fabricated"; },
    p => { p.mnpi[0].issuer = "Another Ltd"; },
    p => { p.mnpi[0].event = ""; },
    p => { p.pii_state = "not_detected"; },
    p => { p.mnpi = []; },
    p => { p.complete = "yes"; },
    p => { p.confidence = .99; },
    p => { p.pii[0].label = "EXECUTE_SCRIPT"; },
  ]) { const raw = positive(); mutate(raw); assert.throws(() => validateProposal(text, raw)); }
  assert.throws(() => validateProposal(text + " alice.tan@example.com", positive()), /ambiguous/);
  assert.throws(() => validateProposal(text, positive(), "length"), /incomplete/);
});
test("partial assessment remains unknown even with grounded candidates", () => {
  const raw = positive(); raw.complete = false;
  const result = validateProposal(text, raw);
  assert.equal(result.sensitivity.pii.state, "unknown");
  assert.equal(result.sensitivity.mnpi.state, "unknown");
});
test("only the exact empty WebLLM thinking header is accepted before JSON", () => {
  const json = JSON.stringify(positive());
  for (const content of [json, "<think>\n\n</think>\n\n" + json]) {
    assert.equal(decodeProposal(text, { message: { content }, finish_reason: "stop" }).sensitivity.pii.state, "present");
  }
  for (const content of ["<think>invented reasoning</think>" + json, "```json\n" + json + "\n```", json + " trailing text"]) {
    assert.throws(() => decodeProposal(text, { message: { content }, finish_reason: "stop" }));
  }
  assert.throws(() => decodeProposal(text, { message: { content: json }, finish_reason: "length" }), /incomplete/);
  const bad = positive(); bad.pii[0].quote = "fabricated";
  assert.throws(() => decodeProposal(text, { message: { content: "<think>\n\n</think>\n\n" + JSON.stringify(bad) }, finish_reason: "stop" }), /missing/);
});
test("input bounds are bytes and no truncation is performed", () => {
  for (const input of ["", " ", "a\0b", 42, "🙂".repeat(MAX_BYTES / 4 + 1)]) assert.throws(() => admitText(input));
  assert.equal(admitText("x".repeat(MAX_BYTES)), "x".repeat(MAX_BYTES));
});
test("request reserves context before loading and uses the supported thinking option", () => {
  const request = inferenceRequest(text);
  assert.equal(request.extra_body.enable_thinking, false);
  assert.equal(JSON.parse(request.messages[1].content).document_text, text);
  assert.equal(request.response_format.type, "json_object");
  assert.throws(() => inferenceRequest("x".repeat(MAX_BYTES)), /context budget/);
});
test("redaction refuses changed source and invalid coordinates", () => {
  for (const span of [
    { start_char: -1, end_char: 2, matched_text: "ab" },
    { start_char: 0, end_char: 0, matched_text: "" },
    { start_char: 0, end_char: 2, matched_text: "wrong" },
    { start_char: 0, end_char: 8, matched_text: "abc" },
  ]) assert.throws(() => previewRedaction("abc", [span]));
});
test("comparison refuses a different document or retired review format", () => {
  const result = { schema_version: "junas.review.v2", document: { text }, sensitivity: { pii: { state: "present" }, mnpi: { state: "unknown" } } };
  assert.equal(validateComparison(text, result), result.sensitivity);
  assert.throws(() => validateComparison(text + " ", result));
  assert.throws(() => validateComparison(text, { ...result, schema_version: "old" }));
});

function fakeBrowser() {
  const entries = {}, urls = [];
  return { entries, urls, runtime: { getURL: p => `chrome-extension://test/${p}` }, tabs: { create: async p => urls.push(p.url) }, storage: { session: {
    get: async key => key === null ? { ...entries } : { [key]: entries[key] },
    set: async values => Object.assign(entries, values),
    remove: async keys => { for (const key of Array.isArray(keys) ? keys : [keys]) delete entries[key]; },
  } } };
}
test("capture transfers only the explicit selection and keeps it out of URLs", async () => {
  const api = fakeBrowser();
  await queueSelection(api, text, 100, "opaque-id");
  assert.equal(api.urls[0], "chrome-extension://test/process.html?selection=opaque-id");
  assert.equal(await consumeSelection(api, "opaque-id", 101), text);
  assert.deepEqual(api.entries, {});
  await assert.rejects(consumeSelection(api, "opaque-id", 102), /expired/);
});
test("expired captures are removed and queue storage is bounded", async () => {
  const api = fakeBrowser();
  for (let i = 0; i < 20; i++) await queueSelection(api, text, 100 + i, `id-${i}`);
  assert.equal(Object.keys(api.entries).length, 16);
  await assert.rejects(consumeSelection(api, "id-19", 400_000), /expired/);
  await queueSelection(api, text, 400_000, "fresh");
  assert.deepEqual(Object.keys(api.entries), ["selection:fresh"]);
});
