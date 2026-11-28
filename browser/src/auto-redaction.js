import { previewRedaction } from "./contract.js";
export function eligibleFindings(proposal, preferences) {
  const findings = [];
  if (proposal.complete) for (const category of ["pii", "mnpi"]) {
    const assessment = proposal.sensitivity[category];
    if (preferences[category] && assessment.state === "present") findings.push(...assessment.evidence.filter(e => Number.isFinite(e.confidence) && e.confidence >= preferences.threshold));
  }
  if (preferences.mnpiExtent === "sentences") {
    const text = proposal.document.text;
    const sentences = [...new Intl.Segmenter("en", { granularity: "sentence" }).segment(text)].map(s => ({
      start: Array.from(text.slice(0, s.index)).length,
      end: Array.from(text.slice(0, s.index + s.segment.length)).length,
    }));
    return findings.map(f => {
      if (f.label !== "CONTEXTUAL_MNPI") return f;
      const matching = sentences.filter(s => s.start < f.end_char && f.start_char < s.end);
      if (!matching.length) return f;
      const start_char = matching[0].start, end_char = matching.at(-1).end;
      return { ...f, start_char, end_char, matched_text: Array.from(text).slice(start_char, end_char).join("") };
    });
  }
  return findings;
}
export function automaticRedaction(proposal, preferences) {
  const findings = eligibleFindings(proposal, preferences);
  return { text: previewRedaction(proposal.document.text, findings), findings: findings.length };
}
