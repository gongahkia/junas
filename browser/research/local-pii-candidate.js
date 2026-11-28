// shadow candidate only: explicit personal context plus structured source patterns.
export function localPiiCandidate(text) {
  const findings = [];
  const patterns = [
    ["EMAIL", /[\w.!#$%&'*+/=?^`{|}~-]+@[\w-]+(?:\.[\w-]+)+/gu, /personal|private|employee|individual|patient|customer/iu],
    ["PHONE", /\+?\d[\d ()-]{6,}\d/gu, /(?:personal|private|her|his|employee).{0,24}(?:mobile|phone)|(?:mobile|phone).{0,24}(?:personal|private)/iu],
    ["NATIONAL_ID", /\b[A-Z]\d{7}[A-Z]\b/gu, /nric|national\s+id|identity\s+(?:card|number)/iu],
    ["BANK_ACCOUNT", /\b\d{2,}(?:[- ]\d{2,}){1,3}\b/gu, /personal\s+bank\s+account|(?:employee|patient|customer).{0,24}bank\s+account/iu],
    ["DATE_OF_BIRTH", /\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Z][a-z]+\s+\d{4})\b/gu, /date\s+of\s+birth|birth\s+date|\bdob\b/iu],
    ["PERSONAL_RECORD_ID", /\b[A-Z]{2,6}-[A-Z0-9]+(?:-[A-Z0-9]+)*\b/gu, /(?:individual|patient|personal|employee).{0,35}(?:file|record|reference)/iu],
  ];
  for (const [label, pattern, context] of patterns) for (const match of text.matchAll(pattern)) {
    const lineStart = text.lastIndexOf("\n", match.index) + 1;
    const line = text.slice(lineStart, text.indexOf("\n", match.index) < 0 ? text.length : text.indexOf("\n", match.index));
    if (!context.test(line) || /shared|company-wide|company inbox|helpdesk|switchboard|corporate contact/iu.test(line)) continue;
    const start_char = Array.from(text.slice(0, match.index)).length;
    findings.push({ label, matched_text: match[0], start_char, end_char: start_char + Array.from(match[0]).length,
      origin: "explicit_context_local_pattern", confidence_kind: "not_a_probability" });
  }
  return findings;
}
