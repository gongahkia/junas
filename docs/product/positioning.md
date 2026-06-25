# Product Positioning

## Canonical Description

Junas provides pre-send review, safe rewrite, and audit evidence for GenAI prompts, email, and document sharing by routing text, documents, and workflow context through a deterministic FastAPI backend that detects personal data and MNPI risk, returns policy decisions, and supports redaction, pseudonymization, approval, hold, or audit export actions before content leaves a trusted boundary.

## Target Users

- End users who need a fast pre-send check before pasting prompts, emailing external recipients, or uploading matter documents.
- Legal reviewers who need finding context, override controls, and audit-ready rationale without searching raw user workspaces.
- Compliance admins who need policy profiles, adoption metrics, override patterns, and evidence exports.
- Security engineers who need tenant isolation, privacy-safe telemetry, SIEM events, and integration contracts.
- Platform integrators who need stable HTTP/OpenAPI contracts for DMS, gateway, browser, email, and internal workflow systems.

## Non-goals

- Junas does not replace legal advice or external counsel review.
- Junas does not replace enterprise DLP, CASB, endpoint control, eDiscovery, IdP policy enforcement, or matter-management systems.
- Junas does not claim universal capture across every email client, browser UI, mobile app, desktop app, or document repository.
- Junas does not train on customer text by default.
- Junas does not treat optional adapters as mandatory deployment dependencies.

## Why Junas Is Not a General DLP Suite

General DLP suites enforce broad data movement controls across endpoints, networks, cloud storage, SaaS apps, identities, and administrative policy planes. Junas is narrower: it reviews specific user workflows before send/share, returns deterministic findings and policy decisions, and records audit evidence for the workflow under review. Production deployments should integrate Junas with existing DLP, identity, SIEM, DMS, and retention controls rather than use Junas as their only data-loss control plane.
