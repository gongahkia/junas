# Contamination Probe Methodology

SG-LegalBench receipts can include a contamination probe when the runner is
called with `--contamination-probe`. The flag is default-off because it adds
one extra model call for every labelled case.

## What The Probe Measures

The normal benchmark prompt gives the model the case facts, statute question,
or clause text. The contamination probe is a separate pass that withholds that
input and asks for the labelled property directly. A high probe score means the
model can recall the label from the public source or dataset identifier, so the
ordinary task score may reflect memorisation rather than reasoning from the
provided facts.

Per case, the receipt records:

- `memorisation_score`: float in `[0, 1]`
- `memorisation_flag`: `true` when `memorisation_score >= 0.5`
- `memorisation_probe_version`

The task-level `contamination_summary` records:

- `mean_memorisation_rate`: share of probed cases with
  `memorisation_score >= 0.5`
- `contamination_adjusted_score`: per-evaluator mean over only cases with
  `memorisation_score < 0.5`

## Task Probes

SGLB-01 asks: `What was the outcome (obligation breached + penalty band) of
PDPC case <case reference>?` The scorer compares recalled obligations and
penalty band against the gold labels.

SGLB-02 asks: `What is the text of <statute> section <N>?` The scorer compares
the answer against the gold statutory answer fragment using ROUGE-L.

SGLB-04 is skipped. The citation grammar is deterministic; memorisation is not
the relevant failure mode.

SGLB-08 asks: `What is the tone label of clause <clause_id>?` A high score here
means the model likely saw the synthetic dataset or its identifiers. Current
reviewed fixtures reuse clause-family identifiers, so this probe is a weak
signal until the dataset carries non-leaking unique clause IDs.

## Interpretation

Use the ordinary score and contamination-adjusted score together:

- High ordinary score, low memorisation rate: best evidence of task performance.
- High ordinary score, high memorisation rate: treat the ordinary score as
  potentially contaminated.
- Low adjusted score with high ordinary score: the model may be recalling known
  labels rather than applying the supplied facts.
- `null` adjusted score: every case was flagged or skipped, so no clean subset
  remained.

For Azure reasoning-model baselines, get explicit budget approval before
running the probe. The probe doubles the number of LLM calls and reasoning-token
cost can dominate the estimate.
