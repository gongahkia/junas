# Contributing

Junas is backend-first. Contributions should preserve the deterministic local
runtime and keep adapter claims tied to documented evidence.

## Setup

Use `uv` from the repo root:

```sh
uv sync --extra dev
uv run python -m spacy download en_core_web_sm
uv run python scripts/preflight.py --strict
```

Run the one-command deterministic demo:

```sh
./scripts/demo.sh
```

Start the backend when you need an interactive local API:

```sh
./scripts/launch/run_backend_only.sh
curl http://127.0.0.1:8000/ready
```

## Verification

For docs-only changes, run the focused tests that cover the touched surface plus
format checks:

```sh
uv run ruff check
git diff --check
```

For runtime changes, run the standard gate:

```sh
./scripts/verify_runtime.sh
uv run pytest
```

For accuracy, corpus, or detector work, also run the relevant generated-doc and
recall gates:

```sh
uv run python scripts/recall_gate.py
uv run python scripts/generate_accuracy_doc.py --check
```

## Invariants

- The default local runtime is deterministic and offline. Do not add provider keys,
  external HTTP calls, LLM calls, or cloud dependencies to `review_profile=strict`.
- The local SKU must not require `torch`, `transformers`, `sentence-transformers`,
  `redis`, `xgboost`, `scikit-learn`, `pandas`, `accelerate`, or external HTTP.
- The FastAPI backend remains the trust boundary. Adapters collect workflow context
  and display backend decisions; they must not become separate detection or policy
  engines.
- Deterministic-high findings must stay visible in the review and policy path.
  Optional public-evidence or LLM helpers may add context for eligible audit-grade
  cases, but must not erase deterministic-high evidence.
- Logs, telemetry, SIEM events, docs examples, and issue bodies must not include
  real secrets, customer text, live personal data, reversible mappings, or auth
  headers.
- README/product claims need local evidence: docs, tests, eval reports, screenshots,
  generated artifacts, or vendor docs where platform behavior is involved.

## Good First Issues

Prefer docs and small tests before changing detector, auth, persistence, or adapter
runtime code. Current scoped issues:

- [#77: Add desktop watcher threat model](https://github.com/gongahkia/junas/issues/77)
- [#78: Add developer FAQ for review and rewrite endpoints](https://github.com/gongahkia/junas/issues/78)
- [#79: Add deployment comparison table](https://github.com/gongahkia/junas/issues/79)
- [#80: Add operator FAQ for DLP coexistence](https://github.com/gongahkia/junas/issues/80)
- [#81: Mark LaunchAgent install optional and admin-controlled](https://github.com/gongahkia/junas/issues/81)

These are intentionally documentation-only entry points drawn from `TODO.md`.

## Pull Request Notes

- Keep changes scoped to the issue or task.
- Update tests when changing behavior, contracts, or user-visible docs.
- Do not broaden maturity, security, or accuracy claims without adding evidence in
  the same change.
- Include the commands you ran in the PR description.

