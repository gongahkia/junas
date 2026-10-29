# Security

Junas is a local classifier research codebase. It is not an enforcement control and should not be used as proof that text is safe to disclose.

Use synthetic, approved or appropriately governed evaluation data. Findings and CLI JSON can contain matched text and extracted document content; treat output accordingly. External OCR, retrieval and LLM helpers require explicit configuration and privacy gates. Strict text evaluation makes no provider calls.

Document parsing is bounded and rejects unsupported/unreadable inputs by default. Native OCR and file parsers process untrusted input; use a disposable environment for untrusted corpora. The optional LLM defined-term cache and teacher-call ledger use `JUNAS_CACHE_DIR` (default `.junas-cache`); manage retention for experiments.

Report exploitable parser, provider-gate or dependency issues privately through the repository's GitHub security reporting mechanism. Do not include real sensitive input in public issues.
