# Local Distilled Adjudicator Model Card

## Promotion Status

No `local_distilled` adapter is promoted in this repository state. The default
`promotion_manifest.json` sets `promoted=false`, and the promotion gate rejects
any adapter path unless `promoted=true` is paired with passing model-card,
privacy-eval, and invariant-eval artifacts.

## Intended Use

The local student is an optional `audit_grade` MNPI adjudicator. It may advise on
ambiguous deterministic outputs only. It is not a replacement for deterministic
PII/MNPI detectors, source verification, counsel review, or the strict runtime.

## Training Data

No promoted adapter means no training dataset is claimed here. A future promoted
adapter must name the teacher provider, corpus paths, consent basis, collection
date, dataset hash, input mode, and whether raw document text was included.

## Evaluation

Promotion requires `training/distillation/eval_against_corpus.py` output for the
target adapter, with `student_provider=local_distilled`, agreement at or above
the manifest threshold, and zero invariant violations unless the manifest is
deliberately changed.

## Privacy

The preferred training and runtime mode is `structured_tokens`: document body
hash, rule names, severities, jurisdictions, and bounded evidence counts, not raw
document text. Remote raw text remains a separate explicit opt-in and is not
allowed for local-adapter promotion evidence.

## Invariants

- The student must not upgrade above the deterministic risk label.
- LLM output remains advisory and cannot create high-severity findings directly.
- `matched_public_sources` stays empty in structured-token mode.
- Privacy ledger events must exist for teacher collection and runtime helper use.
- Promotion is blocked if privacy eval or invariant eval fails.

## Regulatory Notes

EU AI Act GPAI obligations entered into application on 2025-08-02; Commission
enforcement powers start on 2026-08-02; providers of GPAI models placed on the
market before 2025-08-02 must comply by 2027-08-02. Source:
https://digital-strategy.ec.europa.eu/en/policies/guidelines-gpai-providers

SG PDPC opened public consultation on proposed advisory guidelines for use of
personal data in Generative AI on 2026-06-02. Promotion evidence must include
the `pdpc_genai_personal_data_review` privacy check. Source:
https://www.pdpc.gov.sg/organisations/regulations-decisions/regulatory-guidance/public-consultation-on-the-proposed-advisory-guidelines-on-use-of-personal-data-in-generative-ai
