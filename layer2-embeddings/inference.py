import sys
import os
import hashlib
from collections import OrderedDict
from threading import Lock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import get_config_val
from sentence_transformers import SentenceTransformer
import numpy as np

MODEL_NAME = get_config_val("embeddings", "model_name", "EMBEDDINGS_MODEL", "all-mpnet-base-v2", str)
CACHE_SIZE = get_config_val("embeddings", "cache_size", "EMBEDDINGS_CACHE_SIZE", 512, int)

class EmbeddingsEncoder:
    """Singleton for inference-time embedding generation."""
    _instance = None

    def __init__(self, model_name: str = MODEL_NAME):
        # Load model only once
        self.model = SentenceTransformer(model_name)
        self.cache_size = max(0, int(CACHE_SIZE))
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._cache_lock = Lock()

    @classmethod
    def get_instance(cls, model_name: str = MODEL_NAME):
        if cls._instance is None:
            cls._instance = cls(model_name)
        return cls._instance

    def encode(self, text: str) -> np.ndarray:
        """
        Encodes a single string into a Sentence-BERT embedding.
        Returns a 1D numpy array of shape (768,).
        """
        cache_key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if self.cache_size > 0:
            with self._cache_lock:
                cached = self._cache.get(cache_key)
                if cached is not None:
                    self._cache.move_to_end(cache_key)
                    return cached.copy()

        vec = self.model.encode(text)

        if self.cache_size > 0:
            with self._cache_lock:
                self._cache[cache_key] = np.array(vec, copy=True)
                self._cache.move_to_end(cache_key)
                while len(self._cache) > self.cache_size:
                    self._cache.popitem(last=False)
        return vec

# Provide a ready-to-use callable matching the user's "callable at runtime" requirement
def encode_text(text: str) -> np.ndarray:
    """Convenience callable for api/main.py to encode text at runtime."""
    encoder = EmbeddingsEncoder.get_instance()
    return encoder.encode(text)
