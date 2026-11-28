// shadow candidate only: explicit personal context plus structured source patterns.
export function localPiiCandidate(text) {
  const findings = [];
  const patterns = [
    ["EMAIL", /[\w.!#$%&'*+/=?^`{|}~-]+@[\w-]+(?:\.[\w-]+)+/gu, /(?:personal|private|employee|individual|patient|customer)(?:'s)?(?:[- ](?:employee|personal|private))?\s+(?:email|inbox)/iu],
    ["PHONE", /\+?\d[\d ()-]{6,}\d/gu, /(?:personal|private|her|his|employee).{0,24}(?:mobile|phone)|(?:mobile|phone).{0,24}(?:personal|private)/iu],
    ["NATIONAL_ID", /\b[A-Z]\d{7}[A-Z]\b/gu, /nric|national\s+id|identity\s+(?:card|number)/iu],
    ["BANK_ACCOUNT", /\b\d{2,}(?:[- ]\d+)+\b/gu, /personal\s+bank\s+account|(?:employee|patient|customer).{0,24}bank\s+account/iu],
    ["DATE_OF_BIRTH", /\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Z][a-z]+\s+\d{4})\b/gu, /date\s+of\s+birth|birth\s+date|\bdob\b/iu],
    ["PERSONAL_RECORD_ID", /\b[A-Z]{2,6}-[A-Z0-9]+(?:-[A-Z0-9]+)*\b/gu, /(?:individual|patient|personal|employee).{0,35}(?:file reference|record number|file|record|reference)/iu],
  ];
  for (const [label, pattern, context] of patterns) for (const match of text.matchAll(pattern)) {
    const lineStart = text.lastIndexOf("\n", match.index) + 1;
    const prefix = text.slice(lineStart, match.index).split(/[.!?;]\s+|\n/u).at(-1);
    const field = context.exec(prefix);
    if (!field || !/^\s*(?:is|number|reference)?\s*[:=]?\s*["“']?\s*$/iu.test(prefix.slice(field.index + field[0].length)) || /shared|company-wide|company inbox|helpdesk|switchboard|corporate contact/iu.test(prefix)) continue;
    const start_char = Array.from(text.slice(0, match.index)).length;
    findings.push({ label, matched_text: match[0], start_char, end_char: start_char + Array.from(match[0]).length,
      origin: "explicit_context_local_pattern", confidence_kind: "not_a_probability" });
  }
  for (const line of text.matchAll(/(?:^|\n)([^\n]+)/gu)) {
    const content = line[1];
    if (/shared|company-wide|corporate/iu.test(content)) continue;
    const name = content.match(/^(?:Individual|Person|Employee name|Patient name|Customer name):\s*(.+?)\s*[.;]?$/iu)?.[1];
    const address = content.match(/^(?:Employee\s+)?(?:home|residential|personal)\s+address:\s*(.+?)\s*[.;]?$/iu)?.[1];
    let quote, label;
    if (name && /^[\p{L}'’-]+(?:\s+[\p{L}'’-]+){1,3}$/u.test(name) && name.split(/\s+/).every(word => /^[\p{Lu}\p{Script=Han}]/u.test(word)) && !/\b(?:Ltd|Limited|PLC|Corp|Inc|LLC|Holdings|Unknown|Unassigned)\b/iu.test(name)) { quote = name; label = "PERSON_NAME"; }
    if (address && /^\d{1,5}\s+[\p{L}\d\s'’-]+,\s*Singapore\s+\d{6}$/u.test(address)) { quote = address; label = "POSTAL_ADDRESS"; }
    if (!quote) continue;
    const index = line.index + line[0].indexOf(quote), start_char = Array.from(text.slice(0, index)).length;
    findings.push({ label, matched_text: quote, start_char, end_char: start_char + Array.from(quote).length, origin: "explicit_context_local_pattern", confidence_kind: "not_a_probability" });
  }
  return findings;
}
