# Cloud-adjudicator distillation

End-to-end pipeline for distilling a cloud LLM (the *teacher*) into a small local model (the *student*) that serves the same MNPI adjudication contract via `LocalLLMAdjudicator`. Tracks architecture item 29.

## Why this exists

The runtime `LocalLLMAdjudicator` supports `provider=openai` for tenants who opt in. That gets you cloud-grade adjudication accuracy but with two downsides:

1. Per-call latency + cost.
2. The desktop SKU (`kaypoh-local`) cannot use it — by design, the desktop SKU is offline-default.

A LoRA-tuned student model (Qwen-1.5B / Phi-3-mini / Gemma-2B class) can recover most of the teacher's accuracy locally, ship inside `kaypoh-local`, and serve `audit_grade` requests with no cloud round-trip.

## Components

| File | Purpose |
|---|---|
| `prompts.py` | Shared prompt templates so teacher collection + student inference + LoRA training all see byte-identical message shapes. |
| `teacher_collector.py` | Walks one or more corpus directories, calls the configured teacher adjudicator for each doc, emits a JSONL dataset. Idempotent + ledgered. |
| `distill_train.py` | LoRA fine-tunes a base model on the JSONL with structured-JSON output supervision. `--dry-run` validates the dataset without touching a GPU. |
| `eval_against_corpus.py` | Runs the trained student over corpora, measures agreement-rate vs deterministic engine, flags invariant violations. |
| `student_provider.py` | `LocalDistilledAdjudicator` — loads the LoRA adapter + base model and serves `adjudicate()` calls in the same JSON shape as `LocalLLMAdjudicator`. |
| `promotion_gate.py` | Blocks `local_distilled` promotion unless the model card, privacy eval, adapter path, and invariant eval report pass. |

## Runtime activation

```
KAYPOH_LLM_PROVIDER=local_distilled \
KAYPOH_LLM_DISTILLED_ADAPTER_PATH=training/distillation/student-lora-v1 \
KAYPOH_LLM_DISTILLED_BASE_MODEL=Qwen/Qwen2.5-1.5B-Instruct \
uvicorn kaypoh.backend.main:app
```

The `LocalLLMAdjudicator.adjudicate()` routing branch in `inference.py` delegates to the student backend lazily on first call.

## End-to-end workflow

```bash
# 1) collect teacher verdicts (cloud LLM). requires the two-gate opt-in for OpenAI.
OPENAI_API_KEY=sk-... \
KAYPOH_LLM_TENANT_OPT_IN_OPENAI=true \
KAYPOH_LLM_ALLOW_REMOTE_BASE_URL=true \
KAYPOH_LLM_PROVIDER=openai \
KAYPOH_LLM_BASE_URL=https://api.openai.com/v1 \
KAYPOH_LLM_MODEL=gpt-4o-mini \
python3 training/distillation/teacher_collector.py \
    --corpus test/fixtures/legal-corpus \
    --corpus test/fixtures/legal-corpus-adversarial \
    --corpus test/fixtures/legal-corpus-sea \
    --output training/distillation/teacher_verdicts.jsonl

# 2) validate the dataset without spending GPU cycles
python3 training/distillation/distill_train.py \
    --dataset training/distillation/teacher_verdicts.jsonl --dry-run

# 3) actual LoRA training (GPU box)
pip install peft datasets accelerate
python3 training/distillation/distill_train.py \
    --dataset training/distillation/teacher_verdicts.jsonl \
    --output training/distillation/student-lora-v1 \
    --base-model Qwen/Qwen2.5-1.5B-Instruct \
    --epochs 3 --lora-rank 16 --learning-rate 2e-4

# 4) evaluate against locked corpora baselines
python3 training/distillation/eval_against_corpus.py \
    --corpus test/fixtures/legal-corpus \
    --corpus test/fixtures/legal-corpus-adversarial \
    --student-provider local_distilled \
    --adapter-path training/distillation/student-lora-v1 \
    --base-model Qwen/Qwen2.5-1.5B-Instruct \
    --min-agreement 0.85 \
    --max-invariant-violations 0 \
    --output-report reports/llm-distillation/student-lora-v1_eval.json

# 5) promotion gate: model card + privacy eval + invariant eval
python3 training/distillation/promotion_gate.py \
    --manifest training/distillation/promotion_manifest.json
```

## Architectural invariants preserved

- The student is **never** allowed to upgrade past a deterministic-high finding. `eval_against_corpus.py` tracks invariant violations and fails the run if any occur.
- The LLM tier (student or teacher) **only fires inside the ambiguous score band** (`LLM_TIER_MNPI_LOWER ≤ mnpi_score < LLM_TIER_MNPI_UPPER`). The two-tier router is unchanged.
- In `structured_tokens` mode the student sees the same closed-vocabulary outputs the cloud teacher learned to emit — no privacy regression vs `LocalLLMAdjudicator`.

## Privacy posture

- Teacher collection writes a per-call **training ledger** to `${KAYPOH_JOURNAL_DIR}/training_ledger.jsonl` so the auditor can reconstruct exactly which documents went to the teacher.
- `structured_tokens` mode lets you distill on hashes-only data — the trained student never has the chance to memorise raw document text.
- The student inference path is fully local: no outbound network calls.
- Promotion requires `privacy_eval.json` to pass `structured_tokens_default`,
  `remote_raw_text_blocked`, `tenant_consent_required`, and
  `privacy_ledger_recorded`.

## What's intentionally NOT here

- **No ungated student promotion**: `promotion_gate.py` is the promotion decision point.
  It currently records that no adapter is promoted.
- **No multi-tenant fine-tuning**: per-tenant LoRA adapters would require a per-tenant journal sanitisation pipeline that doesn't exist yet. v1 pools across consenting tenants.
- **No quantisation**: the inference path uses bf16/fp32. 4-bit quantisation via `bitsandbytes` is a follow-up once a real adapter exists to measure against.
