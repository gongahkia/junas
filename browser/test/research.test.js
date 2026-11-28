import assert from "node:assert/strict";
import { test } from "node:test";
import { createHash } from "node:crypto";
import { makeValidationCases } from "../research/validation-cases.mjs";
import { rankCandidates } from "../research/selection.mjs";
import { MODEL_IDS } from "../src/contract.js";
import { scoreResults, validateCases } from "../src/evaluation.js";
import { makeCases } from "../eval/cases.js";

test("validation is frozen, disjoint, explicitly scored and balanced without relabeling", () => {
  const cases = makeValidationCases();
  assert.equal(createHash("sha256").update(JSON.stringify(cases, null, 2) + "\n").digest("hex"), "77e98a49189cbe17051cbd8115a1505cb4eea113e3495e45e827a66ef9158233");
  assert.equal(cases.length, 48);
  assert.throws(() => validateCases(cases), /wrong-split/);
  assert.equal(validateCases(cases, { split: "validation" }).length, 48);
  assert.throws(() => validateCases(cases, { split: "holdout" }), /Unsupported/);
  const development = new Set(makeCases().map(c => c.text));
  assert.ok(cases.every(c => !development.has(c.text)));
  for (const quadrant of ["both", "pii_only", "mnpi_only", "neither"]) assert.equal(cases.filter(c => c.quadrant === quadrant).length, 10);
  assert.equal(new Set(cases.flatMap(c => c.pii_evidence.map(e => e.label))).size, 9);
  const report = scoreResults(cases, [], { split: "validation" });
  assert.equal(report.failed, 48); assert.equal(report.passed, false);
  assert.equal(report.reference_kind, "authored_synthetic_validation_expectation");
  assert.equal(cases[0].split, "validation");
});
test("candidate selection rejects partial/missing runs and preserves failed-gate status", () => {
  const reports = MODEL_IDS.map((model, i) => ({ selected_model: model, selected_suite: "screening", documents: 32, received: 32,
    completed: true, failed: 0, model_identity: { model }, passed: false,
    measurements: { pii_positive_detection: .9, mnpi_positive_detection: i === 1 ? .7 : .2, pii_overlap_span_agreement: .8 } }));
  const selected = rankCandidates(reports);
  assert.equal(selected.model, MODEL_IDS[1]);
  assert.equal(selected.status, "exploratory_candidate_with_failed_gates");
  assert.equal(selected.classification_applied, false);
  assert.throws(() => rankCandidates(reports.slice(0, 2)), /One report/);
  assert.throws(() => rankCandidates(reports.map((r, i) => i ? r : { ...r, completed: false })), /Complete/);
  assert.throws(() => rankCandidates(reports.map(r => ({ ...r, failed: 32, model_identity: null }))), /No candidate/);
});
