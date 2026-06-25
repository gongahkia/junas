# Product Research Basis

Checked on 2026-06-14. Use this page to ground product claims in official vendor/security documentation, not inferred adapter coverage.

## Deployment Research Summary

| Area | Source | Product implication |
|---|---|---|
| Microsoft 365 add-in deployment | [Deploy Office Add-ins in the Microsoft 365 admin center](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/manage-deployment-of-add-ins?view=o365-worldwide) | Outlook and Word adapters need admin-managed deployment docs, phased rollout guidance, and manifest upload/URL packaging. |
| Microsoft 365 deployment requirements | [Requirements to use centralized deployment for Office Add-ins](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/centralized-deployment-of-add-ins?view=o365-worldwide) | Tenant deployment docs need admin-role prerequisites and compatibility checks before claiming supported rollout. |
| Outlook Smart Alerts | [Handle OnMessageSend and OnAppointmentSend events in your Outlook add-in with Smart Alerts](https://learn.microsoft.com/en-us/office/dev/add-ins/outlook/onmessagesend-onappointmentsend-events) | Outlook support should center on `OnMessageSend`, requirement-set checks, supported-client notes, and explicit send-mode behavior. |
| Office event-based activation | [Activate add-ins with events](https://learn.microsoft.com/en-us/office/dev/add-ins/develop/event-based-activation) | Hard-block Smart Alerts require admin deployment; Marketplace paths are limited to prompt-user or soft-block send modes. |
| Chrome enterprise extension deployment | [Chrome ExtensionInstallForcelist policy](https://chromeenterprise.google/policies/extension-install-forcelist/) | Browser adapter rollout needs managed-profile/device assumptions, extension id/update URL packaging, and no claim of unmanaged universal coverage. |
| Edge enterprise extension deployment | [Microsoft Edge ExtensionInstallForcelist policy](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies/extensioninstallforcelist) | Edge rollout needs policy examples, managed-device limits, implicit permission review, and update URL handling. |
| OWASP API risks | [OWASP API Security Top 10 2023 table of contents](https://owasp.org/API-Security/editions/2023/en/0x00-toc/) | Backend roadmap needs object-level authorization, authentication, object-property authorization, resource caps, function authorization, SSRF, misconfiguration, inventory, and unsafe-consumption coverage. |
| OWASP CSRF controls | [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) | Local daemon/browser-origin calls need origin validation, non-simple JSON requests, custom headers, CORS preflight behavior, and token checks. |
| Microsoft Purview DLP | [Learn about data loss prevention](https://learn.microsoft.com/en-us/purview/dlp-learn-about-dlp) | Kaypoh should be positioned as complementary to Purview DLP, which covers broader locations, transmission methods, user activities, and deep content analysis. |
| Google Workspace DLP | [About DLP](https://knowledge.workspace.google.com/admin/security/about-dlp) | Google Workspace notes should treat DLP as the platform control for files and sharing rules; Kaypoh can provide pre-send review evidence before or beside those controls. |
| Slack DLP | [Slack data loss prevention](https://slack.com/help/articles/12914005852819-Slack-data-loss-prevention) | Slack integration remains research-only until a real integration exists; Slack's native DLP scans messages, files, and canvases under admin-defined rules. |

## Product Constraints From Research

- Admin deployment is a requirement for production Outlook/Office pilots; user-side sideloading is a dev/test path.
- Smart Alerts support depends on Outlook client capability, requirement sets, manifest configuration, and send-mode policy.
- Browser extensions can be force-installed in managed Chrome/Edge environments, but this does not imply coverage for mobile apps, native apps, unmanaged profiles, or every DOM change.
- Backend API security work must be treated as product-critical because every adapter relies on the same trust boundary.
- Local browser-to-daemon flows must not rely on cookies alone; they need explicit origin and custom-token defenses.
- Existing DLP platforms remain primary enterprise enforcement planes; Kaypoh provides workflow-specific review, rewrite, approval, and audit evidence.
