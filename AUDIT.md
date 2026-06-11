 What I’d do next, in order:

  1. Refresh corpus/eval docs. Current fixtures show 1428 candidate
     docs/labels, while docs still mention old Stage A numbers and stale
     miss concentration. Regenerate docs/miss_concentration.md, docs/
     candidate_corpus_status.md, and architecture corpus text.

  2. Product expansion: audit-grade evidence, not more classifier stack.
     Add ticker to results-calendar lookup for blackout windows, issuer-
     size/materiality lookup providers, and HK “not generally known”
     source thresholds.

  3. Harder ingest reality: .msg/7z still fail closed, OCR optional, and
     broad free-form address parsing is intentionally partial. Next
     useful work is more hostile document-container corpus: Outlook
     exports, PDFs with annotations/forms, weird DOCX comments/track-
        changes, XLSX hidden sheets/pivot caches.

  4. LLM governance path. Distillation exists, but no promoted local
     adapter/baseline. Add model-card style docs, privacy eval, and
          invariant gates. This aligns with EU GPAI obligations now in
     application and enforceable from 2026-08-02 for new providers.
     Source: EU AI Act GPAI timeline/guidelines.
     (digital-strategy.ec.europa.eu
                                          (https://digital-strategy.ec.europa.eu/en/policies/guidelines-gpai-providers))

                                                               5. Regulatory-aligned detector expansion:

  - Pseudonymisation docs should keep stressing “still personal data if
     linkable”; EDPB says this directly. (edpb.europa.eu
    (https://www.edpb.europa.eu/news/news/2025/edpb-adopts-pseudonymisation-guidelines-and-paves-way-improve-cooperation_en))

  - AU children online privacy code work is live in 2026; deepen
    minor/online-activity/age-assurance detection. (oaic.gov.au
    (https://www.oaic.gov.au/privacy/privacy-registers/privacy-codes/childrens-online-privacy-code))

  - SEC cyber incident materiality remains a strong MNPI source area.
    (sec.gov
    (https://www.sec.gov/newsroom/speeches-statements/gerding-cybersecurity-incidents-05212024))

  - India DPDP Rules 2025 add concrete security/breach/child-data hooks
    worth corpus coverage. (meity.gov.in
    (https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf))

  - SG PDPC opened GenAI personal-data guideline consultation on
    2026-06-02; mirror that in LLM/privacy-ledger docs. (pdpc.gov.sg
    (https://www.pdpc.gov.sg/organisations/regulations-decisions/regulatory-guidance/public-consultation-on-the-proposed-advisory-guidelines-on-use-of-personal-data-in-generative-ai))

  Bottom line: runtime looks solid; repo truth/docs and broad lint are
  the main unfinished polish, then expand via defensibility/corpus
  realism rather than adding new ML layers.
