# SGLB-12 Multi-Issue-Spotting

Version: 0.1-draft. Tracking issue: [#53](https://github.com/gongahkia/junas/issues/53).

## Capability

**C5 — Issue spotting (multi-source).** Given a compound SG fact
pattern, identify every issue triggered across PDPA + Employment Act +
Rules of Court 2021.

## Literature anchor

- Guha et al., **LegalBench** (NeurIPS 2023), `learned_hands_*` and
  `proa` issue-spotting families.
- Chalkidis et al., **LexGLUE** (ACL 2022), ECtHR Task A multi-label
  scoring protocol.

## Input contract

```python
case.inputs = {
  "scenario": str,   # 400–800-token compound SG fact pattern
}
```

## Output contract

Model output is a JSON list of issue labels:

```json
["pdpa.protection_obligation", "ea.notice_period_breach", "roc.expert_evidence_procedure_breach"]
```

## Scoring

- `multi_label_f1` over the issue taxonomy.
- **Macro-F1** (each class weighted equally) and **micro-F1** (each
  instance weighted equally) both reported.
- **Exact-set-match** as a strict secondary metric.
- Per-issue P/R in the leaderboard.

## Source provenance

- Adapters: `PdpcAdapter`, `MomAdapter`, `SsoAdapter`.
- Dataset construction:
  1. Author ~80 "atomic scenarios" each carrying exactly one issue
     label from the taxonomy.
  2. Composer samples 2–4 atomic scenarios per compound case; verifies
     non-conflicting label set.
  3. Validator (≥2 independent labellers, ≥85% agreement) gates
     inclusion.
- Issue taxonomy lives at `data/sglb_12/taxonomy.yaml`; each label has
  a trigger condition citing the underlying Act/Rule.

## Limitations

- Synthesised fact patterns may be unrealistic; a 20-item sample is
  reviewed by an SG-law-trained reviewer pre-launch.
- Party names are anonymised with a fixed substitution table so models
  cannot exploit "Mr Tan" as a SG-context signal.
- The taxonomy is necessarily incomplete; under-labelled cases are
  filtered out via the composer's single-label-source constraint.

## v0.1 / v0.2 stratification

- v0.1: ~120 compound scenarios.
- v0.2 held-out: ~30 scenarios from post-2026-Q1 source materials.
- Per-issue and per-source breakdown.
