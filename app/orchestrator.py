# file: app/orchestrator.py
import asyncio
from typing import List, AsyncGenerator, Optional
from app.schema import Prospect, PipelineEvent, Company
from app.logging_utils import log_event, logger
from agents import (
    Hunter, Enricher, Contactor, Scorer, 
    Writer, Compliance, Sequencer, Curator
)
from mcp.registry import MCPRegistry

class Orchestrator:
    def __init__(self):
        self.mcp = MCPRegistry()
        self.hunter = Hunter(self.mcp)
        self.enricher = Enricher(self.mcp)
        self.contactor = Contactor(self.mcp)
        self.scorer = Scorer(self.mcp)
        self.writer = Writer(self.mcp)
        self.compliance = Compliance(self.mcp)
        self.sequencer = Sequencer(self.mcp)
        self.curator = Curator(self.mcp)
    
    async def run_pipeline(self, company_ids: Optional[List[str]] = None) -> AsyncGenerator[dict, None]:
        """Run the full pipeline with streaming events"""
        
        # Hunter phase
        yield log_event("hunter", "Starting prospect discovery", "agent_start")
        prospects = await self.hunter.run(company_ids)
        yield log_event("hunter", f"Found {len(prospects)} prospects", "agent_end", 
                       {"count": len(prospects)})
        
        for prospect in prospects:
            try:
                # Enricher phase
                yield log_event("enricher", f"Enriching {prospect.company.name}", "agent_start")
                prospect = await self.enricher.run(prospect)
                yield log_event("enricher", f"Added {len(prospect.facts)} facts", "agent_end",
                               {"facts_count": len(prospect.facts)})
                
                # Contactor phase
                yield log_event("contactor", f"Finding contacts for {prospect.company.name}", "agent_start")
                prospect = await self.contactor.run(prospect)
                yield log_event("contactor", f"Found {len(prospect.contacts)} contacts", "agent_end",
                               {"contacts_count": len(prospect.contacts)})
                
                # Scorer phase
                yield log_event("scorer", f"Scoring {prospect.company.name}", "agent_start")
                prospect = await self.scorer.run(prospect)
                yield log_event("scorer", f"Fit score: {prospect.fit_score:.2f}", "agent_end",
                               {"fit_score": prospect.fit_score})
                
                if prospect.status == "dropped":
                    yield log_event("scorer", f"Dropped: {prospect.dropped_reason}", "agent_log")
                    continue
                
                # Writer phase with streaming
                yield log_event("writer", f"Drafting outreach for {prospect.company.name}", "agent_start")
                
                async for event in self.writer.run_streaming(prospect):
                    if event["type"] == "llm_token":
                        yield event
                    elif event["type"] == "llm_done":
                        yield event
                        prospect = event["payload"]["prospect"]
                
                yield log_event("writer", "Draft complete", "agent_end",
                               {"has_summary": bool(prospect.summary),
                                "has_email": bool(prospect.email_draft)})
                
                # Compliance phase
                yield log_event("compliance", f"Checking compliance for {prospect.company.name}", "agent_start")
                prospect = await self.compliance.run(prospect)
                
                if prospect.status == "blocked":
                    yield log_event("compliance", f"Blocked: {prospect.dropped_reason}", "policy_block",
                                   {"reason": prospect.dropped_reason})
                    continue
                else:
                    yield log_event("compliance", "Compliance passed", "policy_pass")
                
                # Sequencer phase
                yield log_event("sequencer", f"Sequencing outreach for {prospect.company.name}", "agent_start")
                prospect = await self.sequencer.run(prospect)
                yield log_event("sequencer", f"Thread created: {prospect.thread_id}", "agent_end",
                               {"thread_id": prospect.thread_id})
                
                # Curator phase
                yield log_event("curator", f"Creating handoff for {prospect.company.name}", "agent_start")
                prospect = await self.curator.run(prospect)
                yield log_event("curator", "Handoff ready", "agent_end",
                               {"prospect_id": prospect.id})
                
            except Exception as e:
                logger.error(f"Pipeline error for {prospect.company.name}: {e}")
                yield log_event("orchestrator", f"Error: {str(e)}", "agent_log",
                               {"error": str(e), "prospect_id": prospect.id})