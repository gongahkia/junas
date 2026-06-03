# SGLB-09 Summary-Faithfulness

Version: 0.1-draft. Tracking issue: [#50](https://github.com/gongahkia/junas/issues/50).

## Capability

**C8 — Faithful summarisation.** Given a SG legal document and a
prompt-type-conditioned summary produced by the model, score whether
the summary introduces claims not supported by the source.

## Literature anchor

- Min et al., **FActScore: Fine-grained Atomic Evaluation of Factual
  Precision in Long Form Text Generation** (EMNLP 2023, [arXiv:2305.14251](https://arxiv.org/abs/2305.14251)).
- Fabbri et al., **QAFactEval** (NAACL 2022, [arXiv:2112.08542](https://arxiv.org/abs/2112.08542)).

## Input contract

```python
case.inputs = {
  "source_document": str,   # SG judgment / PDPC decision / MOM advisory
  "prompt_type": str,       # summary | principles | themes | sentencing |
                            # legislative_timeline | policy_timeline
}
```

## Output contract

Model output is the free-form summary text (≤ 800 tokens).

## Scoring

The output is decomposed into atomic factual claims by an LLM extractor
(fixed prompt). For each claim, an ensemble of ≥3 judge models votes
on `supported / contradicted / unsupported` against the source.

- **Score = supported / (supported + unsupported + contradicted)** —
  the FActScore atomic-precision metric.
- Leaderboard also reports `unsupported / total` (hallucination rate),
  `contradicted / total` (contradiction rate), and inter-judge κ on a
  200-claim spot-check subset.

## Source provenance

- Adapters: `ElitigationAdapter` (judgments), `PdpcAdapter` (decisions),
  `MomAdapter` (advisories).
- Required fields: full `body` text + provenance URL.
- Sources are NOT modified; the model receives the document verbatim.

## Limitations

- Judges may favour verbose, hedged summaries; we score precision, not
  recall.
- Inter-judge variance dominates with κ < 0.4; the task is dropped if
  this is sustained (coverage matrix §8).
- Source documents may leak in training data; held-out post-2026-Q1
  subset reports the contamination delta.
- Atomic-claim extraction itself can hallucinate; a 5% sample is
  hand-checked per release.

## v0.1 / v0.2 stratification

- v0.1: ~160 source documents × 6 prompt types = 960 generation slots.
- v0.2 held-out: ~40 sources × 6 prompt types post-2026-Q1.
- Per-prompt-type leaderboard breakdown.
