# Known limitations

- Detection is best effort. `SAFE` means no configured signal was detected, not that all personal data or MNPI is absent.
- The internal fixture locks are narrow regression checks. Historical external TAB and ai4privacy results show substantial recall gaps; see [evaluation methodology](../BENCHMARKS.md).
- No public MNPI text-detection benchmark was identified in the recorded provenance review. Current MNPI evaluation uses internal expert-labelled/project-owner-reviewed fixtures. Strict `conjunctive_mnpi` span placement includes detector reconciliation; these labels are not independent ground truth.
- The internal matcher compares rule/text expectations rather than exact occurrences. Unexpected predictions may be missing annotations rather than false positives.
- TAB and ai4privacy overlap metrics have their own annotation/matching conventions. Aggregate reports spanning training, development and test data must not be presented as held-out accuracy after tuning on them.
- Rule-based PII/MNPI scores are not calibrated probabilities. Statutory citations provide explanatory context, not legal conclusions.
- Native `.msg`, `7z`, macro-enabled Office files and partially readable containers have incomplete support. The default pipeline rejects unsupported extraction. Best-effort mode must retain degraded metadata.
- OCR is optional and text-corpus scores do not measure OCR accuracy. Small glyphs, layouts and ambiguous identifier prefixes remain difficult. The preserved OCR regression fixture remains in `test/fixtures/ocr/`.
- Native PDF signatures are not cryptographically validated. Embedded content, notes, forms and archives use bounded traversal.
- Optional NER, retrieval and LLM configurations change what is measured. Record configuration and evaluate them separately; strict mode does not call retrieval/LLM helpers.
- No product enforcement, approvals, audit journal, rewriting, re-identification, tenant authentication or hosted service is provided by this research tree.
