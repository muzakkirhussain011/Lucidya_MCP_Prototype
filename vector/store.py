# file: vector/store.py
import json
import pickle
from pathlib import Path
import numpy as np
import faiss
from app.config import VECTOR_INDEX_PATH, EMBEDDING_DIM, DATA_DIR

class VectorStore:
    """FAISS vector store with persistence"""
    
    def __init__(self):
        self.index_path = Path(VECTOR_INDEX_PATH)
        self.metadata_path = self.index_path.with_suffix(".meta")
        self.index = None
        self.metadata = []
        self._initialize()
    
    def _initialize(self):
        """Initialize or load the index"""
        if self.index_path.exists():
            self._load()
        else:
            self._create_new()
    
    def _create_new(self):
        """Create a new FAISS index"""
        # Using IndexFlatIP for inner product (cosine with normalized vectors)
        self.index = faiss.IndexFlatIP(EMBEDDING_DIM)
        self.metadata = []
    
    def _load(self):
        """Load existing index and metadata"""
        try:
            self.index = faiss.read_index(str(self.index_path))
            
            if self.metadata_path.exists():
                with open(self.metadata_path, "rb") as f:
                    self.metadata = pickle.load(f)
        except Exception as e:
            print(f"Could not load index: {e}")
            self._create_new()
    
    def save(self):
        """Persist index and metadata"""
        if self.index:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            faiss.write_index(self.index, str(self.index_path))
            
            with open(self.metadata_path, "wb") as f:
                pickle.dump(self.metadata, f)
    
    def add(self, embeddings: np.ndarray, metadata: list):
        """Add embeddings with metadata"""
        if self.index is None:
            self._create_new()
        
        # Normalize embeddings for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized = embeddings / (norms + 1e-10)
        
        self.index.add(normalized.astype(np.float32))
        self.metadata.extend(metadata)
        self.save()
    
    def search(self, query_embedding: np.ndarray, k: int = 5):
        """Search for similar vectors"""
        if self.index is None or self.index.ntotal == 0:
            return []
        
        # Normalize query
        norm = np.linalg.norm(query_embedding)
        normalized = query_embedding / (norm + 1e-10)
        
        # Search
        scores, indices = self.index.search(
            normalized.reshape(1, -1).astype(np.float32), 
            min(k, self.index.ntotal)
        )
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.metadata):
                result = self.metadata[idx].copy()
                result["score"] = float(score)
                results.append(result)
        
        return results
    
    def rebuild_index(self):
        """Rebuild the index from scratch"""
        self._create_new()
        
        # Load seed data and re-embed
        companies_file = DATA_DIR / "companies.json"
        if companies_file.exists():
            with open(companies_file) as f:
                companies = json.load(f)
            
            from vector.embeddings import get_embedding_model
            model = get_embedding_model()
            
            texts = []
            metadata = []
            
            for company in companies:
                # Add company description
                desc = f"{company['name']} is a {company['industry']} company with {company['size']} employees"
                texts.append(desc)
                metadata.append({
                    "company_id": company["id"],
                    "type": "description",
                    "text": desc
                })
                
                # Add pain points
                for pain in company.get("pains", []):
                    text = f"{company['name']} pain point: {pain}"
                    texts.append(text)
                    metadata.append({
                        "company_id": company["id"],
                        "type": "pain",
                        "text": text
                    })
                
                # Add notes
                for note in company.get("notes", []):
                    texts.append(note)
                    metadata.append({
                        "company_id": company["id"],
                        "type": "note",
                        "text": note
                    })
            
            if texts:
                embeddings = model.encode(texts)
                self.add(embeddings, metadata)
    
    def is_initialized(self):
        """Check if the store is initialized"""
        return self.index is not None and self.index.ntotal > 0