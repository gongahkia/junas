from sentence_transformers import SentenceTransformer
import numpy as np
import os
import json
from tqdm import tqdm

# Need to load actual texts from docs/json
public_texts = []
violation_texts = []

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
            except Exception:
                pass

print(f"Loaded {len(public_texts)} public sentences and {len(violation_texts)} violation sentences.")

model = SentenceTransformer("all-mpnet-base-v2") # mpnet > MiniLM bc more context-aware; embedding quality is important in our case with downstream models

# show_progress_bar=True acts as our nice loading indicator for encoding
print("Generating public embeddings...")
public_embeddings = model.encode(public_texts, batch_size=32, show_progress_bar=True)

print("Generating violation embeddings...")
violation_embeddings = model.encode(violation_texts, batch_size=32, show_progress_bar=True) # batch_size=32 means 32 texts being processed in parallel; smaller so lower risk of crashing

np.save("public_embeddings.npy", public_embeddings)
np.save("violation_embeddings.npy", violation_embeddings)
print("Saved embeddings successfully.")