# Operator FAQ

Checked on 2026-07-02 against official Microsoft, Google, and Slack DLP docs.

## Why Does Junas Complement DLP?

Junas is a pre-send review, safe rewrite, approval, and audit-evidence layer for specific workflows. DLP platforms remain the enterprise control plane for broad policy enforcement across SaaS, endpoint, storage, network, identity, and administrative reporting surfaces.

Use Junas where a user, adapter, DMS hook, or API client can ask for a policy decision before an email, GenAI prompt, document upload, or workflow completion proceeds. Use DLP for organization-wide discovery, classification, blocking, alerting, endpoint controls, and cross-application policy.

## Microsoft Purview DLP

Microsoft Purview DLP covers broad Microsoft and endpoint locations through DLP policies, including Enterprise applications and devices, Microsoft 365 services, Office apps, supported Windows/macOS devices, non-Microsoft cloud apps, on-premises repositories, and Inline web traffic.

Source: [Microsoft Purview DLP](https://learn.microsoft.com/en-us/purview/dlp-learn-about-dlp).

How Junas fits: keep Purview as the Microsoft 365 and endpoint enforcement layer. Add Junas when the organization needs workflow-specific pre-send review, deterministic finding details, safe rewrite actions, reviewer approval, and audit evidence before the user reaches the DLP enforcement point.

## Google Workspace DLP

Google Workspace DLP lets admins define DLP rules that scan content, apply to My Drive and Shared drives, trigger incidents, and take actions such as alerts, warnings, and sharing blocks. Google also documents Gmail, Drive, and Chat DLP surfaces.

Source: [Google Workspace DLP](https://knowledge.workspace.google.com/admin/security/about-dlp).

How Junas fits: keep Workspace DLP as the Workspace file/chat sharing control. Add Junas for pre-submit review of prompts, external-email copy, DMS uploads, and direct API workflows that need policy reasons, rewrite, approval, and audit evidence before content enters Workspace sharing flows.

## Slack DLP

Slack DLP scans messages, text-based files, and canvases for admin-defined rule violations, with DLP dashboard alerts, member warnings, and hide/tombstone actions. Slack also documents unsupported content types such as non-text files, some workflow data, externally hosted files, and files over its documented size limit.

Source: [Slack DLP](https://slack.com/help/articles/12914005852819-Slack-data-loss-prevention).

How Junas fits: keep Slack DLP as the Slack-native content control. Junas has no Slack adapter in this repo today; use direct API only for customer-built Slack-like workflows and mark Slack integration notes as research-only until implemented.

## Endpoint Controls

Endpoint controls such as MDM, EDR, USB policy, clipboard governance, browser management, screen capture control, and file-system policy remain outside Junas. The local daemon and desktop watcher are local fallback surfaces, not endpoint enforcement.

Use [`docs/product/non-goals.md`](../product/non-goals.md), [`docs/known-limitations.md`](../known-limitations.md), and [`docs/security/adapter-threat-model.md`](../security/adapter-threat-model.md) when documenting this boundary.

## CASB And SaaS Session Controls

CASB, cloud-app discovery, app sanctioning, SaaS session control, and cross-application policy remain separate control planes. Junas does not discover unmanaged SaaS use, broker sessions, classify stored SaaS repositories, or replace tenant-wide cloud-app governance.

How Junas fits: keep CASB and SaaS security controls active for discovery, sanctioning, access policy, and session enforcement. Add Junas only where a supported workflow can call `/review` before content is sent, pasted, uploaded, or approved, then feed privacy-safe metadata into existing DLP/SIEM programs.

## Operating Pattern

1. Keep existing DLP, endpoint, IdP, CASB, SIEM, and retention controls active.
2. Pick one Junas workflow adapter or direct API path for the pilot.
3. Configure tenant auth, policy profile, no-body logs, SIEM export, retention manifest, and audit-pack export.
4. Route the workflow through `/review`, then apply `policy_decision`, safe rewrite, approval, or hold actions before completion.
5. Feed Junas metadata into DLP/SIEM programs as hashes, counts, policy ids, decisions, actions, and request ids only.

Do not disable existing DLP because Junas is installed. Do not use Junas as the sole exfiltration control. Do not describe Office, browser, desktop, or future Slack surfaces as universal capture.
