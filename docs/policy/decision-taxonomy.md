# Decision Taxonomy

Decision taxonomy labels classify why a reviewer decision was made. They are orthogonal
to review actions from `docs/policy/journal-replay.md`: actions describe workflow state,
while taxonomy labels describe feedback meaning for policy, detector quality, and audit
reporting.

## Allowed Labels

- `false_positive`: the finding is not a real issue after authorized review. This can
  feed false-positive triage, but it must not automatically rewrite detector labels.
- `false_negative`: a reviewer, user, or approval workflow found a missed issue. This
  creates detector-miss work and must not remove any existing finding.
- `acceptable_risk`: the finding is real, but the risk is accepted under the active
  policy or reviewer authority. This is not a detector precision problem.
- `public_source_confirmed`: a public source confirms the information is public enough
  for the workflow. Store source metadata and hashes, not copied source text.
- `stale_information`: the finding relates to information that is no longer current,
  material, or inside the configured retention/relevance window.
- `policy_exception`: an explicit tenant-policy exception applies. This is distinct
  from `false_positive` because the finding can still be real.

## Privacy Rules

Taxonomy capture must be privacy-safe by default:

- store the taxonomy label, reviewer role, finding id, rule, category, severity, and
  hashes for text-bearing fields
- accept optional `reviewer_confidence` and structured `detector_feedback` metadata
  without requiring raw text
- do not require raw prompt, email body, document text, matched text, recipient address,
  filename, or source excerpt
- use rationale fields only for scrubbed operational notes
- treat taxonomy as feedback evidence, not as automatic training data

## Replay Compatibility

Existing journal entries without taxonomy replay unchanged. New payload fields should
preserve unknown future taxonomy strings for audit display, but only labels in
`junas.review.decisions.DECISION_TAXONOMY` may be accepted by current write paths.
