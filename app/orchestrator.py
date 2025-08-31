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
        """Run the full pipeline with streaming events and detailed MCP tracking"""
        
        # Hunter phase
        yield log_event("hunter", "Starting prospect discovery", "agent_start")
        yield log_event("hunter", "Calling MCP Store to load seed companies", "mcp_call", 
                       {"mcp_server": "store", "method": "load_companies"})
        
        prospects = await self.hunter.run(company_ids)
        
        yield log_event("hunter", f"MCP Store returned {len(prospects)} companies", "mcp_response",
                       {"mcp_server": "store", "companies_count": len(prospects)})
        yield log_event("hunter", f"Found {len(prospects)} prospects", "agent_end", 
                       {"count": len(prospects)})
        
        for prospect in prospects:
            try:
                company_name = prospect.company.name
                
                # Enricher phase
                yield log_event("enricher", f"Enriching {company_name}", "agent_start")
                yield log_event("enricher", f"Calling MCP Search for company facts", "mcp_call",
                               {"mcp_server": "search", "company": company_name})
                
                prospect = await self.enricher.run(prospect)
                
                yield log_event("enricher", f"MCP Search returned facts", "mcp_response",
                               {"mcp_server": "search", "facts_found": len(prospect.facts)})
                yield log_event("enricher", f"Calling MCP Store to save {len(prospect.facts)} facts", "mcp_call",
                               {"mcp_server": "store", "method": "save_facts"})
                yield log_event("enricher", f"Added {len(prospect.facts)} facts", "agent_end",
                               {"facts_count": len(prospect.facts)})
                
                # Contactor phase
                yield log_event("contactor", f"Finding contacts for {company_name}", "agent_start")
                yield log_event("contactor", f"Calling MCP Store to check suppressions", "mcp_call",
                               {"mcp_server": "store", "method": "check_suppression", "domain": prospect.company.domain})
                
                # Check suppression
                store = self.mcp.get_store_client()
                suppressed = await store.check_suppression("domain", prospect.company.domain)
                
                if suppressed:
                    yield log_event("contactor", f"Domain {prospect.company.domain} is suppressed", "mcp_response",
                                   {"mcp_server": "store", "suppressed": True})
                else:
                    yield log_event("contactor", f"Domain {prospect.company.domain} is not suppressed", "mcp_response",
                                   {"mcp_server": "store", "suppressed": False})
                
                prospect = await self.contactor.run(prospect)
                
                if prospect.contacts:
                    yield log_event("contactor", f"Calling MCP Store to save {len(prospect.contacts)} contacts", "mcp_call",
                                   {"mcp_server": "store", "method": "save_contacts"})
                
                yield log_event("contactor", f"Found {len(prospect.contacts)} contacts", "agent_end",
                               {"contacts_count": len(prospect.contacts)})
                
                # Scorer phase
                yield log_event("scorer", f"Scoring {company_name}", "agent_start")
                yield log_event("scorer", "Calculating fit score based on industry, size, and pain points", "agent_log")
                
                prospect = await self.scorer.run(prospect)
                
                yield log_event("scorer", f"Calling MCP Store to save prospect with score", "mcp_call",
                               {"mcp_server": "store", "method": "save_prospect", "fit_score": prospect.fit_score})
                yield log_event("scorer", f"Fit score: {prospect.fit_score:.2f}", "agent_end",
                               {"fit_score": prospect.fit_score, "status": prospect.status})
                
                if prospect.status == "dropped":
                    yield log_event("scorer", f"Dropped: {prospect.dropped_reason}", "agent_log",
                                   {"reason": prospect.dropped_reason})
                    continue
                
                # Writer phase with streaming
                yield log_event("writer", f"Drafting outreach for {company_name}", "agent_start")
                yield log_event("writer", "Calling Vector Store for relevant facts", "mcp_call",
                               {"mcp_server": "vector", "method": "retrieve", "company_id": prospect.company.id})
                yield log_event("writer", "Calling Ollama for content generation", "mcp_call",
                               {"mcp_server": "ollama", "model": "qwen3:0.6b"})
                
                async for event in self.writer.run_streaming(prospect):
                    if event["type"] == "llm_token":
                        yield event
                    elif event["type"] == "llm_done":
                        yield event
                        prospect = event["payload"]["prospect"]
                        yield log_event("writer", "Ollama completed generation", "mcp_response",
                                       {"mcp_server": "ollama", "has_summary": bool(prospect.summary),
                                        "has_email": bool(prospect.email_draft)})
                
                yield log_event("writer", f"Calling MCP Store to save draft", "mcp_call",
                               {"mcp_server": "store", "method": "save_prospect"})
                yield log_event("writer", "Draft complete", "agent_end",
                               {"has_summary": bool(prospect.summary),
                                "has_email": bool(prospect.email_draft)})
                
                # Compliance phase
                yield log_event("compliance", f"Checking compliance for {company_name}", "agent_start")
                yield log_event("compliance", "Calling MCP Store to check email/domain suppressions", "mcp_call",
                               {"mcp_server": "store", "method": "check_suppression"})
                
                # Check each contact for suppression
                for contact in prospect.contacts:
                    email_suppressed = await store.check_suppression("email", contact.email)
                    if email_suppressed:
                        yield log_event("compliance", f"Email {contact.email} is suppressed", "mcp_response",
                                       {"mcp_server": "store", "suppressed": True})
                
                yield log_event("compliance", "Checking CAN-SPAM, PECR, CASL requirements", "agent_log")
                
                prospect = await self.compliance.run(prospect)
                
                if prospect.status == "blocked":
                    yield log_event("compliance", f"Blocked: {prospect.dropped_reason}", "policy_block",
                                   {"reason": prospect.dropped_reason})
                    continue
                else:
                    yield log_event("compliance", "All compliance checks passed", "policy_pass")
                    yield log_event("compliance", "Footer appended to email", "agent_log")
                
                # Sequencer phase
                yield log_event("sequencer", f"Sequencing outreach for {company_name}", "agent_start")
                
                if not prospect.contacts or not prospect.email_draft:
                    yield log_event("sequencer", "Missing contacts or email draft", "agent_log",
                                   {"has_contacts": bool(prospect.contacts),
                                    "has_email": bool(prospect.email_draft)})
                    prospect.status = "blocked"
                    prospect.dropped_reason = "No contacts or email draft available"
                    await store.save_prospect(prospect)
                    yield log_event("sequencer", f"Blocked: {prospect.dropped_reason}", "agent_end")
                    continue
                
                yield log_event("sequencer", "Calling MCP Calendar for available slots", "mcp_call",
                               {"mcp_server": "calendar", "method": "suggest_slots"})
                
                calendar = self.mcp.get_calendar_client()
                slots = await calendar.suggest_slots()
                
                yield log_event("sequencer", f"MCP Calendar returned {len(slots)} slots", "mcp_response",
                               {"mcp_server": "calendar", "slots_count": len(slots)})
                
                if slots:
                    yield log_event("sequencer", "Calling MCP Calendar to generate ICS", "mcp_call",
                                   {"mcp_server": "calendar", "method": "generate_ics"})
                
                yield log_event("sequencer", f"Calling MCP Email to send to {prospect.contacts[0].email}", "mcp_call",
                               {"mcp_server": "email", "method": "send", "recipient": prospect.contacts[0].email})
                
                prospect = await self.sequencer.run(prospect)
                
                yield log_event("sequencer", f"MCP Email created thread", "mcp_response",
                               {"mcp_server": "email", "thread_id": prospect.thread_id})
                yield log_event("sequencer", f"Thread created: {prospect.thread_id}", "agent_end",
                               {"thread_id": prospect.thread_id})
                
                # Curator phase
                yield log_event("curator", f"Creating handoff for {company_name}", "agent_start")
                yield log_event("curator", "Calling MCP Email to retrieve thread", "mcp_call",
                               {"mcp_server": "email", "method": "get_thread", "prospect_id": prospect.id})
                
                email_client = self.mcp.get_email_client()
                thread = await email_client.get_thread(prospect.id) if prospect.thread_id else None
                
                if thread:
                    yield log_event("curator", f"MCP Email returned thread with messages", "mcp_response",
                                   {"mcp_server": "email", "has_thread": True})
                
                yield log_event("curator", "Calling MCP Calendar for meeting slots", "mcp_call",
                               {"mcp_server": "calendar", "method": "suggest_slots"})
                
                prospect = await self.curator.run(prospect)
                
                yield log_event("curator", "Calling MCP Store to save handoff packet", "mcp_call",
                               {"mcp_server": "store", "method": "save_handoff"})
                yield log_event("curator", "Handoff packet created and saved", "mcp_response",
                               {"mcp_server": "store", "saved": True})
                yield log_event("curator", "Handoff ready", "agent_end",
                               {"prospect_id": prospect.id, "status": "ready_for_handoff"})
                
            except Exception as e:
                logger.error(f"Pipeline error for {prospect.company.name}: {e}")
                yield log_event("orchestrator", f"Error: {str(e)}", "agent_log",
                               {"error": str(e), "prospect_id": prospect.id})