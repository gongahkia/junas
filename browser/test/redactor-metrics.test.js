import { test } from "node:test";
import assert from "node:assert/strict";
import { redactorMetrics } from "../research/redactor-metrics.js";
import { localPiiCandidate } from "../research/local-pii-candidate.js";
test("redactor scores retain misses/errors and distinguish unnecessary removal", () => {
  const cases = [{ id: "personal", text: "Personal email: nova@example.org.", pii_evidence: [{ start_char: 16, end_char: 32 }], expected: { pii: "present", mnpi: "not_detected" } }];
  const report = redactorMetrics(cases, [], { pii: true, mnpi: false, threshold: .85 });
  assert.equal(report.failed, 1); assert.equal(report.pii_char_recall, 0);
  assert.equal(report.examples[0].output, cases[0].text);
  assert.equal(redactorMetrics(cases, [], { pii: false, mnpi: false, threshold: .85 }).failed, 0);
  const row = { id: cases[0].id, text: cases[0].text, error: "failed" };
  assert.throws(() => redactorMetrics(cases, [row, row], { pii: true }), /Duplicate/);
  assert.throws(() => redactorMetrics(cases, [{ ...row, text: "different source" }], { pii: true }), /wrong-source/);
  assert.throws(() => redactorMetrics(cases, [{ ...row, error: undefined, proposal: { document: { text: "different source" } } }], { pii: true }), /Proposal source/);
});
test("shadow structured-PII candidate requires explicit context and rejects shared contacts", () => {
  assert.equal(localPiiCandidate("Her private mobile is +65 8123 9876.")[0].label, "PHONE");
  assert.equal(localPiiCandidate("Employee date of birth: 1991-07-02.")[0].matched_text, "1991-07-02");
  assert.equal(localPiiCandidate("Personal bank account: 188-332-994.")[0].label, "BANK_ACCOUNT");
  assert.equal(localPiiCandidate("Personal bank account: 991-23456-7.")[0].matched_text, "991-23456-7");
  assert.equal(localPiiCandidate("Shared employee helpdesk: nova@example.org.").length, 0);
  assert.equal(localPiiCandidate("Shipment 1991-07-02. Price +65 8123 9876.").length, 0);
  assert.equal(localPiiCandidate("nova@example.org").length, 0);
  assert.equal(localPiiCandidate("Person: Nadia Rios.")[0].matched_text, "Nadia Rios");
  assert.equal(localPiiCandidate("Person: Acme Holdings Ltd.").length, 0);
  assert.equal(localPiiCandidate("Person: not available.").length, 0);
  assert.equal(localPiiCandidate("Home address: 44 Juniper Road, Singapore 123789.")[0].matched_text, "44 Juniper Road, Singapore 123789");
});
