# Managed LLM Deployment

The production default is deterministic-only review. Public evidence retrieval and LLM adjudication are separate opt-in layers. Do not enable either layer just because the backend is deployed.

## Default: Deterministic-Only

Use this posture for first pilots, regulated environments without provider approval, and public demos:

```sh
export PIPELINE_LAYERS=""
export JUNAS_PUBLIC_EVIDENCE_ENABLED=0
export JUNAS_PUBLIC_EVIDENCE_PROVIDER=none
export JUNAS_LLM_ENABLED=0
export JUNAS_LLM_PROVIDER=none
export JUNAS_LLM_HELPERS_ENABLED=0
export JUNAS_LLM_DEFINED_TERMS_ENABLED=0
export JUNAS_LLM_COVERAGE_AUDIT_ENABLED=0
```

Properties:

- deterministic findings and policy decisions remain the source of truth
- no public-evidence outbound lookup
- no LLM adjudication or helper call
- no provider API keys required
- outbound internet egress can be blocked except for approved infrastructure dependencies

## Opt-In: Public Evidence Only

Public evidence retrieval is for audit-grade public-source checks. It is not LLM adjudication.

```sh
export PIPELINE_LAYERS=public_evidence
export JUNAS_PUBLIC_EVIDENCE_ENABLED=1
export JUNAS_PUBLIC_EVIDENCE_PROVIDER=serper
export SERPER_API_KEY=...
export JUNAS_LLM_ENABLED=0
```

Required controls:

- tenant/workflow approval for external public-source lookup
- sanitized outbound query policy
- privacy-ledger events for every attempted lookup
- SIEM export that hashes or drops sensitive nested values
- egress allowlist limited to the selected provider

## Opt-In: LLM Adjudication

LLM adjudication is advisory. It cannot suppress deterministic-high findings and must keep the deterministic policy decision path intact.

Remote structured-token mode:

```sh
export PIPELINE_LAYERS=public_evidence,llm_adjudicator
export JUNAS_PUBLIC_EVIDENCE_ENABLED=1
export JUNAS_PUBLIC_EVIDENCE_PROVIDER=serper
export SERPER_API_KEY=...
export JUNAS_LLM_ENABLED=1
export JUNAS_LLM_PROVIDER=openai
export JUNAS_LLM_BASE_URL=https://api.openai.com/v1
export JUNAS_LLM_MODEL=<approved-model>
export JUNAS_LLM_API_KEY=...
export JUNAS_LLM_ALLOW_REMOTE_BASE_URL=1
export JUNAS_LLM_INPUT_MODE=structured_tokens
export JUNAS_LLM_ALLOW_REMOTE_RAW_TEXT=0
export JUNAS_LLM_TENANT_OPT_IN_OPENAI=1
```

The `structured_tokens` mode sends rule ids, severities, jurisdiction codes, scores, hashes, and public-evidence metadata. It must not send raw document text, matched spans, prompt text, email bodies, filenames, recipient addresses, reviewer rationale, or mapping values.

Azure OpenAI requires the same deployer and tenant gates plus:

```sh
export JUNAS_LLM_PROVIDER=azure_openai
export JUNAS_LLM_TENANT_OPT_IN_AZURE_OPENAI=1
export JUNAS_LLM_AZURE_API_VERSION=<approved-api-version>
```

## Exceptional: Remote Raw Text

Remote raw-text mode is disabled by default and must stay disabled unless the tenant has explicitly approved raw customer text transfer for the provider, model, workflow, retention window, and data residency posture.

```sh
export JUNAS_LLM_INPUT_MODE=raw_text
export JUNAS_LLM_ALLOW_REMOTE_RAW_TEXT=1
```

Approval evidence must record:

- tenant id and approving actor
- provider, endpoint, model, and region/data residency
- allowed workflows and expiry/review date
- privacy-ledger and SIEM settings
- incident/rollback contact

## Docker Overlay

`docker-compose.managed-llm.yml` is an overlay for a deployment that already satisfies production controls from `docker-compose.production.example.yml` or an equivalent customer baseline.

```sh
JUNAS_LLM_API_KEY=... \
JUNAS_LLM_TENANT_OPT_IN_OPENAI=1 \
SERPER_API_KEY=... \
docker compose -f docker-compose.yml -f docker-compose.managed-llm.yml up --build
```

Do not use the managed-LLM overlay to bypass tenant auth, policy config, journal keys, retention manifest, SIEM review, or no-body logging.

## Verification

- `scripts/preflight.py --deployment production --strict` must pass.
- `/ready` and `/diagnostics` must show helper dependencies as disabled, configured, or unhealthy without leaking prompt/document text.
- `privacy_ledger` entries must appear for public evidence and LLM operations.
- `test/test_structured_tokens_llm.py`, `test/test_openai_provider_optin.py`, and `test/test_tinyfish_and_remote_llm.py` cover the remote gates.
- `docs/security/remote-llm-config.md` remains the lower-level config reference.
