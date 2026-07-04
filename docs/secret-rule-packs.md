# Optional Secret Rule Packs

Junas can import a bounded, text-only subset of Gitleaks TOML rules for users
who want established secret-detector coverage in `/review`. This is disabled by
default and is not a cloud dependency.

Enable with a local file path:

```sh
JUNAS_GITLEAKS_RULE_PACKS=/path/to/gitleaks.toml \
uv run uvicorn junas.backend.main:app --host 127.0.0.1 --port 8000
```

Multiple packs use the platform path separator:

```sh
JUNAS_GITLEAKS_RULE_PACKS=/path/base.toml:/path/team.toml
```

## Supported Gitleaks Subset

Web check performed 2026-07-04 against the official Gitleaks repository docs
and default config:

- <https://github.com/gitleaks/gitleaks?tab=readme-ov-file#configuration>
- <https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml>

Imported fields:

| Gitleaks field | Junas behavior |
|---|---|
| `[[rules]]` | Each text regex rule becomes a deterministic high-severity finding. |
| `id` / `description` / `tags` | Preserved in finding metadata. |
| `regex` | Compiled as a Python regex after a small `(?i)` / `\z` compatibility pass. |
| `secretGroup` | Uses the capture-group span as `matched_text`; defaults to full match. |
| `entropy` | Applies Shannon entropy to the extracted secret span. |
| `keywords` | Case-insensitive prefilter before regex scan. |
| `[allowlist]`, `[[allowlists]]`, `[rules.allowlist]`, `[[rules.allowlists]]` | Supports `regexes`, `stopwords`, `regexTarget`, `condition`, and `targetRules` for text spans. |

Unsupported fields fail fast or no-op by design:

- `[extend]` is not resolved; pass a materialized TOML pack.
- Path, commit, and repository-history allowlists are not applied because Junas
  reviews request text, not git history.
- TruffleHog verification/webhook checks are not run.
- Unsupported regex syntax raises `SecretRulePackError` on the first review
  after env opt-in.

Matches surface as `PII` findings with `legal_basis="EXTERNAL_SECRET_RULE_PACK"`
so existing redaction suggestions and high-risk policy behavior apply.

## Bounds

| Bound | Default | Override |
|---|---:|---|
| Rule-pack file size | 2 MiB | `JUNAS_GITLEAKS_RULE_PACK_MAX_BYTES` |
| Rules per pack | 512 | `JUNAS_GITLEAKS_MAX_RULES` |
| Secret findings per review | 64 | `JUNAS_GITLEAKS_MAX_MATCHES` |
| Regex length | 4,096 chars | fixed |

Default runtime cost is zero because no packs are loaded unless
`JUNAS_GITLEAKS_RULE_PACKS` is set. Enabled packs are cached by the process for
the active env/config tuple; keyword prefilters run before regex scans.

## TruffleHog Evaluation

Web check performed 2026-07-04 against TruffleHog custom detector docs:

- <https://github.com/trufflesecurity/trufflehog/blob/main/pkg/custom_detectors/CUSTOM_DETECTORS.md>

TruffleHog custom detectors support named regexes plus optional verifier logic.
That format is not imported in this pass because Junas would need a separate
YAML loader and a verifier policy boundary to avoid making review depend on
provider calls. The current opt-in path is Gitleaks TOML only.
