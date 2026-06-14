# Product Glossary

| Term | Definition |
|---|---|
| PII | Personally identifiable information: data that identifies, relates to, describes, or can reasonably be linked to a person, including direct identifiers and high-risk combinations of quasi-identifiers. |
| Personal data | Jurisdiction-specific privacy term for information about an identified or identifiable person. Kaypoh uses the term when mapping findings to statutes such as GDPR, UK GDPR, PDPA, or other local privacy laws. |
| MNPI | Material non-public information: information that is not public and could reasonably matter to investors, counterparties, regulators, or market participants if disclosed or traded on. |
| Pre-send review | A review that happens before a user sends, submits, uploads, shares, or pastes content into an external or higher-risk workflow. |
| Safe rewrite | A policy-approved transformation that removes, replaces, delays, or reframes risky spans while preserving review evidence and avoiding reversible mappings unless pseudonymization is explicitly requested. |
| Redaction | Irreversible replacement of sensitive content with opaque markers so the response does not expose the original matched text outside ordinary review findings. |
| Pseudonymization | Reversible deterministic replacement of sensitive values with placeholders plus a mapping that can later reidentify content when the caller is authorized. |
| Anonymization | Irreversible placeholder-only transformation that does not retain a mapping for reidentification. |
| Audit evidence | Privacy-safe evidence about a review, such as hashes, counts, finding ids, policy id/version, decisions, actions, timestamps, and reviewer rationale. |
| Adapter | Optional workflow surface that collects context, calls the backend review contract, and displays or applies policy decisions, such as Outlook, browser, Word, desktop, or DMS integrations. |
| Surface | The user or system environment where review is triggered, such as `outlook`, `browser_genai`, `dms`, `desktop`, `word`, or `api`. |
