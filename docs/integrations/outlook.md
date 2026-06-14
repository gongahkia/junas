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
3. `launchevent.js` reads the message body, subject, recipients, and attachment count.
4. The handler calls `/review` with `document_type="email"`, `review_profile="strict"`, `degraded_policy="block_send"`, `surface="outlook"`, and `workflow="email_send"`.
5. The handler calls `event.completed({allowEvent: true})` only when review completes without degraded coverage, blocking outcome, or findings above the current threshold.
6. When blocked, the user opens the Kaypoh taskpane to review or redact before retrying send.

The reviewed text prepends `Subject: ...` to the body so subject text is scanned. Recipient metadata is reduced to domain list and count. Attachment metadata is reduced to count; filenames are not sent.

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
- Configure send-hook timeout in the taskpane. The default is 4000 ms and allowed range is 1000-8000 ms.
- Keep add-in runtime pages and backend routes on origins allowed by tenant security policy.

## Tenant Deployment Guide

Use Microsoft 365 centralized deployment for hosted Outlook pilots.

Required admin access:

- Exchange admin in the tenant is the documented role required for centralized deployment.
- If upload or app registration is blocked, grant the deploying Exchange admin the Application Administrator role or enable app registrations in Microsoft Entra ID.
- Global Administrator has full add-in lifecycle access, but treat it as break-glass or setup-only because it is highly privileged.

Tenant prerequisites:

- Users must have Exchange Online and active Exchange Online mailboxes.
- The subscription directory must be in Microsoft Entra ID or federated to it.
- Centralized deployment does not cover on-premises Exchange mailboxes.
- `AppsForOfficeEnabled` must not be false for the organization.

Deployment steps:

1. Render and validate the target manifest with the production add-in origin.
2. Sign in to the Microsoft 365 admin center.
3. Go to `Settings > Integrated apps`, select `Add-ins`, then select `Deploy Add-in`.
4. Upload the rendered manifest or provide its URL.
5. Start with `Just me` for admin smoke testing.
6. Move to `Specific users/groups` for pilot rollout, then broaden only after Smart Alerts QA passes.
7. Use `Deploy`, ask testers to restart Outlook, and allow up to 24 hours for new deployment visibility and up to 72 hours for updates.

Group assignment:

- Prefer top-level Microsoft Entra groups over individual users for pilot and production rollout.
- Supported group targets include Microsoft 365 Groups, distribution lists, dynamic groups, and security groups.
- Do not rely on nested group membership for access; centralized deployment targets users in top-level groups.
- Maintain separate pilot, production, and break-glass exclusion groups so rollback does not require manifest changes.
- To change access after deployment, use `Settings > Integrated apps`, select the add-in, open `Users`, update assigned users/groups, then re-test propagation.

## Send Hook Timeout

The launch-event path uses a shorter timeout than normal API calls because Outlook Smart Alerts runs inside the user's send action. Long waits make the send flow feel broken and can trigger Outlook long-running add-in prompts. The default send-hook timeout is 4000 ms, clamped between 1000 ms and 8000 ms via `kaypoh.sendHookTimeoutMs`.

Normal backend and batch workflows may use longer API timeouts because they are not blocking a compose-window send event.

## Event Runtime Bundle

`commands.html` loads Office.js and one event runtime file: `launchevent.js`. Keep Smart Alerts code bundled in that single file. Do not add ES module `import` or `export` statements to the event handler runtime; event-based activation must run in the Office event runtime without a separate module graph.

Shared Outlook taskpane code can live in `taskpane.js`, but `launchevent.js` must remain self-contained for send-hook activation.

## CORS And Well-Known URI Checklist

Microsoft requires extra configuration when event-based activation code uses CORS or SSO from the event runtime. Before a hosted Outlook pilot:

- Serve taskpane, commands page, and `launchevent.js` from the same HTTPS add-in origin used in the rendered manifest.
- Serve `https://<add-in-origin>/.well-known/microsoft-officeaddins-allowed.json` without auth or redirects.
- Include the exact rendered `JSRuntime.Url` in the well-known JSON:

```json
{
  "allowed": [
    "https://outlook-addin.example.com/launchevent.js"
  ]
}
```

- Keep the well-known file `Content-Type` as `application/json`.
- Configure backend CORS to allow the add-in origin and the headers used by the event runtime: `Content-Type`, `X-Kaypoh-Local-Token`, and `Authorization` when tenant auth is enabled.
- Support `OPTIONS` preflight for `/review` and local pairing routes used by Outlook.
- Confirm the rendered manifest `JSRuntime.Url`, CORS allowlist, and well-known `allowed` entry match exactly after staging/production templating.
- Do not allow wildcard origins for production tenant deployments.

## Fallback Behavior

- Backend unavailable: current handler blocks the send attempt with "Kaypoh local review is unavailable" when the handler runs.
- Degraded review: current handler blocks because launch-event review uses `degraded_policy="block_send"`.
- Warn decisions: current handler uses `sendModeOverride=promptUser` where Office supports runtime overrides.
- Rewrite or approval-required decisions: current handler soft-blocks and asks the user to open Kaypoh Review.
- Block decisions: current handler hard-blocks the current send attempt.
- Add-in unavailable before Outlook can run it: `SoftBlock` follows Outlook platform behavior, so this is not a fail-closed enforcement path.
- Taskpane review uses `degraded_policy="warn"` and is user-triggered; Smart Alerts send handling is the enforcement path.

Smart Alert message fixtures for allow, warn, block, and approval-required states live in `test/fixtures/outlook_smart_alert_messages.json`.

## Failure-Mode Table

| Failure | Current handling | Operator note |
|---|---|---|
| Add-in unavailable before event runs | Outlook applies `SoftBlock` platform behavior. | Not fail-closed; validate client support and monitor add-in health. |
| Backend timeout or unavailable | Handler catch path blocks current send attempt. | Default send-hook timeout is 4000 ms; route user to taskpane/pairing check. |
| Offline mode / Work Offline | Event or backend call may not complete. | Treat as unsupported for controlled send enforcement unless tenant accepts soft-block fallback. |
| Malformed response | Mapping falls back to soft-block unless a valid allow decision is present. | Add telemetry once Outlook adapter telemetry exists. |
| Auth failure | Non-2xx `/review` response enters backend-unavailable catch path and blocks current send. | User should re-pair local token or fix tenant API/JWT auth. |
| Degraded document extraction | `degraded_policy="block_send"` plus degraded modes hard-block current send. | User should open Kaypoh Review or retry after extraction issue is resolved. |

## Known Client Limitations

- Manifest version overrides request Mailbox requirement set 1.15; Smart Alerts minimum support starts at Mailbox 1.12 in Microsoft docs.
- Outlook client, Exchange, offline, Work Offline, item-switching, and Simple MAPI behavior vary by platform and version.
- Event handlers should stay short-running; Microsoft documents user prompts after long-running processing and timeout behavior around five minutes.
- Only one `OnMessageSend` event can be declared per add-in manifest.
- Smart Alerts dialog text has platform limits; use concise `errorMessage` text and route detailed remediation to the taskpane.
- Current code does not inspect attachment content, sensitivity labels, or external destination yet.

Security model:

- Production deployment should use Microsoft 365 admin-managed deployment.
- Add-in origin must be HTTPS and controlled by the deployer.
- Backend calls must use tenant auth or local pairing token.
- Message body, subject, recipients, attachments, auth headers, and policy responses must not be stored in local storage, extension storage, or console logs.
- Outlook client support depends on Microsoft requirement sets and Smart Alerts platform behavior.

References:

- Microsoft Smart Alerts `OnMessageSend` docs: <https://learn.microsoft.com/en-us/office/dev/add-ins/outlook/onmessagesend-onappointmentsend-events>
- Microsoft event-based activation docs: <https://learn.microsoft.com/en-us/office/dev/add-ins/develop/event-based-activation>
- Microsoft centralized deployment requirements: <https://learn.microsoft.com/en-us/microsoft-365/admin/manage/centralized-deployment-of-add-ins>
- Microsoft 365 admin center add-in deployment: <https://learn.microsoft.com/en-us/microsoft-365/admin/manage/manage-deployment-of-add-ins>
- Microsoft centralized deployment FAQ: <https://learn.microsoft.com/en-us/microsoft-365/admin/manage/centralized-deployment-faq>
