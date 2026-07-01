# LLM Governance

Junas treats LLM paths as optional advisory layers. The default runtime remains
deterministic-only. Remote LLM use requires tenant opt-in, provider opt-in, and
privacy-ledger evidence.

Operator config gates for remote providers, structured-token default, raw-text opt-in,
and privacy-ledger expectations are documented in `docs/security/remote-llm-config.md`.

## Current Promotion State

No `local_distilled` adapter is promoted in this repository state. The canonical
promotion manifest is `training/distillation/promotion_manifest.json`, currently
set to `promoted=false`.

Run the gate:

```sh
uv run python training/distillation/promotion_gate.py \
  --manifest training/distillation/promotion_manifest.json
```

`promoted=false` passes only when no adapter path is configured. `promoted=true`
requires:

- `training/distillation/MODEL_CARD.md`
- a privacy eval JSON with passing checks
- an `eval_against_corpus.py --output-report` JSON report
- an existing adapter directory
- agreement at or above the manifest threshold
- invariant violations at or below the manifest threshold

## Privacy Eval

Promotion requires `structured_tokens` evidence. Remote raw document text is not
accepted as local-adapter promotion evidence. Required privacy checks are:

- `structured_tokens_default`
- `remote_raw_text_blocked`
- `tenant_consent_required`
- `privacy_ledger_recorded`
- `pdpc_genai_personal_data_review`

## Customer Text Training Invariant

Junas does not train, fine-tune, distill, prompt-optimize, or benchmark LLM/student
models on customer text by default. Customer prompts, email bodies, document text,
matched spans, reviewer rationale containing customer text, reversible mappings, and
raw audit-pack contents are excluded from default training and distillation inputs.

Reviewer feedback may create counts, hashes, decision taxonomy labels, detector issue
categories, and synthetic fixture tasks. It must not become model training data unless
all of these are true:

- explicit customer sample approval covers training or distillation use
- raw sample text is scrubbed or transformed into an approved synthetic reproduction
- retention class, legal-hold status, and subject-erasure handling are documented
- privacy eval records the source and passes structured-token and tenant-consent checks
- promotion evidence names the approved dataset without embedding raw customer text

## SG PDPC GenAI Consultation

PDPC opened public consultation on proposed advisory guidelines for use of
personal data in Generative AI on 2026-06-02. Until final guidance lands,
Junas treats GenAI personal-data use as opt-in, ledgered, and structured-token
by default; promotion evidence must include the
`pdpc_genai_personal_data_review` check.

Source: https://www.pdpc.gov.sg/organisations/regulations-decisions/regulatory-guidance/public-consultation-on-the-proposed-advisory-guidelines-on-use-of-personal-data-in-generative-ai

## Invariant Gate

The student remains advisory. It must not upgrade above the deterministic risk
label, cannot create high-severity findings directly, and must keep structured
mode public-source lists empty. The promotion gate consumes the eval report and
fails if `overall.invariant_violations` exceeds the manifest threshold.

## EU AI Act GPAI Timeline

The European Commission states that GPAI provider obligations entered into
application on 2025-08-02, Commission enforcement powers start on 2026-08-02,
and GPAI models placed on the market before 2025-08-02 must comply by
2027-08-02.

Source: https://digital-strategy.ec.europa.eu/en/policies/guidelines-gpai-providers
