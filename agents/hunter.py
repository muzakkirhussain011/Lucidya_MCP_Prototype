# file: agents/hunter.py
import json
from typing import List, Optional
from app.schema import Company, Prospect
from app.config import COMPANIES_FILE

class Hunter:
    """Loads seed companies and creates prospects"""
    
    def __init__(self, mcp_registry):
        self.mcp = mcp_registry
        self.store = mcp_registry.get_store_client()
    
    async def run(self, company_ids: Optional[List[str]] = None) -> List[Prospect]:
        """Load companies and create prospects"""
        
        # Load from seed file
        with open(COMPANIES_FILE) as f:
            companies_data = json.load(f)
        
        prospects = []
        
        for company_data in companies_data:
            # Filter by IDs if specified
            if company_ids and company_data["id"] not in company_ids:
                continue
            
            company = Company(**company_data)
            
            # Create prospect
            prospect = Prospect(
                id=company.id,
                company=company,
                status="new"
            )
            
            # Save to store
            await self.store.save_prospect(prospect)
            prospects.append(prospect)
        
        return prospects