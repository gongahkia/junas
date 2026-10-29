# Advisory experiments

The default classifier is deterministic. `audit_grade` experiments can add public-evidence retrieval, structured LLM adjudication, defined-term extraction and coverage warnings when explicitly configured.

Deterministic high-severity findings remain controlling evidence. Helpers only engage on eligible cases, and LLM-raised findings are capped at medium severity. Keep strict and assisted accuracy reports separate and record model/provider/input mode.

Remote endpoints require explicit permission in configuration. Remote raw text additionally requires an explicit raw-text opt-in; structured tokens are the remote default. Provider-specific opt-in checks remain in the retained clients. Standard tests mock transport and do not send corpus text to providers.

Before promoting an advisory model, use independently reviewed labels, compare precision and recall with the deterministic baseline, inspect false positives and misses, and run `training/distillation/promotion_gate.py`. Training data must not overlap a claimed held-out test. Defined-term caches and teacher-call ledgers are research artifacts under `JUNAS_CACHE_DIR`.
