# Known Limitations

- Junas is not legal advice, external counsel review, or a procurement-grade legal evaluation.
- Native `.msg` and `7z` files degrade to fail-open best-effort review unless `JUNAS_DOCUMENT_FAIL_CLOSED=1` is set; convert or extract them with a trusted upstream tool for full coverage.
- PDF signatures, XFA, AcroForm fields, annotations, embedded files, and URI actions are surfaced for review; cryptographic signature validation is not performed.
- EML attachments and forwarded messages, DOCX comments/track-changes, XLSX hidden sheets/pivot caches, PPTX notes, and ZIP/TAR members are scanned with bounded recursive traversal.
- Macro-enabled Office files degrade to fail-open best-effort review unless `JUNAS_DOCUMENT_FAIL_CLOSED=1` is set.
- Image OCR is optional. Without OCR, embedded images are mapped and reported, but image text is not reviewed; standalone images return degraded fail-open responses.
- Remote public evidence and LLM layers are disabled by default and require explicit opt-in.
- SAML is not parsed directly. Use an identity-aware proxy or IdP bridge that emits signed JWTs.
- Windows desktop packaging is not shipped by default in this repo.
- Local browser/Office pairing requires the desktop process or an admin flow to approve the first-connect code.
- Office adapters depend on Microsoft 365/Office.js platform support, tenant admin assignment, client version, add-in runtime availability, requirement sets, CORS, and well-known URI handling. Outlook Smart Alerts `SoftBlock` is not fail-closed when Outlook cannot run the add-in, and the Word taskpane is user-triggered review rather than send/share enforcement.
- Browser adapters depend on Chrome/Edge MV3 behavior, managed profile policy, host permissions, DOM selectors, target editor structure, CSP, frames, shadow DOM, and submit flow. They do not cover mobile apps, native apps, unmanaged browsers, unsupported sites, custom editors that hide text from content scripts, or UI changes that break selector discovery.
- Office and browser adapters must not be described as universal capture, universal DLP, full-browser DLP, or guaranteed tenant-wide enforcement. They are workflow activation layers that call the backend when the vendor platform exposes the relevant event or editable surface.
- No public MNPI text-detection benchmark comparable to TAB or ai4privacy was
  identified in the 2026-07-01 source review. MNPI recall is measured against
  internal expert-labelled/project-owner-reviewed fixtures, with provenance in
  `test/fixtures/legal-corpus-reviewed-candidates/mnpi_conjunctive_label_provenance.json`.
  Strict `conjunctive_mnpi` span placement includes detector reconciliation and
  is not an independent public MNPI benchmark.
- The current strict layer-attribution report leaves 360 labels in the residual
  LLM-tier slice: 336 `needs_review` and 24 `true_inference_miss`, 1.55% of
  the 23,170 ideal misses. This is the capped-severity, human-adjudicated,
  server-only boundary for `audit_grade`, not a deterministic-layer target.
- This is the market gap Junas targets: MNPI review is conjunctive over
  materiality, non-public status, issuer/security context, and possession or
  disclosure context, while public PII corpora benchmark direct span extraction.
- Subject erasure deletes reversible mappings and writes journal tombstones; logs, SIEM, backups, legal-hold archives, and any immutable external stores require separate operator controls.
- Accuracy docs are internal benchmark disclosures unless explicitly promoted with human-reviewed corpus locks.
