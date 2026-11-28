import { eligibleFindings } from "../src/auto-redaction.js";
import { localPiiCandidate } from "./local-pii-candidate.js";
export function shadowFindings(item, row, policy) {
  return [...(row?.proposal ? eligibleFindings(row.proposal, policy) : []), ...(policy.pii ? localPiiCandidate(item.text) : [])];
}
