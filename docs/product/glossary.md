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

## Operational Differences

| Action | Use when | Output | Reidentification | Operational note |
|---|---|---|---|---|
| Pseudonymize | The caller needs stable placeholders and may need to restore original values later. | Text with deterministic typed placeholders plus mapping entries. | Reversible when the caller has the mapping or persisted document hash. | Does not approve sending by itself; policy decision still controls workflow. |
| Anonymize | The caller needs an irreversible working copy and does not need restoration. | Text with typed placeholders and no original values in the mapping response. | Not reversible through Kaypoh v2 output. | Reduces downstream exposure after accepted findings are transformed. |
| Redact | The caller needs opaque suppression and should not reveal entity classes in output text. | Text with opaque markers and redaction records without original matched text. | Not reversible. | Best for minimized sharing, not later reconstruction. |
| Safe rewrite | The user needs policy-approved wording before send, paste, upload, or share. | Rewritten text plus span-level replacement audit for allowed findings. | Not reversible unless the caller separately uses pseudonymization. | Applies only allowed actions and keeps skipped findings visible for review. |
| Reviewer approval | Risk needs authenticated human authorization instead of immediate transformation. | Journal event, pending approval state, reviewer role requirements, and later decision. | No content transformation. | Lets adapters retry or complete only after an authorized decision is recorded. |

Quick choice: use pseudonymize for reversible placeholders, anonymize for irreversible typed placeholders, redact for opaque removal, safe rewrite for sendable replacement wording, and reviewer approval for human signoff.
