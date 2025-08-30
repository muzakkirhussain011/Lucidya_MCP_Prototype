from __future__ import annotations
import logging
from typing import List, Dict
from app.domain_models import Company

log = logging.getLogger("orchestrator")

def normalize_bullets(md: str) -> str:
    """Ensure markdown text is properly formatted as bullets."""
    lines = [ln.rstrip() for ln in (md or "").splitlines()]
    out = []
    for ln in lines:
        if not ln:
            continue
        # Ensure line starts with bullet
        if not ln.lstrip().startswith("- "):
            ln = "- " + ln.lstrip("- ").strip()
        out.append(ln)
    return "\n".join(out).strip()

class CompanyEnrichmentAgent:
    def synthesize(self, company: Company, hits: List[Dict]) -> str:
        """Build context for LLM summarization from retrieval hits."""
        log.info("enrichment: synthesize company=%s hits=%d", company.name, len(hits or []))
        
        # Company header
        header = f"Company: {company.name} (industry: {company.industry}, region: {company.region}, size: {company.size})"
        
        # Build context from hits
        ctx_lines = []
        if hits:
            for h in hits:
                url = h.get("url") or h.get("href") or ""
                text = (h.get("text") or h.get("content") or h.get("body") or "")[:400]
                score = h.get("score")
                if text.strip():  # Only include non-empty text
                    if score is not None:
                        ctx_lines.append(f"- [{score:.2f}] {text} ({url})")
                    else:
                        ctx_lines.append(f"- {text} ({url})")
        
        # If no retrieval hits, provide basic context
        if not ctx_lines:
            log.warning("enrichment: no retrieval hits for %s; using metadata-only context", company.name)
            ctx_lines = [
                f"- Company operates in {company.industry} sector with {company.size} employees",
                f"- Based in {company.region} region",
                f"- Website: {company.website}",
            ]
            if company.challenges:
                ctx_lines.append(f"- Known challenges: {', '.join(company.challenges[:2])}")
            if company.tech_stack:
                ctx_lines.append(f"- Technology stack includes: {', '.join(company.tech_stack[:3])}")
        
        context = "\n".join(ctx_lines)
        
        # Build full prompt
        out = f"""{header}

Context and evidence:
{context}

Task: Generate 5-8 bullet points about customer experience opportunities and challenges for {company.name}. 
Focus on practical insights that would be relevant for a CX analytics platform.
Include specific pain points and potential solutions where possible.
"""
        
        log.info("enrichment: built context chars=%d", len(out))
        return out