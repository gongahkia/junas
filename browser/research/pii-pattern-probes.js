// additional authored development probes; never used as untouched validation.
import { localPiiCandidate } from "./local-pii-candidate.js";
import { previewRedaction } from "../src/contract.js";

export function patternProbes() {
  const items = [
    ["unrelated-date", "Employee date of birth: unavailable. Shipment date: 1991-07-02.", []],
    ["unrelated-phone-shaped-number", "Her private mobile is unavailable. Delivery reference: +65 8123 9876.", []],
    ["unrelated-account", "Personal bank account: unavailable. Invoice number: 188-332-994.", []],
    ["unrelated-mailbox", "Employee personal email: unavailable. Vendor inbox: orders@example.org.", []],
    ["personal-and-shared-same-line", "Personal email: nova@example.org. Shared helpdesk: help@example.org.", [["EMAIL", "nova@example.org"]]],
    ["repeated-personal-email", "Personal email: nova@example.org. Personal email: nova@example.org.", [["EMAIL", "nova@example.org"], ["EMAIL", "nova@example.org"]]],
    ["long-account-boundary", "Personal bank account: 123-456-7-8-9.", [["BANK_ACCOUNT", "123-456-7-8-9"]]],
    ["narrative-personal-name", "The employee's name is Nadia Rios.", [["PERSON_NAME", "Nadia Rios"]]],
  ];
  return items.map(([id, text, expected]) => {
    let cursor = 0;
    const gold = expected.map(([label, quote]) => {
      const index = text.indexOf(quote, cursor); cursor = index + quote.length;
      const start_char = Array.from(text.slice(0, index)).length;
      return { label, matched_text: quote, start_char, end_char: start_char + Array.from(quote).length };
    });
    const actual = localPiiCandidate(text);
    const canonical = rows => rows.map(r => `${r.label}:${r.start_char}:${r.end_char}`).sort().join("|");
    return { id, text, expected: gold, actual, exact: canonical(actual) === canonical(gold), output: previewRedaction(text, actual) };
  });
}
