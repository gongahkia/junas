# Research runtime configuration

`config.toml` controls extraction, optional OCR, public evidence, LLM helpers and privacy gates. Environment variables override TOML; explicit dotted-key overrides passed to `get_runtime_settings()` override both. Unknown sections and keys fail validation.

The default pipeline rejects unsupported extraction and disables external providers. Local NER is independently enabled by `JUNAS_LOCAL_NER_FALLBACK=1`. Configuration no longer contains HTTP, authentication, telemetry, cache-service or deployment controls.
