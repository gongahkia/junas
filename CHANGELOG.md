# Changelog

## Unreleased — classifier research scope

- Remove browser/Office/DMS/desktop interfaces, HTTP services and client SDK, approval/send policy, redaction/mapping services, audit persistence, telemetry, hosting and desktop packaging.
- Retain the deterministic PII/MNPI engine, document parsing/OCR, jurisdiction packs, optional advisory experiments, labelled corpora and evaluation tooling.
- Expose a local Python pipeline and `junas classify` research command.
- Add a repeatable accuracy report command with existing regression gates and explicit external-data availability.
- Require Python 3.11 or newer. NER and OCR dependencies are optional extras.

Previous product releases and their implementation are available in Git history. This scope change does not claim improved detector accuracy.
