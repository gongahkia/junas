# Agent Onboarding

Read this first, then read `ARCHITECTURE-PIVOT-24-MAY.md`.

## Current State

Kaypoh is an API-first pre-send safety engine for PII anonymization and MNPI review.

The deterministic review engine is the runtime source of truth. `/classify` and `/classify/batch` are compatibility wrappers over `engine.review()`.

The base `kaypoh-local` SKU is offline-default: deterministic engine, Presidio, spaCy, FastAPI, document extraction, local mappings, and packaging. It must not require torch, transformers, sentence-transformers, redis, xgboost, scikit-learn, pandas, or external HTTP.

The `kaypoh-server` SKU adds explicit opt-in public evidence and LLM adjudication/helper layers. External calls must pass PrivacyGuard and tenant/deployer opt-in gates.

## Required Reading Order

1. `ARCHITECTURE-PIVOT-24-MAY.md`
2. `docs/architecture.md`
3. `docs/statutory-coverage.md`
4. `docs/known-limitations.md`
5. `README.md`

## Standing Principles

- Deterministic review owns blocking decisions.
- Optional public-evidence and LLM layers are advisory unless explicitly documented otherwise.
- `strict` review must not call LLM helper layers.
- PrivacyGuard must sanitize outbound public-evidence/LLM inputs.
- Pseudonymized output remains personal data when Kaypoh or the controller retains a re-identification mapping.
- Fail closed for unsupported containers, unsafe macros, invalid runtime config, malformed tenant overrides, and missing opt-ins.
- Keep compatibility shims thin; canonical implementation lives under `src/kaypoh/`.
- Do not revive the archived layer1-6 classifier stack.

## Useful Commands

```sh
uv sync --extra dev
uv run python -m spacy download en_core_web_sm
./scripts/verify_runtime.sh
uv run python scripts/recall_gate.py
uv run python scripts/generate_accuracy_doc.py --check
```

## Work Guidance

- Prefer tests tied to the changed surface.
- Update generated docs through their scripts, not by hand.
- Keep procurement-facing claims aligned with committed corpus locks and statutory docs.
- Treat `docs/known-limitations.md` as user-facing truth for unsupported ingest and deployment surfaces.
- Commit each discrete audit fix separately.
