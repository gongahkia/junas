# Outlook Smart Alerts Add-In

Source: `integrations/outlook_addin/`

Compatibility path: `packaging/office_addin/`

Maturity: `supported-target`

Runtime target: Office.js Outlook add-in with taskpane plus Smart Alerts `OnMessageSend` launch event.

Current files:

- `manifest.xml`: Mailbox add-in manifest, `OnMessageSend`, `SendMode="SoftBlock"`, taskpane and runtime URLs.
- `launchevent.js`: event-based send handler runtime.
- `taskpane.html`, `taskpane.js`: local review and pairing UI.
- `commands.html`: event runtime host page.

Deploy:

```sh
# dev or staging manifest host must serve HTTPS URLs referenced by manifest.xml
integrations/outlook_addin/manifest.xml
```

Current behavior:

- Manifest requests Mailbox requirement set 1.15 in version overrides.
- Taskpane and launch-event URLs currently point to `https://localhost:3000`.
- Outlook send checks should call `/review` with `surface=outlook` and `workflow=email_send` when the Smart Alerts path is implemented.

Security model:

- Production deployment should use Microsoft 365 admin-managed deployment.
- Add-in origin must be HTTPS and controlled by the deployer.
- Backend calls must use tenant auth or local pairing token.
- Message body, subject, recipients, attachments, auth headers, and policy responses must not be stored in local storage, extension storage, or console logs.
- Outlook client support depends on Microsoft requirement sets and Smart Alerts platform behavior.
