# file: agents/enricher.py
from datetime import datetime
from app.schema import Prospect, Fact
from app.config import FACT_TTL_HOURS
import uuid

class Enricher:
    """Enriches prospects with facts from search"""
    
    def __init__(self, mcp_registry):
        self.mcp = mcp_registry
        self.search = mcp_registry.get_search_client()
        self.store = mcp_registry.get_store_client()
    
    async def run(self, prospect: Prospect) -> Prospect:
        """Enrich prospect with facts"""
        
        # Search for company information
        queries = [
            f"{prospect.company.name} customer experience",
            f"{prospect.company.name} {prospect.company.industry} challenges",
            f"{prospect.company.domain} support contact"
        ]
        
        facts = []
        
        for query in queries:
            results = await self.search.query(query)
            
            for result in results[:2]:  # Top 2 per query
                fact = Fact(
                    id=str(uuid.uuid4()),
                    source=result["source"],
                    text=result["text"],
                    collected_at=datetime.utcnow(),
                    ttl_hours=FACT_TTL_HOURS,
                    confidence=result.get("confidence", 0.7),
                    company_id=prospect.company.id
                )
                facts.append(fact)
                await self.store.save_fact(fact)
        
        # Add company pain points as facts
        for pain in prospect.company.pains:
            fact = Fact(
                id=str(uuid.uuid4()),
                source="seed_data",
                text=f"Known pain point: {pain}",
                collected_at=datetime.utcnow(),
                ttl_hours=FACT_TTL_HOURS * 2,  # Seed data lasts longer
                confidence=0.9,
                company_id=prospect.company.id
            )
            facts.append(fact)
            await self.store.save_fact(fact)
        
        prospect.facts = facts
        prospect.status = "enriched"
        await self.store.save_prospect(prospect)
        
        return prospect