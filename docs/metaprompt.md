# Metaprompt For Layer-Trigger String Generation

Use the template below to prompt an LLM to generate layer-targeted test strings in the same style as `docs/layer_trigger_strings.md`, adapted for a specific `X` context and `Y` company.

Replace `<X_CONTEXT>` and `<Y_COMPANY>` before use.

```text
You are generating backend test strings for Noupe's `/classify` pipeline.

Context inputs:
- X_CONTEXT: <X_CONTEXT>
- Y_COMPANY: <Y_COMPANY>

Goal:
Generate strings written in the same style as the existing layer-trigger examples:
- concise
- corporate / analyst / internal-note tone
- plausible business language

Critical pipeline constraints you must satisfy:
1. Lexicon deterministic short-circuit is triggered by either:
   - an exact restricted-entity match, or
   - a money amount >= 1,000,000 (e.g., "$2.5 million").
2. Embedding runs when the request is not short-circuited.
3. Clustering should be tested with an unusual/jargon-heavy outlier sentence.
4. Model-2 is gated: it only runs if Model-1 predicts risk.
5. Mosaic requires an `entity_id` to run.
6. Mosaic escalation needs 10 unique low-risk fragments for the same `entity_id`.
7. Regression can run as final synthesis when configured/artifacts exist.

Output requirements:
1. Return exactly the sections below.
2. Each section must contain one fenced `text` code block, except `mosaic_request_template` which must be fenced `json`.
3. Use Y_COMPANY naturally in each sentence where it fits.
4. Do not reuse the exact wording of previous examples.
5. Keep each single-line string <= 180 characters.

Sections to output (in this exact order):
- lexicon_short_circuit
- embedding_baseline
- clustering_anomaly_candidate
- model1_risk_candidate
- model2_high_risk_candidate
- mosaic_single_fragment
- mosaic_request_template
- regression_candidate
- mosaic_escalation_fragments_10

Per-section criteria:
- lexicon_short_circuit:
  Include Y_COMPANY plus either an exact restricted-entity form (if known) OR a money expression >= $1,000,000.
  Intention: trigger lexicon high-risk short-circuit.

- embedding_baseline:
  Neutral/public update language.
  Avoid confidentiality cues, avoid large money expressions, avoid severe event wording.
  Intention: allow embedding to run without short-circuit.

- clustering_anomaly_candidate:
  Use abnormal/rare financial jargon and synthetic phrasing.
  Avoid short-circuit patterns from lexicon.
  Intention: increase anomaly likelihood for clustering.

- model1_risk_candidate:
  Include non-public forward-looking signal (draft/internal/unannounced/confidential style).
  Avoid money >= $1,000,000 to prevent lexicon short-circuit.
  Intention: bias Model-1 toward risk.

- model2_high_risk_candidate:
  Stronger severity than model1_risk_candidate (e.g., layoffs, regulatory action, board-level adverse decision).
  Keep non-public tone and explicit impact cue (percentage allowed).
  Avoid money >= $1,000,000 to prevent lexicon short-circuit.
  Intention: bias Model-2 toward high_risk after Model-1 risk gate.

- mosaic_single_fragment:
  Mild risk signal likely to be low_risk (not clearly safe, not clearly high_risk).
  Must mention Y_COMPANY.

- mosaic_request_template:
  Provide JSON object:
  {"text":"<exact mosaic_single_fragment text>","entity_id":"<slugified-y-company>-mosaic"}

- regression_candidate:
  Mixed-signal statement with several soft risk indicators.
  Avoid lexicon short-circuit patterns.
  Intention: produce richer upstream features for regression.

- mosaic_escalation_fragments_10:
  Exactly 10 lines inside one `text` code block.
  All 10 lines must:
  - use the same X_CONTEXT and Y_COMPANY theme,
  - be semantically distinct,
  - stay mild/low-risk leaning,
  - avoid exact duplicates and near-duplicates.

Final validation checklist (must be satisfied before you return):
- 9 required sections present, in exact order.
- 8 `text` code blocks + 1 `json` code block.
- Mosaic set has exactly 10 unique lines.
- Lexicon short-circuit line contains a deterministic trigger.
- Model2 line is stronger than Model1 line.
```

Recommended usage note: after generating strings, verify execution via `observability.executed_layers` and `observability.skipped_layers`.
