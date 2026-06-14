# SGLB-09 Summary-Faithfulness

Version: 0.1-local-scaffold. Tracking issue: [#50](https://github.com/gongahkia/junas/issues/50).

## Status

Implemented locally as a deterministic smoke scaffold:

- builder: `backend/benchmark/dataset_builders/sglb_09.py`
- task runner: `backend/benchmark/tasks/sglb_09.py`
- evaluator: `atomic_fact_score`
- dataset: `backend/benchmark/datasets/sglb_09_summary_faithfulness.yaml`

This is benchmark-ineligible. The PROMPTS-TO-RUN.md Azure single-judge
v0.1 smoke and v0.2 multi-judge kappa run are still pending.

## Capability

**C8 - Faithful summarisation.** Given a Singapore legal source text and
a candidate summary, identify atomic factual claims in the summary and
mark whether each claim is supported by the source.

## Literature anchor

- Min et al., **FActScore: Fine-grained Atomic Evaluation of Factual
  Precision in Long Form Text Generation** (EMNLP 2023, [arXiv:2305.14251](https://arxiv.org/abs/2305.14251)).
- Fabbri et al., **QAFactEval** (NAACL 2022, [arXiv:2112.08542](https://arxiv.org/abs/2112.08542)).

## Input contract

```python
case.inputs = {
  "source_text": str,  # PDPC fact summary in the local scaffold
  "summary": str,      # candidate summary to evaluate
}
```

## Output contract

```json
{
  "atomic_facts": [
    {"fact": "A warning was issued to Acme.", "supported": true}
  ]
}
```

## Scoring

`atomic_fact_score` parses the JSON output, selects facts with
`supported == true`, and computes deterministic precision:

```text
score = supported_true_facts_present_in_source_text / predicted_supported_true_facts
```

Containment is exact after whitespace collapse and case folding. If the
model predicts no supported facts, the score is `1.0` only when the gold
scaffold also has no supported facts; otherwise it is `0.0`.

## Local data provenance

The scaffold reuses existing SGLB-01 PDPC JSONL rows. It builds 20
synthetic summary-faithfulness cases by cycling three variants:

- `faithful`
- `mild_hallucination`
- `wholesale_fabrication`

Labels are deterministic and mechanically derived from the generated
summary text. Metadata records `data_tier: synthetic`,
`benchmark_eligible: false`, source SGLB-01 identifiers, and the source
PDPC citation/URL where present.

## Pending publication gates

- Azure single-judge v0.1 smoke from PROMPTS-TO-RUN.md.
- v0.2 judge ensemble across Azure, Anthropic, and Gemini.
- Pairwise kappa and Fleiss' kappa.
- 20-case human-validated holdout.
- Scale path to N=200 after kappa passes the coverage-matrix threshold.
