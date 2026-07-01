# Future Slack And Google Workspace Notes

Status: research-only until implemented. There is no Slack or Google Workspace adapter source in this repo, and no production support claim exists for either surface.

Verified against official Slack and Google documentation on 2026-07-01. Use this page for roadmap scoping only; use `surface="api"` or an already implemented adapter for production pilots today.

## Claim Boundary

- Do not claim Slack, Gmail, Google Chat, Google Drive, Calendar, Chrome, Docs, Sheets, or Slides coverage from this repo.
- Do not claim Junas replaces Slack DLP, Google Workspace data protection rules, Google Vault, CASB, endpoint DLP, or native admin controls.
- Do not claim pre-send blocking until an implemented adapter has install, auth, policy-decision mapping, failure behavior, privacy, telemetry, uninstall, and smoke-test evidence.
- Future implementations must use the backend `/review` contract and must not store raw message, file, prompt, document, matched text, auth tokens, or admin investigation data in adapter logs or telemetry.

## Research Summary

| Platform | Official surface | Research implication |
|---|---|---|
| Slack | Slack DLP scans messages, text-based files, and canvases, with rule actions such as dashboard alert, warning, and hide/tombstone. | Treat Slack DLP as the native control plane; a Junas adapter would need to interoperate with approved Slack DLP/Discovery flows, not bypass them. |
| Slack | Slack Discovery APIs support eDiscovery and DLP apps that scan messages and files, support policy enforcement, and allow quarantined content to be reviewed or removed. | Any Junas Slack pilot must validate Enterprise/Discovery eligibility and write-path permissions before claiming enforcement. |
| Slack | Slack Enterprise data-management docs say canvases and lists can be downloaded/scanned through Discovery API endpoints and can support tombstone/delete operations. | Canvas/list coverage is research-only and must be separately certified from ordinary messages/files. |
| Google Workspace | Google data protection rules cover selected apps including Chat, Drive, Gmail, Calendar, and Chrome; rules define what to scan and what action to take. | Treat Google Workspace DLP as the native admin surface. Junas should not claim broad Workspace DLP coverage from a single add-on or API flow. |
| Gmail | Gmail DLP scans sent/received messages and attachments; actions include block, warn, quarantine, audit, labels, and custom notes. | A future Gmail path must decide whether Junas runs before native Gmail DLP, as a gateway/API workflow, or only as advisory review. |
| Google Chat | Chat DLP scans sent messages and uploaded attachments; actions include block, warn, and audit. | A future Chat path must model message/file-upload triggers and latency/degraded scan behavior. |
| Google Admin APIs | Alert Center exposes DLP rule violation data, and Reports API chat activity includes `dlp_scan_status`. | Admin evidence integration should consume native alert/audit metadata, not scrape user content. |

## Future Slack Scope

Potential request context if implemented:

```json
{
  "surface": "slack",
  "workflow": "collaboration_message",
  "document_type": "chat_message",
  "actor_role": "end_user",
  "external_destination": true,
  "recipient_count": 8,
  "attachment_count": 1,
  "requested_action": "send"
}
```

Research-only capture surfaces:

- message posted or edited
- file shared or uploaded
- Slack Connect channel or DM context
- canvas/list content when Enterprise Discovery support is explicitly validated
- admin review/tombstone/delete events from approved DLP or Discovery workflows

Required before implementation:

- Confirm Enterprise Grid or eligible plan requirements for Slack DLP/Discovery.
- Define install and admin-consent flow.
- Define whether Junas is advisory, warn-only, tombstone/hide-capable, or reviewer-routed.
- Map Slack conversation/workspace/channel ids to privacy-safe counts/hashes; do not store raw channel names or message links in telemetry.
- Add fixture Slack pages/API payloads that run without Slack credentials.
- Add adapter telemetry: `slack_review_started`, `slack_policy_decision_received`, `slack_message_held`, `slack_backend_failure`.
- Document failure behavior for API timeout, missing scopes, Slack Connect external ownership, message edit after review, and file-scan delay.

Not supported today:

- no Slack app manifest
- no Slack event receiver
- no Slack Discovery API connector
- no Slack DLP write-back
- no Slack Connect enforcement proof

## Future Google Workspace Scope

Potential request contexts if implemented:

```json
{
  "surface": "google_workspace",
  "workflow": "email_send",
  "document_type": "email",
  "actor_role": "end_user",
  "external_destination": true,
  "recipient_domains": ["outside-counsel.example"],
  "recipient_count": 2,
  "attachment_count": 1,
  "requested_action": "send"
}
```

```json
{
  "surface": "google_workspace",
  "workflow": "collaboration_message",
  "document_type": "chat_message",
  "actor_role": "end_user",
  "external_destination": true,
  "attachment_count": 1,
  "requested_action": "submit"
}
```

Research-only capture surfaces:

- Gmail outgoing message and attachment review
- Google Chat sent message and attachment upload review
- Drive file upload/share review
- Docs/Sheets/Slides editor review only if implemented as an add-on or workflow hook with clear enforcement limits
- Alert Center `DlpRuleViolation` and Reports API audit joins for admin evidence

Required before implementation:

- Confirm Workspace edition, admin privileges, and OAuth scopes for the selected app surface.
- Decide whether Junas is pre-send/pre-upload enforcement, advisory review, or SIEM/audit evidence only.
- Map Workspace actors, recipients, shared-drive/external-share context, and attachment counts to backend workflow fields.
- Keep raw message bodies, file contents, snippets, attachment names, Drive titles, and admin investigation details out of telemetry.
- Add local fixture tests for Gmail-like send, Chat-like message/file upload, and Drive-like document upload without Google credentials.
- Document interaction with native Google DLP actions: block, warn, quarantine, audit, labels, and custom notes.

Not supported today:

- no Google Workspace add-on
- no Gmail/Chat/Drive event hook
- no Admin SDK connector
- no Alert Center ingest
- no Google Workspace Marketplace deployment

## Implementation Gate

Before either future surface can move beyond research-only:

- Add source code under `integrations/` with a clear owner and runtime target.
- Add auth and tenant-boundary docs.
- Add privacy storage/log tests.
- Add failure-semantics tests.
- Add smoke tests that run without external SaaS credentials.
- Update `docs/integrations/compatibility-matrix.md`.
- Update `INTEGRATIONS.md` maturity from `planned` only after evidence exists.

## Official References

- Slack data loss prevention: <https://slack.com/help/articles/12914005852819-Slack-data-loss-prevention>
- Slack Discovery APIs: <https://slack.com/help/articles/360002079527-A-guide-to-Slacks-Discovery-APIs>
- Slack canvases/lists data management: <https://slack.com/help/articles/15708101445011-How-data-management-features-apply-to-canvases-and-lists>
- Google Workspace DLP overview: <https://knowledge.workspace.google.com/admin/security/about-dlp>
- Google data protection rules: <https://knowledge.workspace.google.com/admin/security/create-data-protection-rules>
- Gmail DLP: <https://knowledge.workspace.google.com/admin/security/prevent-data-leaks-in-email-and-attachments-gmail-dlp>
- Google Chat DLP: <https://knowledge.workspace.google.com/admin/security/prevent-data-leaks-from-chat-messages-and-attachments>
- Google Alert Center DLP rule violations: <https://developers.google.com/workspace/admin/alertcenter/reference/rest/v1beta1/DlpRuleViolation>
- Google Chat audit activity: <https://developers.google.com/workspace/admin/reports/v1/appendix/activity/chat>
