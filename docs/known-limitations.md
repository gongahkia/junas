# Known Limitations

- Kaypoh is not legal advice, external counsel review, or a procurement-grade legal evaluation.
- Native `.msg` and `7z` files degrade to fail-open best-effort review unless `KAYPOH_DOCUMENT_FAIL_CLOSED=1` is set; convert or extract them with a trusted upstream tool for full coverage.
- PDF signatures, XFA, AcroForm fields, annotations, embedded files, and URI actions are surfaced for review; cryptographic signature validation is not performed.
- EML attachments and forwarded messages, DOCX comments/track-changes, XLSX hidden sheets/pivot caches, PPTX notes, and ZIP/TAR members are scanned with bounded recursive traversal.
- Macro-enabled Office files degrade to fail-open best-effort review unless `KAYPOH_DOCUMENT_FAIL_CLOSED=1` is set.
- Image OCR is optional. Without OCR, embedded images are mapped and reported, but image text is not reviewed; standalone images return degraded fail-open responses.
- Remote public evidence and LLM layers are disabled by default and require explicit opt-in.
- SAML is not parsed directly. Use an identity-aware proxy or IdP bridge that emits signed JWTs.
- Windows desktop packaging is not shipped by default in this repo.
- Local browser/Office pairing requires the desktop process or an admin flow to approve the first-connect code.
- Standalone manual redaction has lower expected adoption than in-workflow pre-send capture because users must leave the send/share workflow and remember to run a separate tool.
- Subject erasure deletes reversible mappings and writes journal tombstones; immutable logs, SIEM, backups, and legal-hold archives require separate operator controls.
- Accuracy docs are internal benchmark disclosures unless explicitly promoted with human-reviewed corpus locks.
