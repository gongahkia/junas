# Remote LLM Configuration

Junas treats remote LLMs as optional advisory providers. The deterministic review engine
is the default. Remote LLM transport requires deployer opt-in, tenant/provider opt-in,
structured-token input by default, and privacy-ledger evidence.

## Defaults

`config.toml` keeps remote LLM behavior off:

```toml
[llm]
enabled = false
provider = "vllm"
base_url = "http://127.0.0.1:8001/v1"
allow_remote_base_url = false
allow_remote_raw_text = false
tenant_opt_in_openai = false
tenant_opt_in_azure_openai = false
```

Input mode behavior:

- Local/private LLM base URLs default to `raw_text`.
- Remote LLM base URLs default to `structured_tokens` when `llm_input_mode` is omitted.
- Remote `llm_input_mode="raw_text"` is rejected unless `allow_remote_raw_text=true`.

Runtime drift tests:

- `test/test_runtime_settings_validation.py`
- `test/test_structured_tokens_llm.py`
- `test/test_openai_provider_optin.py`
- `test/test_tinyfish_and_remote_llm.py`

## Structured-Token Remote Mode

Use this shape for remote advisory review when no raw document text approval exists:

```toml
[llm]
enabled = true
provider = "openai"
base_url = "https://api.openai.com/v1"
model = "<approved-model>"
allow_remote_base_url = true
tenant_opt_in_openai = true
llm_input_mode = "structured_tokens"
allow_remote_raw_text = false
```

Environment equivalent:

```sh
export JUNAS_LLM_ENABLED=1
export JUNAS_LLM_PROVIDER=openai
export JUNAS_LLM_BASE_URL=https://api.openai.com/v1
export JUNAS_LLM_MODEL=<approved-model>
export JUNAS_LLM_ALLOW_REMOTE_BASE_URL=1
export JUNAS_LLM_TENANT_OPT_IN_OPENAI=1
export JUNAS_LLM_INPUT_MODE=structured_tokens
export JUNAS_LLM_ALLOW_REMOTE_RAW_TEXT=0
```

`structured_tokens` sends abstract rule, severity, jurisdiction, score, hash, and public
evidence metadata. It must not send raw document text or matched spans.

## Raw-Text Remote Mode

Use remote raw-text mode only when the tenant has explicitly approved sending raw
document text to that provider for the workflow.

```toml
[llm]
enabled = true
provider = "openai"
base_url = "https://api.openai.com/v1"
model = "<approved-model>"
allow_remote_base_url = true
tenant_opt_in_openai = true
llm_input_mode = "raw_text"
allow_remote_raw_text = true
```

Required approval record:

- Tenant id and actor approving the opt-in.
- Provider, model, endpoint, and data residency note.
- Workflows allowed to send raw text.
- Expiry or review date.
- Confirmation that privacy-ledger and SIEM events are enabled for the deployment.

LLM helper layers that send raw preambles or document excerpts inherit the same
`allow_remote_raw_text=true` requirement.

## Azure OpenAI

Azure OpenAI requires the deployer-level remote URL gate, tenant/provider opt-in, and an
Azure API version:

```toml
[llm]
enabled = true
provider = "azure_openai"
base_url = "https://<resource>.openai.azure.com"
model = "<deployment-name>"
allow_remote_base_url = true
tenant_opt_in_azure_openai = true
azure_api_version = "<approved-api-version>"
llm_input_mode = "structured_tokens"
allow_remote_raw_text = false
```

Environment keys:

```sh
export JUNAS_LLM_PROVIDER=azure_openai
export JUNAS_LLM_BASE_URL=https://<resource>.openai.azure.com
export JUNAS_LLM_MODEL=<deployment-name>
export JUNAS_LLM_ALLOW_REMOTE_BASE_URL=1
export JUNAS_LLM_TENANT_OPT_IN_AZURE_OPENAI=1
export JUNAS_LLM_AZURE_API_VERSION=<approved-api-version>
export JUNAS_LLM_INPUT_MODE=structured_tokens
```

## Privacy Ledger

Remote LLM and public-evidence paths must emit privacy-ledger entries. Expected fields
include:

- `operation`, such as `llm_adjudication`, `llm_defined_terms`, or `external_query`.
- `destination`, such as `openai`, `azure_openai`, `exa`, or `tinyfish`.
- `input_mode`, especially `structured_tokens` or `raw_text` for LLM paths.
- `allowed`, `reason`, and `redactions`.

Responses return `privacy_ledger` for audit-grade paths. SIEM export hashes or drops
sensitive nested values; use `test/test_siem_export.py` as the regression guard.

## Governance Links

- Promotion and invariant gates: `docs/llm-governance.md`.
- Release gate: `docs/security/release-checklist.md`.
- Dependency/security scans: `docs/security/dependency-scanning.md`.
