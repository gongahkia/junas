# Browser Enterprise Deployment

Checked on 2026-07-01 against official Chrome Enterprise and Microsoft Edge policy docs:

- Chrome `ExtensionInstallForcelist`: https://chromeenterprise.google/policies/extension-install-forcelist/
- Chrome `ExtensionSettings`: https://support.google.com/chrome/a/answer/9867568
- Edge `ExtensionInstallForcelist`: https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies/extensioninstallforcelist
- Edge `ExtensionSettings`: https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies/extensionsettings

This page covers managed Chrome/Edge pilots for `integrations/browser_extension/`.
It does not make Junas a universal browser DLP control.

## Required Inputs

- Published extension ID for Chrome Web Store, Edge Add-ons, or a signed self-hosted CRX.
- Update URL for the selected channel.
- Managed Chrome or Edge profile/device policy scope.
- Junas backend URL, auth mode, and local pairing or hosted-server token procedure.
- Manifest permission review from `docs/integrations/browser-extension.md`.
- QA evidence from `docs/integrations/genai-browser.md` before expanding support claims.

Use `./scripts/package_browser_extension.sh` for a ZIP artifact. Set
`JUNAS_CHROME_EXTENSION_KEY` only for enterprise-controlled CRX packaging where IT owns
the signing key. A developer-loaded unpacked extension is not production deployment evidence.

## Chrome Policy

For Chrome Web Store distribution, use the Chrome Web Store extension ID and the Chrome
Web Store update service:

```text
<chrome_web_store_extension_id>;https://clients2.google.com/service/update2/crx
```

For a self-hosted signed CRX, use an HTTPS update manifest XML URL controlled by the
customer:

```text
<self_hosted_extension_id>;https://extensions.example.com/junas/update.xml
```

Chrome `ExtensionSettings` can also force install an extension and declare update
behavior:

```json
{
  "<extension_id>": {
    "installation_mode": "force_installed",
    "update_url": "https://clients2.google.com/service/update2/crx",
    "override_update_url": true
  }
}
```

Chrome's `update_url` is required for `force_installed` and `normal_installed` in
`ExtensionSettings`. Chrome uses the configured URL for initial installation. For later
updates, Chrome uses the extension manifest update URL unless `override_update_url` is
true.

## Edge Policy

For Edge Add-ons distribution, use the Edge extension ID and Edge Add-ons update service:

```text
<edge_addons_extension_id>;https://edge.microsoft.com/extensionwebstorebase/v1/crx
```

For a self-hosted signed CRX, use an update manifest XML URL:

```text
<self_hosted_extension_id>;https://extensions.example.com/junas/update.xml
```

Edge `ExtensionInstallForcelist` values are extension IDs with an optional update URL
after a semicolon. The update URL is used for initial installation; later updates use
the extension manifest update URL unless `ExtensionSettings.override_update_url` is set.

```json
{
  "<extension_id>": {
    "installation_mode": "force_installed",
    "update_url": "https://edge.microsoft.com/extensionwebstorebase/v1/crx",
    "override_update_url": true
  }
}
```

Edge outside-store force install has platform limits. Windows devices outside Microsoft
Active Directory or Microsoft Entra ID are limited to Edge Add-ons. macOS outside-store
force install requires MDM or MCX/domain management.

## Verification

- `chrome://policy` or `edge://policy` shows `ExtensionInstallForcelist` and any
  `ExtensionSettings` JSON without parse errors.
- `chrome://extensions` or `edge://extensions` shows the Junas extension as managed,
  with the expected extension ID and version.
- The extension options health check reports `server healthy` or the expected local
  daemon state.
- The managed profile reaches only the documented target hosts: `chatgpt.com`,
  `claude.ai`, and `gemini.google.com`.
- The published manifest does not request `activeTab`, `tabs`, `scripting`,
  `webRequest`, `cookies`, `history`, `downloads`, `identity`, or `<all_urls>`.
- Privacy checks pass: no raw prompt text in extension storage, console logs, or
  telemetry.

Do not treat a force-installed extension as fail-closed enforcement. If selectors,
content-script injection, CSP, service-worker lifecycle, auth, or backend availability
breaks, the adapter must follow `docs/integrations/genai-browser.md` failure behavior.
