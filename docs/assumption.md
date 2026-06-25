# Assumptions

## General

- Junas is API-only in this repo; archived UI/demo surfaces are not runtime product paths.
- `POST /review`, `POST /pseudonymize`, irreversible `POST /anonymize`, `POST /redact`, `POST /redact-pii`, `POST /hold-until-public`, `POST /cite-public-source`, and `POST /request-approval` are the primary endpoints.
- `POST /classify` and `POST /classify/batch` are compatibility shims over `engine.review()`.
- The deterministic engine is the source of truth. LLM/retrieval tiers are advisory and cannot suppress deterministic-high findings.
- Batch classification is limited to 32 items per call.

## Deterministic Review

- spaCy model: `en_core_web_sm`.
- Presidio recognizers supplement deterministic jurisdiction packs.
- Jurisdiction-specific detectors must be statute-anchored and covered by fixtures plus recall/precision locks.
- Defined-term suppression and entity linking are document-local, with optional session inheritance when a `session_id` is supplied.

## Public Evidence

- Public-source retrieval is optional and disabled by default.
- Supported providers: Exa, Tinyfish, Serper, SerpAPI.
- External providers receive only sanitized entity/ticker/event/date queries.
- Original request text, offending spans, emails, phone numbers, local IDs, and exact private financial values are not sent externally.
- `privacy_ledger` records every outbound query decision.

## LLM Adjudication

- LLM adjudication is optional and disabled by default.
- Local/private LLM endpoints may receive raw text.
- Remote endpoints default to `structured_tokens`; remote raw text requires both `JUNAS_LLM_ALLOW_REMOTE_BASE_URL=1` and `JUNAS_LLM_ALLOW_REMOTE_RAW_TEXT=1`.
- OpenAI requires the additional tenant opt-in gate `JUNAS_LLM_TENANT_OPT_IN_OPENAI=1`.
- LLM output is structured JSON and can only soften eligible ambiguous cases when public evidence supports it.

## FastAPI Orchestration

- Canonical app entrypoint is `junas.backend.main:app`; root `backend.*`, `api.*`, and `configs.*` shims are not supported.
- Default pipeline is empty because the deterministic engine is called directly.
- Configurable optional layers are `public_evidence` and `llm_adjudicator`.
- `GET /health`, `/ready`, `/diagnostics`, and `/metrics` expose runtime status.
- Swagger and ReDoc are served by FastAPI at `/docs` and `/redoc`.
