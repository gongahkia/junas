from sentence_transformers import SentenceTransformer
import numpy as np
import sys
from pathlib import Path
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from helper.training_corpus import load_documents_from_batches

# Need to load actual texts from docs/json/batch*.json
public_texts = []
violation_texts = []
all_texts = []  # all sentences regardless of label, for IsolationForest (unknown unknowns detection)
failed_batches = []

data_dir = Path("docs/json")
try:
    documents = load_documents_from_batches(data_dir)
except Exception as e:
    failed_batches.append((str(data_dir), str(e)))
    documents = []
    print(f"[WARN] Failed to load batch corpus from {data_dir}: {e}")

for doc in tqdm(documents, desc="Loading batch documents for embeddings", unit="doc"):
    for sentence in doc["sentences"]:
        label = sentence["label"].lower()
        text = sentence["text"]
        if label == "non":
            public_texts.append(text)
        elif label in ["low", "high"]:
            violation_texts.append(text)
        if text:
            all_texts.append(text)

print(f"Loaded {len(public_texts)} public, {len(violation_texts)} violation, {len(all_texts)} total sentences.")
if failed_batches:
    print(f"[WARN] {len(failed_batches)} batch load(s) failed.")
if not all_texts:
    raise RuntimeError("No valid sentences found in docs/json/batch*.json; cannot generate embeddings.")

model = SentenceTransformer("all-mpnet-base-v2") # mpnet > MiniLM bc more context-aware; embedding quality is important in our case with downstream models

# show_progress_bar=True acts as our nice loading indicator for encoding
print("Generating public embeddings...")
public_embeddings = model.encode(public_texts, batch_size=32, show_progress_bar=True)

print("Generating violation embeddings...")
violation_embeddings = model.encode(violation_texts, batch_size=32, show_progress_bar=True) # batch_size=32 means 32 texts being processed in parallel; smaller so lower risk of crashing

print("Generating all embeddings (for IsolationForest — unknown unknowns detection)...")
all_embeddings = model.encode(all_texts, batch_size=32, show_progress_bar=True)

np.save("public_embeddings.npy", public_embeddings)
np.save("violation_embeddings.npy", violation_embeddings)
np.save("all_embeddings.npy", all_embeddings)
print("Saved embeddings successfully.")
