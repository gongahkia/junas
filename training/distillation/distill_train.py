#!/usr/bin/env python3
"""LoRA fine-tune a small base model on collected teacher verdicts (item 29 step b).

Reads the JSONL produced by `teacher_collector.py`, constructs (system + user, target)
pairs where the target is the teacher's canonical JSON response, and LoRA-tunes the
configured base model with structured-JSON output supervision.

Heavy ML deps (transformers, peft, accelerate, bitsandbytes-for-quant) are LAZILY
imported inside `train()` so `--dry-run` works on a clean Python interpreter that
only has the deterministic engine deps installed. This is deliberate: the trainer
script lives in `training/` but should be inspectable + dataset-validatable from any
dev box; the actual training run happens on a GPU box where these deps are present.

Default base model: `Qwen/Qwen2.5-1.5B-Instruct`. Override via `--base-model`.
Override the LoRA target modules with `--lora-target-modules` (default is the
standard "q_proj,k_proj,v_proj,o_proj" set for Qwen / Llama-style architectures).

Usage:
    # validate the dataset, no training run (no GPU required)
    python3 training/distillation/distill_train.py \\
        --dataset training/distillation/teacher_verdicts.jsonl --dry-run

    # actual fine-tune on a GPU box (needs torch + transformers + peft installed)
    python3 training/distillation/distill_train.py \\
        --dataset training/distillation/teacher_verdicts.jsonl \\
        --output training/distillation/student-lora-v1 \\
        --base-model Qwen/Qwen2.5-1.5B-Instruct

Exit codes:
    0  training (or --dry-run validation) succeeded
    1  dataset invalid / training failed
    2  required dep missing (only when --dry-run is NOT set)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


@dataclass(frozen=True)
class DatasetRow:
    """Validated training example. The user_content is the EXACT user-turn string
    the teacher saw; the target is the canonical JSON the student must learn to
    emit. The dataset builder validates these are well-formed before training."""
    system_prompt: str
    user_content: str
    target: str
    input_mode: str
    doc_id: str


@dataclass
class DatasetStats:
    rows: int
    by_input_mode: dict[str, int]
    by_document_type: dict[str, int]
    by_risk_label: dict[str, int]
    max_user_chars: int
    max_target_chars: int
    skipped_rows: int


def _load_dataset_rows(jsonl_path: Path) -> tuple[list[DatasetRow], DatasetStats, list[str]]:
    """Parse the teacher JSONL and convert each row to a DatasetRow. Skips rows that
    are malformed or have status != 'adjudicated' (mock/error teacher outputs are
    valid in their own right but not training-grade). Returns the rows, summary
    stats, and any warning strings for the operator."""
    from training.distillation.prompts import (
        SYSTEM_PROMPT_RAW_TEXT,
        SYSTEM_PROMPT_STRUCTURED_TOKENS,
        build_target,
    )

    rows: list[DatasetRow] = []
    by_mode: dict[str, int] = {}
    by_doc_type: dict[str, int] = {}
    by_label: dict[str, int] = {}
    max_user = 0
    max_target = 0
    skipped = 0
    warnings: list[str] = []

    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line_num, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                warnings.append(f"line {line_num}: JSON decode failure: {exc}")
                skipped += 1
                continue

            mode = str(raw.get("input_mode", "raw_text"))
            if mode == "raw_text":
                system_prompt = SYSTEM_PROMPT_RAW_TEXT
            elif mode == "structured_tokens":
                system_prompt = SYSTEM_PROMPT_STRUCTURED_TOKENS
            else:
                warnings.append(f"line {line_num}: unknown input_mode {mode!r}; skipping")
                skipped += 1
                continue

            user_content = raw.get("user_content")
            verdict = raw.get("teacher_verdict", {}) or {}
            if not isinstance(user_content, str) or not isinstance(verdict, dict):
                warnings.append(f"line {line_num}: malformed user_content or teacher_verdict; skipping")
                skipped += 1
                continue
            if str(verdict.get("status", "")) != "adjudicated":
                warnings.append(
                    f"line {line_num}: teacher_verdict status={verdict.get('status')!r}; skipping"
                )
                skipped += 1
                continue

            target = build_target(verdict)
            rows.append(DatasetRow(
                system_prompt=system_prompt,
                user_content=user_content,
                target=target,
                input_mode=mode,
                doc_id=str(raw.get("doc_id", f"row-{line_num}")),
            ))
            by_mode[mode] = by_mode.get(mode, 0) + 1
            by_doc_type[raw.get("document_type", "generic")] = (
                by_doc_type.get(raw.get("document_type", "generic"), 0) + 1
            )
            label = str(verdict.get("risk_label", "")) or "SAFE"
            by_label[label] = by_label.get(label, 0) + 1
            max_user = max(max_user, len(user_content))
            max_target = max(max_target, len(target))

    stats = DatasetStats(
        rows=len(rows),
        by_input_mode=by_mode,
        by_document_type=by_doc_type,
        by_risk_label=by_label,
        max_user_chars=max_user,
        max_target_chars=max_target,
        skipped_rows=skipped,
    )
    return rows, stats, warnings


def _validate_dataset(rows: list[DatasetRow], stats: DatasetStats, *, min_rows: int) -> list[str]:
    """Cheap sanity checks. Anything trivially bad about the dataset surfaces here
    BEFORE we spend any GPU time."""
    errors: list[str] = []
    if stats.rows < min_rows:
        errors.append(
            f"dataset has {stats.rows} rows; minimum {min_rows} required. Run "
            "teacher_collector.py with more corpora or lower --min-rows."
        )
    if stats.rows > 0 and len(stats.by_risk_label) == 1:
        only = list(stats.by_risk_label.keys())[0]
        errors.append(
            f"dataset only contains a single risk_label ({only}); the student will "
            "trivially predict that label. Collect more diverse teacher verdicts."
        )
    if stats.max_target_chars == 0:
        errors.append("dataset has at least one empty target string; teacher emitted no JSON")
    return errors


def train(
    *,
    rows: list[DatasetRow],
    output_dir: Path,
    base_model: str,
    epochs: int,
    learning_rate: float,
    lora_rank: int,
    lora_alpha: int,
    lora_target_modules: list[str],
    max_seq_length: int,
    seed: int,
) -> dict[str, Any]:
    """Actually run the LoRA fine-tune. Heavy imports are deferred to here so
    --dry-run never touches the ML stack."""
    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            DataCollatorForLanguageModeling,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise RuntimeError(
            "training requires `torch`, `transformers`, `peft`, and `datasets`. "
            f"Install them with `pip install junas[server,training]`. (missing: {exc})"
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def _format_example(row: DatasetRow) -> str:
        # generic chat-template fallback: most instruction-tuned bases support
        # apply_chat_template, but the trainer should still run on bases that don't.
        if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
            messages = [
                {"role": "system", "content": row.system_prompt},
                {"role": "user", "content": row.user_content},
                {"role": "assistant", "content": row.target},
            ]
            return tokenizer.apply_chat_template(messages, tokenize=False)
        return (
            f"<|system|>\n{row.system_prompt}\n"
            f"<|user|>\n{row.user_content}\n"
            f"<|assistant|>\n{row.target}\n"
        )

    examples = [{"text": _format_example(r)} for r in rows]
    dataset = Dataset.from_list(examples).shuffle(seed=seed)

    def _tokenize(batch):
        out = tokenizer(
            batch["text"], truncation=True, max_length=max_seq_length, padding="longest",
        )
        out["labels"] = out["input_ids"].copy()
        return out

    dataset = dataset.map(_tokenize, batched=True, remove_columns=["text"])

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        trust_remote_code=True,
    )
    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=lora_rank,
        lora_alpha=lora_alpha,
        lora_dropout=0.05,
        target_modules=lora_target_modules,
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    output_dir.mkdir(parents=True, exist_ok=True)
    args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        learning_rate=learning_rate,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        logging_steps=5,
        save_strategy="epoch",
        bf16=torch.cuda.is_available(),
        seed=seed,
        report_to=[],
    )
    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    trainer = Trainer(model=model, args=args, train_dataset=dataset, data_collator=collator)
    trainer.train()
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    return {
        "base_model": base_model,
        "rows_trained_on": len(rows),
        "epochs": epochs,
        "lora_rank": lora_rank,
        "output_dir": str(output_dir),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LoRA-distill a student from teacher verdicts")
    parser.add_argument("--dataset", type=Path, required=True, help="teacher JSONL path")
    parser.add_argument("--output", type=Path, default=Path("training/distillation/student-lora"),
                        help="output directory for the LoRA adapter")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument(
        "--lora-target-modules", default="q_proj,k_proj,v_proj,o_proj",
        help="comma-separated list of attention-projection modules to LoRA-adapt",
    )
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--min-rows", type=int, default=5,
                        help="minimum rows required to consider training viable")
    parser.add_argument("--dry-run", action="store_true",
                        help="parse + validate the dataset and print stats; do not train.")
    args = parser.parse_args(argv)

    dataset_path = args.dataset if args.dataset.is_absolute() else (REPO_ROOT / args.dataset).resolve()
    if not dataset_path.exists():
        print(f"dataset missing: {dataset_path}", file=sys.stderr)
        return 1

    rows, stats, warnings = _load_dataset_rows(dataset_path)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)

    validation_errors = _validate_dataset(rows, stats, min_rows=args.min_rows)
    print(json.dumps({
        "dataset": str(dataset_path),
        "stats": {
            "rows": stats.rows,
            "skipped_rows": stats.skipped_rows,
            "by_input_mode": stats.by_input_mode,
            "by_document_type": stats.by_document_type,
            "by_risk_label": stats.by_risk_label,
            "max_user_chars": stats.max_user_chars,
            "max_target_chars": stats.max_target_chars,
        },
        "validation_errors": validation_errors,
        "would_train": not args.dry_run and not validation_errors,
    }, indent=2))

    if validation_errors:
        return 1
    if args.dry_run:
        return 0

    try:
        result = train(
            rows=rows,
            output_dir=(args.output if args.output.is_absolute() else (REPO_ROOT / args.output).resolve()),
            base_model=args.base_model,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            lora_rank=args.lora_rank,
            lora_alpha=args.lora_alpha,
            lora_target_modules=[m.strip() for m in args.lora_target_modules.split(",") if m.strip()],
            max_seq_length=args.max_seq_length,
            seed=args.seed,
        )
    except RuntimeError as exc:
        print(f"training prerequisite missing: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({"result": result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
