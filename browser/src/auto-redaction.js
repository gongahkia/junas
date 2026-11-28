import { previewRedaction } from "./contract.js";
export function automaticRedaction(proposal, preferences) {
  const findings = [];
  if (proposal.complete) for (const category of ["pii", "mnpi"]) {
    const assessment = proposal.sensitivity[category];
    if (preferences[category] && assessment.state === "present") findings.push(...assessment.evidence.filter(e => Number.isFinite(e.confidence) && e.confidence >= preferences.threshold));
  }
  return { text: previewRedaction(proposal.document.text, findings), findings: findings.length };
}
