# Product Non-goals

Junas is a pre-send review, safe rewrite, and audit-evidence layer. The following systems remain separate control planes.

| Area | Non-goal | Junas boundary |
|---|---|---|
| Enterprise DLP | Junas does not replace DLP policy, network inspection, endpoint discovery, SaaS storage scanning, or enterprise data classification. | Junas reviews explicit workflow submissions and can feed decisions/evidence into DLP-led programs. |
| Legal advice | Junas does not provide legal advice, privilege calls, matter strategy, or external counsel review. | Junas surfaces findings, policy reasons, and reviewer workflow evidence for qualified reviewers. |
| eDiscovery | Junas does not replace legal hold, collection, processing, review platforms, production, or chain-of-custody systems. | Junas can retain audit evidence about pre-send review decisions when configured. |
| Endpoint control | Junas does not replace device management, USB controls, clipboard governance, screen capture controls, file-system policy, or EDR. | Junas desktop features are local fallback surfaces, not enterprise endpoint enforcement. |
| CASB | Junas does not replace cloud-app discovery, sanctioning, session control, or cross-SaaS activity policy. | Junas browser/DMS/API integrations target specific workflows and should coexist with CASB controls. |
| IdP policy enforcement | Junas does not replace SSO, MFA, conditional access, group policy, or identity lifecycle management. | Junas consumes tenant/auth context from trusted identity infrastructure and rejects caller-supplied tenant authority. |

These non-goals prevent product claims from expanding beyond verified review workflows. Roadmap work should add deployment evidence, adapter QA, and policy-contract coverage before promoting any surface maturity.
