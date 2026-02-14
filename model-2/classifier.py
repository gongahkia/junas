import os
import torch
import pandas as pd
import numpy as np
from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments
from torch.utils.data import Dataset

MODEL_NAME = "bert-base-uncased"
MAX_SEQ_LEN = 512
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints")

class ViolationDataset(Dataset): # expects df with columns: text, label (violation corpus only, no public/safe data)
    def __init__(self, texts, labels, tokenizer, max_len=MAX_SEQ_LEN):
        self.encodings = tokenizer(texts, truncation=True, padding=True, max_length=max_len, return_tensors="pt")
        self.labels = torch.tensor(labels, dtype=torch.long)
    def __len__(self):
        return len(self.labels)
    def __getitem__(self, idx):
        item = {k: v[idx] for k, v in self.encodings.items()}
        item["labels"] = self.labels[idx]
        return item

def load_data(csv_path: str) -> tuple: # schema: text,label where label ∈ {0=low_risk, 1=high_risk}
    df = pd.read_csv(csv_path)
    return df["text"].tolist(), df["label"].tolist()

def compute_class_weights(labels: list) -> torch.Tensor: # inverse frequency weighting for 90/10 imbalance
    counts = np.bincount(labels)
    weights = 1.0 / counts
    weights = weights / weights.sum() * len(counts) # normalize
    return torch.tensor(weights, dtype=torch.float)

class WeightedTrainer(Trainer): # custom trainer with class-weighted loss
    def __init__(self, class_weights=None, **kwargs):
        super().__init__(**kwargs)
        self.class_weights = class_weights
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits
        loss_fn = torch.nn.CrossEntropyLoss(weight=self.class_weights.to(logits.device) if self.class_weights is not None else None)
        loss = loss_fn(logits, labels)
        return (loss, outputs) if return_outputs else loss

def train(train_csv: str, val_csv: str = None, epochs: int = 5, lr: float = 2e-5, batch_size: int = 16):
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)
    train_texts, train_labels = load_data(train_csv)
    class_weights = compute_class_weights(train_labels)
    train_dataset = ViolationDataset(train_texts, train_labels, tokenizer)
    val_dataset = None
    if val_csv:
        val_texts, val_labels = load_data(val_csv)
        val_dataset = ViolationDataset(val_texts, val_labels, tokenizer)
    args = TrainingArguments(
        output_dir=OUTPUT_DIR, num_train_epochs=epochs, per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size, learning_rate=lr, weight_decay=0.01,
        eval_strategy="epoch" if val_dataset else "no", save_strategy="epoch",
        load_best_model_at_end=bool(val_dataset), logging_steps=50, seed=42,
    )
    trainer = WeightedTrainer(class_weights=class_weights, model=model, args=args, train_dataset=train_dataset, eval_dataset=val_dataset)
    trainer.train()
    trainer.save_model(os.path.join(OUTPUT_DIR, "best"))
    tokenizer.save_pretrained(os.path.join(OUTPUT_DIR, "best"))
    return trainer

if __name__ == "__main__":
    import sys
    train_path = sys.argv[1] if len(sys.argv) > 1 else "data/train.csv"
    val_path = sys.argv[2] if len(sys.argv) > 2 else None
    train(train_path, val_path)
