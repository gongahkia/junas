# Community Rule Packs

Junas can consume local community rule packs through the optional Gitleaks TOML
importer. This repo currently carries an in-tree seed under `rules/community/`;
the intended external home is `gongahkia/junas-rules` after the format has enough
contributor traffic to justify a separate release stream.

## Local Smoke Test

```sh
uv run junas rules test \
  --gitleaks rules/community/gitleaks-acme-demo.toml \
  --text-file rules/community/fixtures/acme-api-token.txt
```

Machine-readable output:

```sh
uv run junas rules test \
  --gitleaks rules/community/gitleaks-acme-demo.toml \
  --text-file rules/community/fixtures/acme-api-token.txt \
  --json
```

To enable a pack in `/review`, point `JUNAS_GITLEAKS_RULE_PACKS` at one or more
local TOML files as documented in `docs/secret-rule-packs.md`.

## Rule Format

Community packs use the supported Gitleaks TOML subset:

- `title` at the file root
- `[[rules]]` with `id`, `description`, `regex`, `secretGroup`, optional
  `entropy`, `keywords`, and `tags`
- root `[[allowlists]]` or per-rule `[[rules.allowlists]]` for known safe
  placeholders and test strings
- no `[extend]`; publish materialized packs only

Each rule should tag its source and intent, for example `secret`, `saas`,
`internal`, or `community`.

## Required Tests

Every contributed rule must include:

- one regex or detector-equivalent rule
- one matching fixture containing a synthetic token
- one non-matching or allowlisted fixture when the format has likely false
  positives
- local `junas rules test` evidence before review

Fixtures must be fake. Do not commit production secrets, customer data, or token
samples copied from incidents.

## Versioning

The future `gongahkia/junas-rules` repo should version packs independently from
Junas:

- `vMAJOR.MINOR.PATCH` tags for released pack bundles
- major bumps for renamed/removed rule IDs or severity-affecting changes
- minor bumps for new rules or allowlists
- patch bumps for fixture/doc-only fixes or tighter false-positive handling

Junas consumes local files, not remote URLs. Operators pin pack versions by
checking out or vendoring a tagged rule-pack release and setting
`JUNAS_GITLEAKS_RULE_PACKS` to those local files.

## Repository Plan

Until `gongahkia/junas-rules` exists, keep seed rules in `rules/community/`.
When split out, preserve this layout:

- `gitleaks/*.toml` for materialized Gitleaks-compatible packs
- `fixtures/<rule-id>/match.txt` and `fixtures/<rule-id>/allowlisted.txt`
- `tests/` with a CLI smoke wrapper around `junas rules test`
- `CONTRIBUTING.md` requiring one rule plus one fixture per contribution
