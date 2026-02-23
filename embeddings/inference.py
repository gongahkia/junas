from sentence_transformers import SentenceTransformer
import numpy as np

class EmbeddingsEncoder:
    """Singleton for inference-time embedding generation."""
    _instance = None

    def __init__(self, model_name: str = "all-mpnet-base-v2"):
        # Load model only once
        self.model = SentenceTransformer(model_name)

    @classmethod
    def get_instance(cls, model_name: str = "all-mpnet-base-v2"):
        if cls._instance is None:
            cls._instance = cls(model_name)
        return cls._instance

    def encode(self, text: str) -> np.ndarray:
        """
        Encodes a single string into a Sentence-BERT embedding.
        Returns a 1D numpy array of shape (768,).
        """
        # encode() returns a numpy array by default
        return self.model.encode(text)

# Provide a ready-to-use callable matching the user's "callable at runtime" requirement
def encode_text(text: str) -> np.ndarray:
    """Convenience callable for api/main.py to encode text at runtime."""
    encoder = EmbeddingsEncoder.get_instance()
    return encoder.encode(text)
