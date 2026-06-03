# External Rule Packs

`Aki` can optionally import established secret-detection regex rules from a local gitleaks TOML file.

## Decision

V1 supports gitleaks-style TOML rules. Gitleaks rules expose `id` and `regex` fields that map directly into Aki's existing regex-based detector registry.

Trufflehog is not imported in v1. Its detectors are more code- and entropy-oriented, so a faithful import would require a larger detector abstraction than the current regex registry. Treat trufflehog as an evaluated but deferred format.

## Config

```toml
[detection]
external_rules_path = "/path/to/gitleaks.toml"
external_rules_format = "gitleaks"
max_external_patterns = 128
```

The rule pack is local-only. Aki does not download rule packs or call a cloud scanner.

## Imported Fields

For each `[[rules]]` entry, Aki reads:

- `id`
- `regex`

Other gitleaks fields, such as `description`, `keywords`, `tags`, and `entropy`, are accepted by the TOML parser but are not interpreted by v1.

Imported pattern names are prefixed with `gitleaks:`. For example, a gitleaks rule with `id = "github-pat"` becomes `gitleaks:github-pat` in Aki's pattern manager and detection logs.

## Bounds

External rules are disabled unless `external_rules_path` is set.

Imported rules are compiled once at startup. Runtime scan cost is bounded by `max_external_patterns`, and Aki hard-caps that value at 128 imported patterns. Individual imported regex strings longer than 4096 bytes are skipped.

If the configured rule file cannot be parsed or a rule regex cannot compile with Rust's regex engine, Aki logs a warning and continues with built-in/user rules.

## Validation

Use `aki test-patterns` with a temporary config to verify imported rules:

```console
$ XDG_CONFIG_HOME=/tmp/aki-config aki test-patterns "token=ghp_abcdefghijklmnopqrstuvwxyzABCDEFGH12"
```

The test fixture in `privacy-core/fixtures/gitleaks_rules.toml` covers gitleaks import behavior in `cargo test --all`.
