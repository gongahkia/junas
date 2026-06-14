# Product Non-goals

Kaypoh is a pre-send review, safe rewrite, and audit-evidence layer. The following systems remain separate control planes.

| Area | Non-goal | Kaypoh boundary |
|---|---|---|
| Enterprise DLP | Kaypoh does not replace DLP policy, network inspection, endpoint discovery, SaaS storage scanning, or enterprise data classification. | Kaypoh reviews explicit workflow submissions and can feed decisions/evidence into DLP-led programs. |
| Legal advice | Kaypoh does not provide legal advice, privilege calls, matter strategy, or external counsel review. | Kaypoh surfaces findings, policy reasons, and reviewer workflow evidence for qualified reviewers. |
| eDiscovery | Kaypoh does not replace legal hold, collection, processing, review platforms, production, or chain-of-custody systems. | Kaypoh can retain audit evidence about pre-send review decisions when configured. |
| Endpoint control | Kaypoh does not replace device management, USB controls, clipboard governance, screen capture controls, file-system policy, or EDR. | Kaypoh desktop features are local fallback surfaces, not enterprise endpoint enforcement. |
| CASB | Kaypoh does not replace cloud-app discovery, sanctioning, session control, or cross-SaaS activity policy. | Kaypoh browser/DMS/API integrations target specific workflows and should coexist with CASB controls. |
| IdP policy enforcement | Kaypoh does not replace SSO, MFA, conditional access, group policy, or identity lifecycle management. | Kaypoh consumes tenant/auth context from trusted identity infrastructure and rejects caller-supplied tenant authority. |

These non-goals prevent product claims from expanding beyond verified review workflows. Roadmap work should add deployment evidence, adapter QA, and policy-contract coverage before promoting any surface maturity.
