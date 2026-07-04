# Aki Community Rule Packs

This folder is the in-repo seed for a future standalone `gongahkia/aki-rules`
repository. Packs here use the bounded Gitleaks TOML subset documented in
`docs/community-rule-packs.md` and `docs/secret-rule-packs.md`.

Run the sample pack locally:

```sh
uv run aki rules test \
  --gitleaks rules/community/gitleaks-acme-demo.toml \
  --text-file rules/community/fixtures/acme-api-token.txt
```

Contribution minimum:

- one `[[rules]]` regex or detector-equivalent rule
- one matching fixture under `fixtures/`
- one non-matching or allowlisted fixture when false positives are likely
- version note in the pack README or release entry before external publication
