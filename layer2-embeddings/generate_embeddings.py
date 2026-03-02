from sentence_transformers import SentenceTransformer
import numpy as np
import os
import json
from tqdm import tqdm

# Need to load actual texts from docs/json
public_texts = []
violation_texts = []
all_texts = []  # all sentences regardless of label, for IsolationForest (unknown unknowns detection)
failed_files = []

json_dir = "docs/json"
if os.path.exists(json_dir):
    files = [f for f in os.listdir(json_dir) if f.endswith(".json")]
    for filename in tqdm(files, desc="Loading JSON documents for embeddings", unit="file"):
        filepath = os.path.join(json_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                for sentence in data.get("document_sentence_array", []):
                    # "non" = public, "low"/"high" = violation
                    label = sentence.get("label", "").lower()
                    text = sentence.get("text", "")
                    if label == "non":
                        public_texts.append(text)
                    elif label in ["low", "high"]:
                        violation_texts.append(text)
                    if text:
                        all_texts.append(text)
            except Exception as e:
                failed_files.append((filename, str(e)))
                print(f"[WARN] Skipping malformed JSON file {filename}: {e}")

print(f"Loaded {len(public_texts)} public, {len(violation_texts)} violation, {len(all_texts)} total sentences.")
if failed_files:
    print(f"[WARN] {len(failed_files)} file(s) were skipped due to parse errors.")
if not all_texts:
    raise RuntimeError("No valid sentences found in docs/json; cannot generate embeddings.")

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
