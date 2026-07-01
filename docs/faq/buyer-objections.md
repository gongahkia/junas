# Buyer Objections

Use this page in procurement, security, legal, and pilot-review conversations. Each
answer must point to committed evidence or a documented limitation. Do not turn roadmap
intent, screenshots, or demos into claims.

| Objection | What to say | Evidence to show | Must not claim |
|---|---|---|---|
| Accuracy proof | Junas has in-repo deterministic fixture evidence and policy-contract tests. Independent TAB and ai4privacy scores are not claimed until committed eval reports exist. | `docs/accuracy.md`, `docs/faq/procurement.md`, promoted corpus locks, precision/recall reports. | Coverage of every customer document, every jurisdiction, or independent benchmark performance not yet run. |
| Legal liability | Junas returns pre-send review, policy decisions, safe rewrite actions, and audit evidence. Customer counsel and policy owners remain responsible for legal interpretation and approval policy. | `docs/product/non-goals.md`, `docs/policy/decision-contract.md`, `docs/known-limitations.md`. | Legal advice, privileged legal opinion, or replacement for counsel review. |
| Data residency | Deterministic-only, local-only, hosted, and customer-managed modes can run without remote LLMs. Public evidence and remote LLM layers require explicit deployment gates. | `docs/deployment-local-only.md`, `docs/deployment-customer-managed.md`, `docs/deployment-managed-llm.md`, `docs/security/remote-llm-config.md`. | That all deployments are air-gapped, or that remote raw text is impossible when an operator explicitly enables it. |
| Admin deployment | Backend deployment, adapter packaging, Microsoft 365 assignment, browser enterprise policy, rollback, and pilot scope are separate control planes. | `docs/install.md`, `docs/integrations/adapter-packaging.md`, `docs/deployment-rollback.md`, `docs/integrations/outlook.md`, `docs/integrations/browser-enterprise-deployment.md`. | That installing the backend automatically deploys Office/browser adapters or covers all users. |
| User friction | Pilot value must be measured with activation, reviewed-send, accepted rewrite, blocked-send, audit-pack, and false-positive metrics. | `docs/product/value-metrics.md`, `docs/product/pilot-success-rubric.md`, `docs/deployment-pilot-rollout.md`. | That users will adopt standalone manual redaction without workflow evidence. |
| False positives | False positives are tracked through reviewer decisions, override taxonomy, support triage, and false-positive override rate. | `docs/policy/decision-taxonomy.md`, `docs/admin-console/false-positive-triage.md`, `docs/product/pilot-success-rubric.md`. | Zero false positives or no reviewer workload. |
| Existing DLP interoperability | Junas complements Microsoft Purview, Google Workspace DLP, Slack DLP, CASB, endpoint, IdP, SIEM, and retention controls. It focuses on workflow-specific pre-send review and audit evidence. | `docs/faq/operator.md`, `docs/product/non-goals.md`, `docs/security/adapter-threat-model.md`. | Replacement of DLP, endpoint control, CASB, IdP policy, eDiscovery, or native SaaS admin controls. |

## Required Prep Before Buyer Calls

- Open `docs/faq/procurement.md` and confirm the current promoted accuracy evidence.
- Open `docs/known-limitations.md` and confirm unsupported ingest, adapter, and deployment boundaries.
- Pick the intended deployment mode and adapter from `docs/deployment-pilot-rollout.md`.
- Prepare the rollback path from `docs/deployment-rollback.md`.
- Prepare the pilot success measures from `docs/product/pilot-success-rubric.md`.

## Claim Escalation

Escalate instead of answering from memory when a buyer asks for:

- independent benchmark scores not committed in this repo
- legal opinions or liability allocation
- data residency guarantees for a provider, region, or tenant contract
- support for a SaaS surface without implemented adapter source and tests
- claims that Junas replaces existing DLP, SIEM, endpoint, IdP, or eDiscovery controls
