# Word Taskpane

Source: `packaging/word_addin/`

Maturity: `experimental`

Runtime target: Office.js Word taskpane for user-triggered document review.

Current files:

- `manifest.xml`: Word taskpane manifest, `ReadDocument` permission, Home tab command.
- `taskpane.html`, `taskpane.js`: local document review UI.

Deploy:

```sh
packaging/word_addin/manifest.xml
```

Current behavior:

- Opens a Kaypoh Review taskpane from Word.
- Reviews selected or provided document text through the configured backend/local daemon.
- Does not enforce send-time, upload-time, or repository check-in behavior.

Security model:

- Production deployment should use Microsoft 365 admin-managed deployment.
- Backend calls must use tenant auth or local pairing token.
- Document text should be sent only to the configured Kaypoh backend/local daemon.
- The taskpane must not persist raw document text, reversible mappings, or auth headers in Office storage or logs.
