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
uv run python scripts/render_outlook_manifest.py --profile dev
uv run python scripts/render_outlook_manifest.py --profile staging --origin https://outlook-addin.staging.example.com
uv run python scripts/render_outlook_manifest.py --profile production --origin https://outlook-addin.example.com
uv run python scripts/validate_outlook_manifest.py dist/outlook-addin/production/manifest.xml --profile production
```

The source manifest is a template. Rendered manifests are written to `dist/outlook-addin/{profile}/manifest.xml` by default. Dev defaults to `https://localhost:3000`; staging and production require an explicit non-local HTTPS origin.

## Smart Alerts Flow

1. User selects Send in Outlook.
2. Outlook activates the `OnMessageSend` launch event when the client supports Smart Alerts for that item.
3. `launchevent.js` reads the message body as text.
4. The handler calls `/review` with `document_type="email"`, `review_profile="strict"`, and `degraded_policy="block_send"`.
5. The handler calls `event.completed({allowEvent: true})` only when review completes without degraded coverage, blocking outcome, or findings above the current threshold.
6. When blocked, the user opens the Kaypoh taskpane to review or redact before retrying send.

Target production behavior should include `surface="outlook"`, `workflow="email_send"`, recipients, subject, and attachment metadata when Office.js exposes them. The current launch-event code reviews body text only.

## SendMode Behavior

The current manifest declares:

```xml
<LaunchEvent Type="OnMessageSend" FunctionName="onMessageSendHandler" SendMode="SoftBlock"/>
```

`SoftBlock` is the supported target mode for this repo today. Microsoft documents three Smart Alerts send modes: prompt user, soft block, and block. With soft block, Outlook alerts the user when the item does not meet add-in conditions, but if the add-in is unavailable the item can be sent. `Block` is stricter when the add-in fails or cannot connect, but deployment and marketplace rules differ.

Kaypoh policy mapping:

- `allow`: call `allowEvent: true`.
- `warn`: call `allowEvent: false` with `sendModeOverride=promptUser` when available.
- `approval_required` or `rewrite_required`: soft-block the send attempt and route to the taskpane.
- `block`, degraded coverage, malformed response, or backend error: hard-block the current send attempt when the event handler is running.

## Admin Deployment

- Render `manifest.xml` at build time with `scripts/render_outlook_manifest.py`.
- Validate rendered manifests with `scripts/validate_outlook_manifest.py` before deployment.
- Deploy through Microsoft 365 admin-managed deployment for production pilots.
- Assign to scoped pilot groups before tenant-wide rollout.
- Configure backend auth or local pairing token; the taskpane stores endpoint and local token in Office runtime storage or localStorage fallback.
- Keep add-in runtime pages and backend routes on origins allowed by tenant security policy.

## Fallback Behavior

- Backend unavailable: current handler blocks the send attempt with "Kaypoh local review is unavailable" when the handler runs.
- Degraded review: current handler blocks because launch-event review uses `degraded_policy="block_send"`.
- Warn decisions: current handler uses `sendModeOverride=promptUser` where Office supports runtime overrides.
- Rewrite or approval-required decisions: current handler soft-blocks and asks the user to open Kaypoh Review.
- Block decisions: current handler hard-blocks the current send attempt.
- Add-in unavailable before Outlook can run it: `SoftBlock` follows Outlook platform behavior, so this is not a fail-closed enforcement path.
- Taskpane review uses `degraded_policy="warn"` and is user-triggered; Smart Alerts send handling is the enforcement path.

## Known Client Limitations

- Manifest version overrides request Mailbox requirement set 1.15; Smart Alerts minimum support starts at Mailbox 1.12 in Microsoft docs.
- Outlook client, Exchange, offline, Work Offline, item-switching, and Simple MAPI behavior vary by platform and version.
- Event handlers should stay short-running; Microsoft documents user prompts after long-running processing and timeout behavior around five minutes.
- Only one `OnMessageSend` event can be declared per add-in manifest.
- Smart Alerts dialog text has platform limits; use concise `errorMessage` text and route detailed remediation to the taskpane.
- Current code does not inspect attachments, subject, recipient domains, sensitivity labels, or external destination yet.

Security model:

- Production deployment should use Microsoft 365 admin-managed deployment.
- Add-in origin must be HTTPS and controlled by the deployer.
- Backend calls must use tenant auth or local pairing token.
- Message body, subject, recipients, attachments, auth headers, and policy responses must not be stored in local storage, extension storage, or console logs.
- Outlook client support depends on Microsoft requirement sets and Smart Alerts platform behavior.

References:

- Microsoft Smart Alerts `OnMessageSend` docs: <https://learn.microsoft.com/en-us/office/dev/add-ins/outlook/onmessagesend-onappointmentsend-events>
- Microsoft event-based activation docs: <https://learn.microsoft.com/en-us/office/dev/add-ins/develop/event-based-activation>
