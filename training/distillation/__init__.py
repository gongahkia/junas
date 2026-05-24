"""Cloud-adjudicator distillation pipeline (architecture item 29).

Three scripts + one runtime provider:

- teacher_collector.py: runs the cloud LLM adjudicator (provider=openai, both gates set)
  over one or more corpora; writes JSONL of {text, deterministic_findings, teacher_verdict}.
- distill_train.py: LoRA fine-tunes a 1-3B param base model on the teacher JSONL with
  structured-JSON output supervision.
- eval_against_corpus.py: runs the student over the corpora and gates on locked
  precision/recall baselines in recall.lock.json / recall_adversarial.lock.json.
- local_distilled provider branch in LocalLLMAdjudicator: serves student verdicts via
  the same `adjudicate()` interface — no runtime contract changes.
"""
