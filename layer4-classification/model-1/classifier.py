import os
import torch
import pandas as pd
from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments
from torch.utils.data import Dataset

MODEL_NAME = "ProsusAI/finbert"
MAX_SEQ_LEN = 512
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints")

class MNPIDataset(Dataset): # expects df with columns: text, label
    def __init__(self, texts, labels, tokenizer, max_len=MAX_SEQ_LEN):
        # We manually tokenize in batches to show a progress bar
        from tqdm import tqdm
        print("Tokenizing texts for MNPIDataset...")
        input_ids, attention_masks = [], []
        # Process in batches of 1000 for efficiency while showing progress
        batch_size = 1000
        for i in tqdm(range(0, len(texts), batch_size), desc="Tokenizing", unit="batch"):
            batch_texts = texts[i:i + batch_size]
            encoded = tokenizer(batch_texts, truncation=True, padding="max_length", max_length=max_len, return_tensors="pt")
            input_ids.append(encoded["input_ids"])
            attention_masks.append(encoded["attention_mask"])
            
        self.encodings = {
            "input_ids": torch.cat(input_ids, dim=0),
            "attention_mask": torch.cat(attention_masks, dim=0)
        }
        self.labels = torch.tensor(labels, dtype=torch.long)
    def __len__(self):
        return len(self.labels)
    def __getitem__(self, idx):
        item = {k: v[idx] for k, v in self.encodings.items()}
        item["labels"] = self.labels[idx]
        return item

def load_data(csv_path: str) -> tuple: # schema: text,label where label ∈ {0=public, 1=non_public}
    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    from tqdm import tqdm
    # Simulate a small loading bar for reading dataset just so the user sees progress
    texts = [t for t in tqdm(df["text"].tolist(), desc="Reading texts", unit="record")]
    labels = [l for l in tqdm(df["label"].tolist(), desc="Reading labels", unit="record")]
    return texts, labels

def train(train_csv: str, val_csv: str = None, epochs: int = 3, lr: float = 2e-5, batch_size: int = 16):
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)
    train_texts, train_labels = load_data(train_csv)
    train_dataset = MNPIDataset(train_texts, train_labels, tokenizer)
    val_dataset = None
    if val_csv:
        val_texts, val_labels = load_data(val_csv)
        val_dataset = MNPIDataset(val_texts, val_labels, tokenizer)
    args = TrainingArguments(
        output_dir=OUTPUT_DIR, num_train_epochs=epochs, per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size, learning_rate=lr, weight_decay=0.01,
        eval_strategy="epoch" if val_dataset else "no", save_strategy="epoch",
        load_best_model_at_end=bool(val_dataset), logging_steps=50, seed=42,
    )
    trainer = Trainer(model=model, args=args, train_dataset=train_dataset, eval_dataset=val_dataset)
    trainer.train()
    trainer.save_model(os.path.join(OUTPUT_DIR, "best"))
    tokenizer.save_pretrained(os.path.join(OUTPUT_DIR, "best"))
    return trainer

if __name__ == "__main__":
    import sys
    train_path = sys.argv[1] if len(sys.argv) > 1 else "data/train.csv"
    val_path = sys.argv[2] if len(sys.argv) > 2 else None
    train(train_path, val_path)
