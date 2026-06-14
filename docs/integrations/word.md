# Word Taskpane

Source: `integrations/word_addin/`

Compatibility path: `packaging/word_addin/`

Maturity: `experimental`

Runtime target: Office.js Word taskpane for user-triggered document review.

Current files:

- `manifest.xml`: Word taskpane manifest, `ReadDocument` permission, Home tab command.
- `taskpane.html`, `taskpane.js`: local document review UI.

Deploy:

```sh
integrations/word_addin/manifest.xml
```

Current behavior:

- Opens a Kaypoh Review taskpane from Word.
- Reviews selected or provided document text through the configured backend/local daemon.
- Does not enforce send-time, upload-time, or repository check-in behavior.

## Document Review Flow

1. User opens the Kaypoh taskpane from the Word Home tab.
2. User chooses review selection or review body.
3. `taskpane.js` reads selected text through `Office.context.document.getSelectedDataAsync` or full body text through `Word.run`.
4. The taskpane calls `/review` with `document_type="word_document"`, `review_profile="strict"`, and `degraded_policy="warn"`.
5. The taskpane renders scores, finding count, degraded-mode count, and `send_allowed` status.

## Enforcement Boundary

The Word taskpane is document review, not true send-time enforcement.

- It does not block Word save, export, print, share, email-send, DMS upload, or repository check-in.
- It does not run automatically on every document edit.
- It does not inspect recipients, destination repositories, or external sharing context.
- It should route users to Outlook Smart Alerts, DMS hooks, or direct API review when completion must be enforced.

Use Word review for author-side checking, drafting cleanup, and local proofing before a controlled workflow performs final policy review.

## Deployment Notes

- Replace `https://localhost:3000` manifest URLs with a deployer-controlled HTTPS origin before pilot deployment.
- `ReadDocument` is required because the taskpane reads selected or body text.
- Production deployment should use Microsoft 365 admin-managed deployment or a controlled dev sideload path.
- Backend auth should use tenant API/JWT auth or local pairing token, depending on deployment mode.

## Failure Behavior

- Backend error: show the error in the taskpane output; no Word action is blocked.
- Degraded review: show degraded count and `send_allowed`; final completion must be enforced elsewhere.
- Empty selection/body: backend validation can fail because `/review` requires text or document payload.
- User edits after review: require a fresh taskpane review before relying on the result.

Security model:

- Production deployment should use Microsoft 365 admin-managed deployment.
- Backend calls must use tenant auth or local pairing token.
- Document text should be sent only to the configured Kaypoh backend/local daemon.
- The taskpane must not persist raw document text, reversible mappings, or auth headers in Office storage or logs.
