# Community Rule Packs

The planned community rule-pack repository is `gongahkia/aki-rules`. Until that repository is split out, this repo keeps the format contract and a sample pack under [`rule-packs/`](../rule-packs/).

## Format

Aki consumes community rule packs as local gitleaks-compatible TOML files. V1 reads only `id` and `regex`; other fields are kept for contributor clarity and future compatibility.

```toml
title = "aki community rules"

[[rules]]
id = "vendor-demo-token"
description = "What this fake or vendor-specific token shape detects"
regex = '''vendor_demo_[a-z0-9_]{16,}'''
keywords = ["vendor_demo_"]
tags = ["vendor", "token"]
```

Required fields:

- `id`: stable, lowercase, hyphen-separated rule identifier.
- `regex`: Rust `regex` syntax. Keep it bounded and specific.

Recommended fields:

- `description`: one sentence explaining the detector.
- `keywords`: literals that make the rule easy to review.
- `tags`: product, category, or owner labels.

## Required Fixture

Every rule contribution must include one fixture string that matches the rule. Fixtures must be fake, reserved, or project-specific examples that cannot be mistaken for a live credential.

For example:

- Rule: [`rule-packs/aki-rules-sample.toml`](../rule-packs/aki-rules-sample.toml)
- Fixture: [`rule-packs/fixtures/sample-aki-demo-service-key.txt`](../rule-packs/fixtures/sample-aki-demo-service-key.txt)

Do not submit real secrets, live customer examples, production tokens, private keys, or copied incident artifacts.

## Required Tests

Each new rule must include:

- One regex or detector rule in the TOML pack.
- One matching fixture under `fixtures/`.
- One test that imports the pack and proves the fixture matches.

In this repository, the sample pack is covered by:

```console
$ cargo test -p privacy-core detection::external_rules::tests::imports_community_rule_pack_sample
```

## Versioning

`gongahkia/aki-rules` should use SemVer tags once it exists:

- Patch: rule wording, fixture cleanup, or false-positive tightening that should not break expected matches.
- Minor: new rules or new fixture categories.
- Major: format changes or broad regex behavior changes that can alter scan cost or match semantics.

Aki does not auto-download rule packs. Users pin a local checkout, release archive, or vendored file path and update it intentionally.

## Local Consumption

Configure Aki with a local rule-pack path:

```toml
[detection]
external_rules_path = "/path/to/aki-rules/aki-rules.toml"
external_rules_format = "gitleaks"
max_external_patterns = 128
```

Then verify the pack locally:

```console
$ aki test-patterns "$(cat /path/to/aki-rules/fixtures/example.txt)"
```

Imported patterns are prefixed with `gitleaks:` in the pattern manager and detection logs. The import remains local-only; Aki does not call a cloud scanner or upload fixtures.
