# file: vector/retriever.py
from typing import List, Dict
from vector.store import VectorStore
from vector.embeddings import get_embedding_model

class Retriever:
    """Retrieves relevant facts from vector store"""
    
    def __init__(self):
        self.store = VectorStore()
        self.embedding_model = get_embedding_model()
    
    def retrieve(self, company_id: str, k: int = 5) -> List[Dict]:
        """Retrieve relevant facts for a company"""
        
        # Build query
        query = f"customer experience insights for company {company_id}"
        
        # Encode query
        query_embedding = self.embedding_model.encode([query])[0]
        
        # Search
        results = self.store.search(query_embedding, k=k*2)  # Get more, filter later
        
        # Filter by company
        company_results = [
            r for r in results 
            if r.get("company_id") == company_id
        ]
        
        # If not enough company-specific, include general
        if len(company_results) < k:
            for r in results:
                if r not in company_results:
                    company_results.append(r)
                if len(company_results) >= k:
                    break
        
        return company_results[:k]