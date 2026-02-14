from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("all-mpnet-base-v2") # mpnet > MiniLM bc more context-aware; embedding quality is important in our case with downstream models

public_embeddings = model.encode(public_texts, batch_size=32, show_progress_bar=True)
violation_embeddings = model.encode(violation_texts, batch_size=32, show_progress_bar=True) # batch_size=32 means 32 texts being processed in parallel; smaller so lower risk of crashing

np.save("public_embeddings.npy", public_embeddings)
np.save("violation_embeddings.npy", violation_embeddings)