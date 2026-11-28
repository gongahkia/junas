import { MODEL_IDS } from "../src/contract.js";

export function rankCandidates(reports) {
  if (reports.length !== MODEL_IDS.length || new Set(reports.map(r => r.selected_model)).size !== MODEL_IDS.length) throw Error("One report per declared model is required.");
  for (const report of reports) {
    if (!MODEL_IDS.includes(report.selected_model) || report.selected_suite !== "screening" || report.documents !== 32 || report.received !== 32 || !report.completed) throw Error("Complete fixed-screen reports required before selection.");
    for (const metric of ["pii_positive_detection", "mnpi_positive_detection", "pii_overlap_span_agreement"]) if (!Number.isFinite(report.measurements[metric])) throw Error("Finite screening measurements required.");
  }
  const ranked = [...reports].filter(r => r.model_identity && r.failed < r.documents).sort((a, b) => {
    const weakest = r => Math.min(r.measurements.pii_positive_detection, r.measurements.mnpi_positive_detection);
    return weakest(b) - weakest(a) || b.measurements.pii_overlap_span_agreement - a.measurements.pii_overlap_span_agreement || a.failed - b.failed || MODEL_IDS.indexOf(a.selected_model) - MODEL_IDS.indexOf(b.selected_model);
  });
  if (!ranked.length) throw Error("No candidate produced a usable proposal; no validation candidate can be selected.");
  return { model: ranked[0].selected_model, identity: ranked[0].model_identity, screen_passed: ranked[0].passed,
    status: ranked[0].passed ? "candidate_for_validation" : "exploratory_candidate_with_failed_gates", classification_applied: false,
    ranking: ranked.map(r => r.selected_model), interpretation: "Selection on authored development data; no automatic promotion or independent accuracy claim." };
}
