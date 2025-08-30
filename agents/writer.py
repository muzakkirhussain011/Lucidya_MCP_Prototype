# file: agents/writer.py
import json
import aiohttp
from typing import AsyncGenerator
from app.schema import Prospect
from app.config import OLLAMA_BASE_URL, MODEL_NAME
from app.logging_utils import log_event
from vector.retriever import Retriever

class Writer:
    """Generates outreach content with Ollama streaming"""
    
    def __init__(self, mcp_registry):
        self.mcp = mcp_registry
        self.store = mcp_registry.get_store_client()
        self.retriever = Retriever()
    
    async def run_streaming(self, prospect: Prospect) -> AsyncGenerator[dict, None]:
        """Generate content with streaming tokens"""
        
        # Get relevant facts from vector store
        relevant_facts = self.retriever.retrieve(prospect.company.id, k=5)
        
        # Build context
        context = f"""
Company: {prospect.company.name}
Industry: {prospect.company.industry}
Size: {prospect.company.size} employees
Domain: {prospect.company.domain}

Pain Points:
{chr(10).join(f'- {pain}' for pain in prospect.company.pains)}

Key Facts:
{chr(10).join(f'- {fact["text"]} (confidence: {fact.get("score", 0.7):.2f})' for fact in relevant_facts[:3])}
"""
        
        # Generate summary first
        summary_prompt = f"""{context}

Generate a brief bullet-point summary of key insights about this company's customer experience opportunities. 
Format: 3-5 bullets, each starting with "•". Be specific and actionable."""
        
        summary_text = ""
        
        async with aiohttp.ClientSession() as session:
            # Summary generation
            async with session.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": MODEL_NAME,
                    "prompt": summary_prompt,
                    "stream": True,
                    "think": False
                }
            ) as response:
                async for line in response.content:
                    if line:
                        try:
                            chunk = json.loads(line)
                            if "response" in chunk:
                                token = chunk["response"]
                                summary_text += token
                                yield log_event("writer", token, "llm_token", 
                                              {"type": "summary", "token": token})
                            
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        
        # Generate email
        # Derive a greeting hint from the first contact, if available
        greeting_name = None
        if prospect.contacts:
            try:
                greeting_name = (prospect.contacts[0].name or "").split()[0] or None
            except Exception:
                greeting_name = None

        greeting_hint = (
            f"Use this greeting exactly: 'Hi {greeting_name},'" if greeting_name else "Use this greeting exactly: 'Hi there,'"
        )

        email_prompt = f"""{context}

You are writing on behalf of Lucidya, a customer experience analytics platform.
The email is from Lucidya to leaders at {prospect.company.name} and should clearly show how Lucidya can help address the pains and facts above.

{greeting_hint}

Requirements:
- Subject line: brief, compelling, references their context or outcomes
- Body: 150–180 words, professional and friendly
- Clearly connect their pains/facts to Lucidya capabilities (e.g., omnichannel feedback, AI-driven sentiment/topics, dashboards, actionable insights)
- Be specific without unverifiable claims; avoid guarantees or inflated numbers
- One clear call-to-action to schedule a short 20–30 minute conversation or demo next week
- Keep it practical and value-focused; no fluff
- Signature: 'The Lucidya Team' (do not invent a personal name)

Format response exactly as:
Subject: [subject line]
Body: [email body]
"""
        
        email_text = ""
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": MODEL_NAME,
                    "prompt": email_prompt,
                    "stream": True,
                    "think": False
                }
            ) as response:
                async for line in response.content:
                    if line:
                        try:
                            chunk = json.loads(line)
                            if "response" in chunk:
                                token = chunk["response"]
                                email_text += token
                                yield log_event("writer", token, "llm_token",
                                              {"type": "email", "token": token})
                            
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        
        # Parse email
        email_parts = {"subject": "", "body": ""}
        if "Subject:" in email_text and "Body:" in email_text:
            parts = email_text.split("Body:")
            email_parts["subject"] = parts[0].replace("Subject:", "").strip()
            email_parts["body"] = parts[1].strip()
        else:
            # Fallback
            email_parts["subject"] = f"Improve {prospect.company.name}'s Customer Experience"
            email_parts["body"] = email_text or "I'd like to discuss how we can help improve your customer experience."
        
        # Update prospect
        prospect.summary = summary_text
        prospect.email_draft = email_parts
        prospect.status = "drafted"
        await self.store.save_prospect(prospect)
        
        # Emit completion event
        yield log_event("writer", "Generation complete", "llm_done", 
                       {"prospect": prospect, "summary": summary_text, "email": email_parts})
    
    async def run(self, prospect: Prospect) -> Prospect:
        """Non-streaming version for compatibility"""
        async for event in self.run_streaming(prospect):
            if event["type"] == "llm_done":
                return event["payload"]["prospect"]
        return prospect
