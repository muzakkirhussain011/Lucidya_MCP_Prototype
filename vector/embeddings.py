# file: vector/embeddings.py
from sentence_transformers import SentenceTransformer
import numpy as np
from app.config import EMBEDDING_MODEL, EMBEDDING_DIM

class EmbeddingModel:
    """Manages sentence transformer embeddings"""
    
    def __init__(self):
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the embedding model"""
        try:
            self.model = SentenceTransformer(EMBEDDING_MODEL)
        except Exception as e:
            print(f"Warning: Could not load embedding model: {e}")
            # Fallback to random embeddings for testing
            self.model = None
    
    def encode(self, texts):
        """Encode texts to embeddings"""
        if self.model:
            embeddings = self.model.encode(texts, normalize_embeddings=True)
            return embeddings
        else:
            # Fallback: random embeddings
            return np.random.randn(len(texts), EMBEDDING_DIM).astype(np.float32)

# Singleton
_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = EmbeddingModel()
    return _embedding_model