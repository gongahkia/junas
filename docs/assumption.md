# Runtime assumptions

- The baseline is a local, deterministic PII/MNPI detector. Its scores are heuristic risk scores, not probabilities.
- The classifier returns findings and evidence; there is no send decision, approval workflow, redaction service or HTTP endpoint.
- Jurisdiction packs and defined-term/entity context affect classification. Context terms are supplied explicitly and are not persisted in sessions.
- Local spaCy NER is opt-in with `JUNAS_LOCAL_NER_FALLBACK=1` and requires the `ner` extra plus a model. It is not silently included in the baseline.
- Image OCR is separately configured. Without OCR, image content is not detected; unsupported/unreadable files fail closed by default.
- Retrieval and LLM helpers require `audit_grade` plus explicit configuration. Provider opt-ins and restrictions on raw-text transfer remain enforced.
- External benchmarks, internal regression labels and OCR fixtures are distinct evidence sources. Neither synthetic labels nor passing regression locks prove general accuracy.
