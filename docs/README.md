# Docs Folder

This folder contains operator, developer, and product documentation. Product docs under `product/` are normative for roadmap decisions: roadmap, adapter maturity, and integration claims should match those documents before implementation starts.

- `running.md`: launch and operational commands
- `install.md`: local, extension, Office, and server install flow
- `admin-security.md`: identity, tenant, key, SIEM, and local pairing controls
- `threat-model.md`: data flow, trust boundaries, threats, controls, and residual risk
- `known-limitations.md`: explicit unsupported or limited surfaces
- `llm-governance.md`: LLM promotion, privacy eval, and invariant gates
- `schema.md`: API and artifact contracts
- `architecture.md`: pipeline architecture overview
- `accuracy.md`: generated per-detector recall/precision disclosure
- `deployment-hardening.md`: production filesystem, transport, secrets, Kubernetes, and SIEM guidance
- `mapping-store-hardening.md`: encryption, retention, subject erasure, and deployment controls for persisted mappings
- `assumption.md`: implementation assumptions and invariants
- `product/positioning.md`: canonical product positioning, target users, non-goals, and DLP boundary
- `product/workflows.md`: daily workflow maps for Outlook, GenAI browser, DMS, API, reviewer, and auditor paths
- `product/personas.md`: jobs-to-be-done for end users, legal reviewers, compliance admins, security engineers, and platform integrators
- `product/non-goals.md`: explicit control planes Kaypoh does not replace
- `product/research-basis.md`: external deployment/security research basis for adapter and DLP claims
- `product/glossary.md`: product vocabulary for review, rewrite, audit evidence, adapters, and surfaces
- `product/review-examples.md`: same-contract `/review` examples for GenAI, email, legal memo, DMS, and Slack-style messages
- `api/`: generated Postman collection, cURL snippets, and Python client integration notes
- `json/`: example training corpus batches
