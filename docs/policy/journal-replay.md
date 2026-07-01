# Review Decision Journal Replay

The review journal is replayed as an event log. `review_started` records the initial findings and each `decision_recorded` event records one reviewer action for one finding. Replay uses the latest decision per `finding_id`.

HMAC chaining provides tamper-evidence only when `JUNAS_JOURNAL_KEY` or
`JUNAS_JOURNAL_KEYS_FILE` is supplied. Junas does not provide OS-level append-only
storage.

## Action Compatibility

Decision taxonomy is documented separately in
`docs/policy/decision-taxonomy.md`. Taxonomy labels explain feedback meaning, while
actions below explain workflow state.

Legacy actions remain valid:

- `accept`: finding is accepted as valid.
- `reject`: finding is rejected. It is excluded by downstream `findings_after_decisions` only when recorded by an authorized reviewer identity.
- `rewrite`: finding is valid and needs replacement text.

Extended actions are additive:

- `approve`: reviewer approves proceeding with the finding present.
- `policy_exception`: reviewer approves a documented exception.
- `accept_risk`: reviewer accepts the risk for this finding.
- `request_changes`: reviewer requires content changes before completion.
- `hold`: reviewer requires holding the content.

## Replay Rules

- Old journal entries replay unchanged; missing extended actions need no migration.
- New actions are stored in the same `decision_recorded.payload.action` string field.
- New privacy-safe feedback metadata may be stored on the same event as optional
  `decision_taxonomy`, `reviewer_confidence`, and `detector_feedback` fields.
- `reject` is the only action that can remove a finding from downstream anonymization input.
- Reject removal requires `reviewer_identity_source` of `api_key`, `jwt`, or `dev_header` plus a non-empty `reviewer_id`.
- `none`, empty, or legacy reviewer identity sources preserve the finding for downstream anonymization.
- All other known actions keep the finding visible for audit, export, and later review.
- Unknown future actions must be preserved as strings and treated as non-reject for replay unless a later version documents stricter behavior.
- Audit exports preserve raw action strings in `decisions.json` and count all known action names instead of collapsing them to the legacy three-action set.
- Feedback exports preserve the raw action string for emitted rows; unknown future actions should be skipped until explicitly mapped.

## API Compatibility

`POST /review/{review_id}/decision` keeps `finding_id` and `action` as the only
required request fields. Optional `decision_taxonomy`, `reviewer_confidence`, and
`detector_feedback` fields can be sent without raw text. Existing clients that send
only `accept`, `reject`, or `rewrite` continue to work without request changes.
