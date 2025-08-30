# file: scripts/seed_vectorstore.py
#!/usr/bin/env python3
"""Seed the vector store with initial data"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vector.store import VectorStore
from vector.embeddings import get_embedding_model
from app.config import DATA_DIR

def seed_vectorstore():
    """Build and persist the initial vector index"""
    
    print("Initializing vector store...")
    store = VectorStore()
    model = get_embedding_model()
    
    # Load companies
    companies_file = DATA_DIR / "companies.json"
    if not companies_file.exists():
        print(f"Error: {companies_file} not found")
        return
    
    with open(companies_file) as f:
        companies = json.load(f)
    
    print(f"Loading {len(companies)} companies...")
    
    texts = []
    metadata = []
    
    for company in companies:
        # Company description
        desc = f"{company['name']} is a {company['industry']} company with {company['size']} employees"
        texts.append(desc)
        metadata.append({
            "company_id": company["id"],
            "type": "description",
            "text": desc
        })
        
        # Pain points
        for pain in company.get("pains", []):
            pain_text = f"{company['name']} challenge: {pain}"
            texts.append(pain_text)
            metadata.append({
                "company_id": company["id"],
                "type": "pain",
                "text": pain_text
            })
        
        # Notes
        for note in company.get("notes", []):
            note_text = f"{company['name']}: {note}"
            texts.append(note_text)
            metadata.append({
                "company_id": company["id"],
                "type": "note",
                "text": note_text
            })
    
    print(f"Encoding {len(texts)} documents...")
    embeddings = model.encode(texts)
    
    print("Adding to index...")
    store.add(embeddings, metadata)
    
    print(f"Vector store initialized with {len(texts)} documents")
    print(f"Index saved to: {store.index_path}")
    
    # Test retrieval
    print("\nTesting retrieval...")
    from vector.retriever import Retriever
    retriever = Retriever()
    
    for company in companies[:1]:  # Test with first company
        results = retriever.retrieve(company["id"], k=3)
        print(f"\nTop results for {company['name']}:")
        for r in results:
            print(f"  - {r['text'][:80]}... (score: {r.get('score', 0):.3f})")

if __name__ == "__main__":
    seed_vectorstore()