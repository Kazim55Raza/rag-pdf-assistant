import faiss
import numpy as np
import pickle
from typing import List, Dict, Any

def create_faiss_index(chunks: List[Dict[str, Any]], embeddings: np.ndarray) -> bytes:
    """
    Creates an in-memory FAISS index and packages it with chunk metadata.
    Returns bytes suitable for storing in Supabase Storage.
    """
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    
    # Serialize FAISS index
    faiss_bytes = faiss.serialize_index(index)
    
    # Package index + text metadata together
    package = {
        "faiss_index": faiss_bytes,
        "chunks": chunks
    }
    return pickle.dumps(package)

def search_faiss_index(index_package_bytes: bytes, query_embedding: np.ndarray, top_k: int = 4) -> List[Dict[str, Any]]:
    """
    Unpacks FAISS bytes from Supabase and retrieves top-k matching text chunks.
    """
    package = pickle.loads(index_package_bytes)
    faiss_bytes = package["faiss_index"]
    chunks = package["chunks"]
    
    index = faiss.deserialize_index(faiss_bytes)
    
    # Search index
    distances, indices = index.search(query_embedding.reshape(1, -1), top_k)
    
    results = []
    for idx in indices[0]:
        if 0 <= idx < len(chunks):
            results.append(chunks[idx])
            
    return results