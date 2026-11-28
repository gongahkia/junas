import { automaticRedaction, eligibleFindings } from "../src/auto-redaction.js";
import { previewRedaction } from "../src/contract.js";

export function redactorMetrics(cases, rows, policy, choose = null) {
  const byId = new Map(rows.map(r => [r.id, r]));
  let failed = 0, abstained = 0, changed = 0, piiGold = 0, piiCovered = 0, extra = 0, removed = 0, exactOutputs = 0, mnpiPositive = 0, mnpiRedacted = 0, negativeChanged = 0;
  const examples = [];
  for (const item of cases) {
    const row = byId.get(item.id), reference = new Set();
    if (policy.pii) for (const span of item.pii_evidence) for (let i = span.start_char; i < span.end_char; i++) reference.add(i);
    piiGold += reference.size;
    // no exact MNPI span gold exists: its authored event paragraph is an allowable region, not a minimal-span annotation.
    const allowable = new Set(reference);
    if (policy.mnpi && item.expected.mnpi === "present") {
      mnpiPositive++;
      const financial = item.text.split(/\n+/).find(line => /(?:Listed issuer|Listed |Orchid Holdings)/.test(line)) ?? item.text.split("\n")[0];
      const start = Array.from(item.text.slice(0, item.text.indexOf(financial))).length;
      for (let i = start; i < start + Array.from(financial).length; i++) allowable.add(i);
    }
    if (!policy.pii && !policy.mnpi) { examples.push({ id: item.id, input: item.text, output: item.text, removed_chars: 0 }); continue; }
    if (!row || row.error) {
      failed++;
      if (!choose) { examples.push({ id: item.id, input: item.text, output: item.text, error: row?.error ?? "missing result", phase: row?.phase ?? "missing" }); continue; }
    }
    if (row && row.text !== item.text) throw Error("Result source mismatch.");
    const proposal = row?.proposal;
    if (!proposal?.complete || ["pii", "mnpi"].some(c => policy[c] && proposal.sensitivity[c].state === "unknown")) abstained++;
    const findings = choose ? choose(item, row, policy) : eligibleFindings(proposal, policy), mask = new Set();
    for (const span of findings) for (let i = span.start_char; i < span.end_char; i++) mask.add(i);
    const output = choose ? previewRedaction(item.text, findings) : automaticRedaction(proposal, policy).text;
    if (mask.size) changed++;
    removed += mask.size;
    piiCovered += [...reference].filter(i => mask.has(i)).length;
    extra += [...mask].filter(i => !allowable.has(i)).length;
    const isNegative = (!policy.pii || item.expected.pii === "not_detected") && (!policy.mnpi || item.expected.mnpi === "not_detected");
    if (isNegative && mask.size) negativeChanged++;
    if (policy.mnpi && item.expected.mnpi === "present" && findings.some(f => f.label === "CONTEXTUAL_MNPI")) mnpiRedacted++;
    if (!policy.mnpi || item.expected.mnpi === "not_detected") {
      if (mask.size === reference.size && [...mask].every(i => reference.has(i))) exactOutputs++;
    }
    examples.push({ id: item.id, input: item.text, output, complete: proposal?.complete ?? false, error: row?.error, removed_chars: mask.size,
      pii_missed_chars: [...reference].filter(i => !mask.has(i)).length, outside_allowable_chars: [...mask].filter(i => !allowable.has(i)).length });
  }
  return { policy, documents: cases.length, failed, abstained, changed, pii_gold_chars: piiGold, pii_redacted_chars: piiCovered,
    pii_char_recall: piiGold ? piiCovered / piiGold : null, removed_chars: removed, outside_allowable_chars: extra,
    negative_documents_changed: negativeChanged, exact_pii_only_outputs: exactOutputs, mnpi_positive_documents: mnpiPositive, mnpi_documents_redacted: mnpiRedacted,
    interpretation: "Authored reference agreement. MNPI uses passage-level detection and an allowable paragraph, not exact minimal-span gold. Failures remain in recall denominators.", examples };
}
