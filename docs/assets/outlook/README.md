# Outlook Smart Alert Renderings

These images are rendered fixtures, not live Outlook screenshots. They are generated from `test/fixtures/outlook_smart_alert_messages.json` with:

```sh
uv run python scripts/render_outlook_smart_alert_screenshots.py
```

Files:

- `outlook-smart-alert-allow.png`: `allowEvent=true`; no Smart Alert dialog is shown.
- `outlook-smart-alert-warn.png`: prompt-user warning with "Send anyway" handling.
- `outlook-smart-alert-block.png`: hard block with the policy-block message.
- `outlook-smart-alert-approval_required.png`: soft block requiring reviewer approval.

Use these only as faithful renderings of the current fixture strings. Validate real Smart Alert UI on each Outlook client family before making deployment claims.
