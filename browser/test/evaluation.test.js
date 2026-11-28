import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import { makeCases } from "../eval/cases.js";
import { scoreResults, validateCases } from "../src/evaluation.js";
import { inferenceRequest } from "../src/contract.js";
const cases = makeCases();
const rows = cases.map(c => ({ id: c.id, text: c.text, states: c.expected, pii_evidence: c.pii_evidence, inference_ms: 20 }));
test("fixed comparison screen retains every family, PII type and balanced core quadrants", async () => {
  const ids = JSON.parse(await readFile(new URL("../eval/screening-ids.json", import.meta.url)));
  const screen = cases.filter(c => ids.includes(c.id));
  assert.equal(ids.length, 32); assert.equal(new Set(ids).size, 32); assert.equal(screen.length, 32);
  assert.equal(new Set(screen.map(c => c.family)).size, 24);
  assert.equal(new Set(screen.flatMap(c => c.pii_evidence.map(e => e.label))).size, 9);
  for (const q of ["both", "pii_only", "mnpi_only", "neither"]) assert.equal(screen.filter(c => c.quadrant === q).length, 6);
});
test("corpus is reproducible, broad, balanced and within the full prompt budget", async () => {
  assert.deepEqual(JSON.parse(await readFile(new URL("../eval/cases.json", import.meta.url))), cases);
  assert.equal(validateCases(cases).length, 144);
  for (const quadrant of ["both", "pii_only", "mnpi_only", "neither"]) assert.equal(cases.filter(c => c.quadrant === quadrant).length, 32);
  assert.equal(new Set(cases.flatMap(c => c.pii_evidence.map(s => s.label))).size, 9);
  assert.equal(new Set(cases.filter(c => c.quadrant !== "edge").map(c => c.family)).size, 16);
  for (const c of cases) {
    const request = inferenceRequest(c.text);
    assert.ok(request.messages.reduce((n, m) => n + new TextEncoder().encode(m.content).length, 0) + 1536 <= 4096);
  }
});
test("errors and missing cases stay in denominators", () => {
  const perfect = scoreResults(cases, rows);
  assert.equal(perfect.failed, 0); assert.equal(perfect.passed, true);
  const failed = scoreResults(cases, []);
  assert.equal(failed.failed, 144); assert.equal(failed.passed, false);
  assert.equal(failed.inference_ms.p95, null);
  const oneError = scoreResults(cases, rows.map((r, i) => i === 0 ? { ...r, error: "timeout" } : r));
  assert.equal(oneError.failed, 1); assert.equal(oneError.passed, false);
});
test("wrong sources, reused identities and invalid spans cannot be scored", () => {
  assert.throws(() => scoreResults(cases, [...rows, rows[0]]));
  assert.throws(() => scoreResults(cases, [{ ...rows[0], text: "another source" }]));
  assert.throws(() => validateCases([{ ...cases[0], split: "holdout" }]));
  const r = rows.find(r => r.pii_evidence.length);
  assert.throws(() => scoreResults(cases, [{ ...r, pii_evidence: [{ ...r.pii_evidence[0], end_char: 9999 }] }]));
});
test("overlap matching is one-to-one and independent of prediction order", () => {
  const c = { ...cases[0], id: "matching", text: "abc def", pii_evidence: [
    { label: "EMAIL", start_char: 0, end_char: 3, matched_text: "abc" },
    { label: "EMAIL", start_char: 4, end_char: 7, matched_text: "def" },
  ] };
  const evidence = [
    { label: "EMAIL", start_char: 0, end_char: 7, matched_text: "abc def" },
    { label: "EMAIL", start_char: 0, end_char: 3, matched_text: "abc" },
  ];
  for (const pii_evidence of [evidence, [...evidence].reverse()]) assert.equal(scoreResults([c], [{ id: c.id, text: c.text, states: c.expected, pii_evidence }]).pii_spans.overlapping_matches, 2);
});
