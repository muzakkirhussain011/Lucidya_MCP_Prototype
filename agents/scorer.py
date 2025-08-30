# file: agents/scorer.py
from datetime import datetime, timedelta
from app.schema import Prospect
from app.config import MIN_FIT_SCORE

class Scorer:
    """Scores prospects and drops low-quality ones"""
    
    def __init__(self, mcp_registry):
        self.mcp = mcp_registry
        self.store = mcp_registry.get_store_client()
    
    async def run(self, prospect: Prospect) -> Prospect:
        """Score prospect based on various factors"""
        
        score = 0.0
        
        # Industry scoring
        high_value_industries = ["SaaS", "FinTech", "E-commerce", "Healthcare Tech"]
        if prospect.company.industry in high_value_industries:
            score += 0.3
        else:
            score += 0.1
        
        # Size scoring
        if 100 <= prospect.company.size <= 5000:
            score += 0.2  # Sweet spot
        elif prospect.company.size > 5000:
            score += 0.1  # Enterprise, harder to sell
        else:
            score += 0.05  # Too small
        
        # Pain points alignment
        cx_related_pains = ["customer retention", "NPS", "support efficiency", "personalization"]
        matching_pains = sum(
            1 for pain in prospect.company.pains 
            if any(keyword in pain.lower() for keyword in cx_related_pains)
        )
        score += min(0.3, matching_pains * 0.1)
        
        # Facts freshness
        fresh_facts = 0
        stale_facts = 0
        now = datetime.utcnow()
        
        for fact in prospect.facts:
            age_hours = (now - fact.collected_at).total_seconds() / 3600
            if age_hours > fact.ttl_hours:
                stale_facts += 1
            else:
                fresh_facts += 1
        
        if fresh_facts > 0:
            score += min(0.2, fresh_facts * 0.05)
        
        # Confidence from facts
        if prospect.facts:
            avg_confidence = sum(f.confidence for f in prospect.facts) / len(prospect.facts)
            score += avg_confidence * 0.2
        
        # Normalize score
        prospect.fit_score = min(1.0, score)
        
        # Decision
        if prospect.fit_score < MIN_FIT_SCORE:
            prospect.status = "dropped"
            prospect.dropped_reason = f"Low fit score: {prospect.fit_score:.2f}"
        elif stale_facts > fresh_facts:
            prospect.status = "dropped"
            prospect.dropped_reason = f"Stale facts: {stale_facts}/{len(prospect.facts)}"
        else:
            prospect.status = "scored"
        
        await self.store.save_prospect(prospect)
        return prospect