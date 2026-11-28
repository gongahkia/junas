# Runtime assumptions

- The baseline is a local, deterministic PII/MNPI detector. It returns contextual states and evidence, without document risk scores or calibrated probabilities.
- The classifier returns findings and evidence; there is no send decision, approval workflow, redaction service or HTTP endpoint.
- Jurisdiction packs and defined-term/entity context affect classification. Context terms are supplied explicitly and are not persisted in sessions.
- Local spaCy NER is opt-in with `JUNAS_LOCAL_NER_FALLBACK=1` and requires the `ner` extra plus a model. It is not silently included in the baseline.
- Inputs are inline text or bounded UTF-8 text files. Native documents, images and OCR are outside current scope; retired formats/configuration are rejected.
- Retrieval and LLM helpers require `audit_grade` plus explicit configuration. Provider opt-ins and restrictions on raw-text transfer remain enforced.
- External masking benchmarks, internal regression labels and synthetic model references are distinct evidence sources. Historical OCR reports are archived. Neither synthetic agreement nor passing regression locks proves general accuracy.
