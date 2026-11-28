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
