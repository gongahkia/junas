import { test } from "node:test";
import assert from "node:assert/strict";
import { decodeProposal, inferenceRequest } from "../src/contract.js";
import { automaticRedaction } from "../src/auto-redaction.js";
import { validateSettings, DEFAULT_SETTINGS } from "../src/local-data.js";
test("uncalibrated confidence does not bypass grounding, completeness or category settings", () => {
  const text = "Private email: a@example.org.";
  const raw = { pii_state: "present", pii: [{ label: "EMAIL", quote: "a@example.org", confidence: .9 }], mnpi_state: "not_detected", mnpi: [], complete: true };
  const decode = () => decodeProposal(text, { finish_reason: "stop", message: { content: JSON.stringify(raw) } }, true);
  assert.equal(automaticRedaction(decode(), DEFAULT_SETTINGS).text, "Private email: [REDACTED].");
  assert.equal(automaticRedaction(decode(), { ...DEFAULT_SETTINGS, threshold: .95 }).findings, 0);
  assert.equal(automaticRedaction(decode(), { ...DEFAULT_SETTINGS, pii: false }).findings, 0);
  raw.complete = false; assert.equal(automaticRedaction(decode(), DEFAULT_SETTINGS).findings, 0);
  raw.complete = true; raw.pii[0].confidence = 1.1; assert.throws(decode, /confidence/);
  raw.pii[0].confidence = .99; raw.pii[0].quote = "invented"; assert.throws(decode, /source/);
  assert.ok(JSON.parse(inferenceRequest(text, DEFAULT_SETTINGS.model, true).response_format.schema).properties.pii.items.required.includes("confidence"));
  assert.throws(() => validateSettings({ ...DEFAULT_SETTINGS, threshold: NaN }), /Invalid/);
});
test("MNPI scope defaults to its evidence interval and optionally expands within the selected passage", () => {
  const text = "Public context. Aster has secret news. Other context.";
  const start = text.indexOf("secret"), end = start + "secret news".length;
  const proposal = { document: { text }, complete: true, sensitivity: {
    pii: { state: "not_detected", evidence: [] },
    mnpi: { state: "present", evidence: [{ label: "CONTEXTUAL_MNPI", start_char: start, end_char: end, matched_text: "secret news", confidence: .95 }] },
  } };
  assert.equal(automaticRedaction(proposal, DEFAULT_SETTINGS).text, "Public context. Aster has [REDACTED]. Other context.");
  const expanded = automaticRedaction(proposal, { ...DEFAULT_SETTINGS, mnpiExtent: "sentences" }).text;
  assert.ok(expanded.startsWith("Public context. "));
  assert.ok(expanded.includes("[REDACTED]"));
  assert.ok(expanded.endsWith("Other context."));
  assert.throws(() => validateSettings({ ...DEFAULT_SETTINGS, mnpiExtent: "document" }), /extent/);
});
test("all quadrants obey category switches, threshold boundaries and MNPI scope", () => {
  for (const pii of [false, true]) for (const mnpi of [false, true]) {
    const financial = "Listed Aster PLC agreed a material merger; this event is confidential.";
    const text = `🙂 Public context. ${pii ? "Personal email: a@example.org. " : "Lunch starts at noon. "}${mnpi ? financial : "The public report is available."} Other context.`;
    const raw = { pii_state: pii ? "present" : "not_detected", pii: pii ? [{ label: "EMAIL", quote: "a@example.org", confidence: .85 }] : [],
      mnpi_state: mnpi ? "present" : "not_detected", mnpi: mnpi ? [{ issuer: "Aster PLC", event: "agreed a material merger", materiality: "material", claimed_nonpublic: "confidential", confidence: .85 }] : [], complete: true };
    const proposal = decodeProposal(text, { finish_reason: "stop", message: { content: JSON.stringify(raw) } }, true);
    for (const enabledPii of [false, true]) for (const enabledMnpi of [false, true]) for (const threshold of [0, .5, .7, .85, .95, 1]) for (const mnpiExtent of ["evidence", "sentences"]) {
      const result = automaticRedaction(proposal, { ...DEFAULT_SETTINGS, pii: enabledPii, mnpi: enabledMnpi, threshold, mnpiExtent });
      const removePii = pii && enabledPii && threshold <= .85, removeMnpi = mnpi && enabledMnpi && threshold <= .85;
      assert.equal(result.findings, Number(removePii) + Number(removeMnpi));
      assert.equal(result.text.includes("a@example.org"), pii && !removePii);
      assert.equal(result.text.includes("Aster PLC"), mnpi && !removeMnpi);
      assert.ok(result.text.startsWith("🙂 Public context. "));
      assert.ok(result.text.endsWith("Other context."));
      if (!removePii && !removeMnpi) assert.equal(result.text, text);
      if (removeMnpi && mnpiExtent === "evidence") assert.ok(result.text.includes("Listed [REDACTED]."));
      if (removeMnpi && mnpiExtent === "sentences") assert.ok(!result.text.includes("Listed "));
    }
  }
});
