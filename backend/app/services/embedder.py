from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List

_model = None

def get_embedder() -> SentenceTransformer:
    global _model
    if _model is None:
        # Downloads model once (~90MB) and keeps it in memory
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def generate_embeddings(texts: List[str]) -> np.ndarray:
    model = get_embedder()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return embeddings.astype(np.float32)