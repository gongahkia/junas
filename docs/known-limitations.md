# Known limitations

- Detection is best effort. `SAFE` means no configured signal was detected, not that all personal data or MNPI is absent.
- The internal fixture locks are narrow regression checks. Historical external TAB and ai4privacy results show substantial recall gaps; see [evaluation methodology](../BENCHMARKS.md).
- No public MNPI text-detection benchmark was identified in the recorded provenance review. Current MNPI evaluation uses internal expert-labelled/project-owner-reviewed fixtures. Strict `conjunctive_mnpi` span placement includes detector reconciliation; these labels are not independent ground truth.
- The internal matcher compares rule/text expectations rather than exact occurrences. Unexpected predictions may be missing annotations rather than false positives.
- TAB and ai4privacy overlap metrics have their own annotation/matching conventions. Aggregate reports spanning training, development and test data must not be presented as held-out accuracy after tuning on them.
- Rule-based PII/MNPI scores are not calibrated probabilities. Statutory citations provide explanatory context, not legal conclusions.
- Junas is text-only. Native PDF/Office/email/archive/image inputs, OCR and base64-document ingestion were removed. Externally prepared text may omit information from its original file; Junas cannot assess the completeness of that external conversion. Historical OCR/document fixtures and reports remain archived evidence, not supported entrypoints.
- Automated model-consensus corpora are synthetic development evidence. Different models can share errors, and their confidence scores are uncalibrated self-reports. Conditional agreement metrics against model-declared exhaustive labels are not independently validated accuracy; see [the research contract](automated-corpus.md).
- Optional NER, retrieval and LLM configurations change what is measured. Record configuration and evaluate them separately; strict mode does not call retrieval/LLM helpers.
- No product enforcement, approvals, audit journal, rewriting, re-identification, tenant authentication or hosted service is provided by this research tree.
