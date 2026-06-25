# Review Examples

Each example uses the same current backend contract: `POST /review` with inline `text` or `document_base64`, jurisdiction fields, `document_type`, optional `entity_id`, and `include_suggestions`. Workflow-context fields such as `surface` and `workflow` are planned policy-contract work and are intentionally not used here until the schema accepts them.

## GenAI Prompt

```json
{
  "text": "Draft a client update for Project Raven. Include Dr Jane Tan's NRIC S1234567D and note that Acme will acquire GlobalTech before the announcement.",
  "source_jurisdiction": "SG",
  "destination_jurisdiction": "US",
  "document_type": "genai_prompt",
  "entity_id": "Acme",
  "include_suggestions": true
}
```

## External Email

```json
{
  "text": "Subject: Draft terms\n\nPlease send the draft SPA to outside counsel. Jane Tan S1234567D is listed as signatory. Project Raven pricing is still confidential.",
  "source_jurisdiction": "SG",
  "destination_jurisdiction": "US",
  "document_type": "email",
  "entity_id": "Project Raven",
  "include_suggestions": true
}
```

## Legal Memo

```json
{
  "text": "Privileged draft memo: Acme has not announced the GlobalTech acquisition. The board pack includes passport E1234567 for the executive witness.",
  "source_jurisdiction": "SG",
  "destination_jurisdiction": "UK",
  "document_type": "legal_memo",
  "entity_id": "Acme",
  "review_profile": "strict",
  "include_suggestions": true
}
```

## DMS Upload

```json
{
  "document_base64": "UHJvamVjdCBSYXZlbiBjbG9zaW5nIG1lbW8uIEphbmUgVGFuIFMxMjM0NTY3RCBpcyBsaXN0ZWQgYXMgYXV0aG9yaXNlZCBzaWduYXRvcnku",
  "document_filename": "closing-memo.txt",
  "document_mime_type": "text/plain",
  "source_jurisdiction": "SG",
  "destination_jurisdiction": "US",
  "document_type": "dms_upload",
  "entity_id": "Project Raven",
  "include_suggestions": true
}
```

## Slack-style Message

This is a direct API example for a Slack-like collaboration message. It is not a claim that a Slack adapter exists.

```json
{
  "text": "Can someone review this before I post? GlobalTech acquisition will be announced Monday, and Dr Jane Tan's passport E1234567 is in the draft.",
  "source_jurisdiction": "SG",
  "destination_jurisdiction": "SG",
  "document_type": "collaboration_message",
  "entity_id": "GlobalTech",
  "include_suggestions": true
}
```
